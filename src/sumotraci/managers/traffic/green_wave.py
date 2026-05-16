from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from ...core.config import Settings
from ...core.sumo_interface import SumoInterface
from ...domain.enums import SeverityEnum
from ...domain.schemas import GreenWaveAllocationView
from .edf import ArbitrationPolicy, EDFArbitration

_DRAIN_HIGHLIGHT_COLOR: Tuple[int, int, int, int] = (0, 200, 255, 255)
_DEFAULT_HIGHLIGHT_COLOR: Tuple[int, int, int, int] = (255, 255, 255, 255)
_TLS_MARKER_HALF_SIZE: float = 4.0
_LANE_HIGHLIGHT_LINE_WIDTH: float = 3.0
_HIGHLIGHT_LAYER: int = 10


class Phase(str, Enum):
    CLEARING = "CLEARING"        # yellow on opposing greens; wait T_clear
    EV_GREEN = "EV_GREEN"        # green for priority lane, red elsewhere; wait until requester is done
    EXIT_YELLOW = "EXIT_YELLOW"  # yellow on priority greens; wait T_clear, then restore or hand off


@dataclass
class _PendingRequest:
    requester_id: str
    priority_edge: str
    priority_value: float
    severity: str


@dataclass
class _Allocation:
    tls_id: str
    requester_id: str       # vehicle ID for EVs; "drain:<edge>" for spillback drains
    priority_value: float   # ETA-based for EVs; DRAIN_PRIORITY_VALUE for drains. Lower = wins arbitration.
    severity: str
    original_program: str
    controlled_lanes: List[str]
    priority_edge: str      # edge whose lanes receive the green signal
    phase: Phase
    wait_until: Optional[float]     # absolute sim time; None means event-driven exit
    # set when entering EV_GREEN; used for anti-flicker hold and drain timeout
    ev_green_started_at: Optional[float] = None
    pending: List[_PendingRequest] = field(default_factory=list)  # priority-sorted waiters
    highlight_polygon_ids: List[str] = field(default_factory=list)  # SUMO polygon IDs for visual overlay


def first_route_edge_at_tls(
    sumo: SumoInterface, veh_id: str, controlled_lanes: List[str]
) -> Optional[str]:
    """Return the first edge on veh_id's remaining route that is controlled by this TLS."""
    controlled_edges = {sumo.lane_get_edge_id(lane) for lane in controlled_lanes}
    route = sumo.vehicle_get_route(veh_id)
    idx = sumo.vehicle_get_route_index(veh_id)
    for edge in route[idx:]:
        if edge in controlled_edges:
            return edge
    return None


class GreenWaveManager:
    """
    Drives a 3-phase preemption per active allocation:

        CLEARING    → yellow on opposing greens, wait T_clear
        EV_GREEN    → green for priority lane, red elsewhere; exit is event-driven
        EXIT_YELLOW → yellow on priority greens, wait T_clear, then either hand off to
                      the next pending requester (no program restore) or restore original

    Public surface: request(), request_drain(), tick(), allocations.

    Requesters: an EV (requester_id = vehicle ID) or a drain (requester_id = "drain:<edge>").
    For EVs the event-driven exit checks vehicle_get_next_tls; for drains it checks lane
    occupancy with hysteresis.

    Arbitration is ETA-based (smaller `priority_value` wins). Two anti-flicker mechanisms:
      * MIN_EV_GREEN_HOLD: an EV holder is non-preemptable for the first N seconds
        after entering EV_GREEN. Drain holders are NOT subject to this lock-out
        (any EV preempts a drain immediately).
      * PREEMPT_DELTA_THRESHOLD: a new requester must be at least delta seconds
        better in priority_value to displace the holder; otherwise it queues.

    Pending queue: when a request loses arbitration to the current holder, it joins
    the holder's pending list (priority-sorted). On natural finish the next pending
    requester takes over directly — avoiding a round-trip through the original program.
    The pending list is wiped each tick and refilled by the strategy's calls in the
    same step.
    """

    def __init__(
        self,
        settings: Settings,
        sumo: SumoInterface,
        arbitration: Optional[ArbitrationPolicy] = None,
        min_ev_green_hold: Optional[float] = None,
        use_pending_queue: bool = True,
    ):
        self.settings = settings
        self.sumo = sumo
        self.arbitration: ArbitrationPolicy = arbitration or EDFArbitration(
            delta=settings.PREEMPT_DELTA_THRESHOLD
        )
        # Anti-flicker hold window. Pass 0.0 to disable the EV_GREEN lock-out
        # (the strategy does this when GW_ANTIFLICKER is off).
        self._min_ev_green_hold: float = (
            min_ev_green_hold
            if min_ev_green_hold is not None
            else settings.MIN_EV_GREEN_HOLD
        )
        # When False, requests that lose arbitration are dropped instead of
        # queued; the strategy re-requests next tick. With the queue empty,
        # tick()/_handoff_or_restore() naturally degenerate to plain restore.
        self._use_pending_queue: bool = use_pending_queue
        self._allocations: List[_Allocation] = []
        self._highlight_counter: int = 0

    # -------- public API --------

    def request(
        self,
        tls_id: str,
        requester_id: str,
        priority_edge: str,
        priority_value: float,
        severity: str = "",
    ) -> bool:
        """Register a green-wave allocation for priority_edge at tls_id.

        priority_edge must be an edge controlled by this TLS and on the requester's
        path (for EVs) or the saturated edge (for drains). priority_value is the
        ETA-based score for arbitration (smaller = more urgent).

        Returns True if accepted (new allocation, idempotent re-request, preemption,
        or queued). Returns False only when the TLS state cannot be read.
        """
        existing = self._find_at_tls(tls_id)
        if existing is not None:
            if existing.requester_id == requester_id:
                # Idempotent: refresh the priority_value so dynamic ETA is reflected.
                existing.priority_value = priority_value
                return True
            if self._holder_is_locked(existing):
                if self._use_pending_queue:
                    self._enqueue(existing, requester_id, priority_edge, priority_value, severity)
                return True
            if not self.arbitration.can_preempt(existing.priority_value, priority_value):
                if self._use_pending_queue:
                    self._enqueue(existing, requester_id, priority_edge, priority_value, severity)
                return True
            # Preempt: tear down the holder and fall through to install the new one.
            # The displaced holder's pending list is discarded — the strategy will
            # refill it within this same tick (it iterates EVs in EDF order).
            self._restore(existing)
            self._allocations.remove(existing)

        try:
            controlled_lanes = self.sumo.trafficlight_get_controlled_lanes(tls_id)
            original_program = self.sumo.trafficlight_get_program(tls_id)
        except self.sumo.TraCIException:
            return False

        alloc = _Allocation(
            tls_id=tls_id,
            requester_id=requester_id,
            priority_value=priority_value,
            severity=severity,
            original_program=original_program,
            controlled_lanes=controlled_lanes,
            priority_edge=priority_edge,
            phase=Phase.CLEARING,
            wait_until=None,
        )
        self._enter_clearing(alloc)
        self._allocations.append(alloc)
        return True

    def request_drain(self, tls_id: str, saturated_edge: str) -> bool:
        """Request green for saturated_edge to drain a spillback bottleneck."""
        return self.request(
            tls_id=tls_id,
            requester_id=f"drain:{saturated_edge}",
            priority_edge=saturated_edge,
            priority_value=self.settings.DRAIN_PRIORITY_VALUE,
            severity="DRAIN",
        )

    def tick(self, now: float) -> None:
        """Advance every allocation by zero or one phase; restore or hand off the finished ones."""
        # Drop finished allocations only via the survivors swap below — never via
        # in-place self._allocations.remove() during this iteration. Removing in-place
        # would shift indices and cause the for-loop iterator to skip the next alloc,
        # leaking its TLS in a frozen manual state.
        survivors: List[_Allocation] = []
        for alloc in self._allocations:
            if self._ready_to_advance(alloc, now):
                if alloc.phase == Phase.CLEARING:
                    self._enter_ev_green(alloc, now)
                elif alloc.phase == Phase.EV_GREEN:
                    self._enter_exit_yellow(alloc, now)
                elif alloc.phase == Phase.EXIT_YELLOW:
                    replacement = self._handoff_or_restore(alloc)
                    if replacement is not None:
                        survivors.append(replacement)
                    continue
            survivors.append(alloc)
        # Wipe pending; the strategy's request() calls in this same step will refill it.
        # This is the staleness guard: an EV that moved out of range last step will not
        # request again, so its pending entry simply will not reappear.
        for a in survivors:
            a.pending = []
        self._allocations = survivors

    @property
    def allocations(self) -> List[GreenWaveAllocationView]:
        return [
            GreenWaveAllocationView(
                tls_id=a.tls_id,
                requester_id=a.requester_id,
                priority_value=a.priority_value,
                severity=a.severity,
                phase=a.phase.value,
            )
            for a in self._allocations
        ]

    # -------- phase logic --------

    def _ready_to_advance(self, alloc: _Allocation, now: float) -> bool:
        if alloc.phase == Phase.EV_GREEN:
            return self._requester_done(alloc, now)
        # CLEARING and EXIT_YELLOW are time-gated.
        return alloc.wait_until is not None and now >= alloc.wait_until

    def _enter_clearing(self, alloc: _Allocation) -> None:
        # Set yellow on lanes currently green on conflicting approaches; preserve the
        # priority lane so SUMO advances it naturally to red while we wait.
        current = self.sumo.trafficlight_get_red_yellow_green_state(alloc.tls_id)
        new_state = "".join(
            ch if alloc.priority_edge in lane
            else ("y" if ch in ("g", "G") else ch)
            for ch, lane in zip(current, alloc.controlled_lanes)
        )
        if new_state != current:
            self.sumo.trafficlight_set_red_yellow_green_state(alloc.tls_id, new_state)
        alloc.phase = Phase.CLEARING
        alloc.wait_until = (
            self.sumo.get_time() + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT
        )
        self._set_highlight(alloc)

    def _enter_ev_green(self, alloc: _Allocation, now: float) -> None:
        new_state = "".join(
            "G" if alloc.priority_edge in lane else "r"
            for lane in alloc.controlled_lanes
        )
        self.sumo.trafficlight_set_red_yellow_green_state(alloc.tls_id, new_state)
        alloc.phase = Phase.EV_GREEN
        alloc.wait_until = None
        alloc.ev_green_started_at = now

    def _enter_exit_yellow(self, alloc: _Allocation, now: float) -> None:
        current = self.sumo.trafficlight_get_red_yellow_green_state(alloc.tls_id)
        new_state = "".join("y" if ch in ("g", "G") else ch for ch in current)
        self.sumo.trafficlight_set_red_yellow_green_state(alloc.tls_id, new_state)
        alloc.phase = Phase.EXIT_YELLOW
        alloc.wait_until = now + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT

    # -------- handoff & queue --------

    def _holder_is_locked(self, holder: _Allocation) -> bool:
        """True if the holder is in the EV_GREEN anti-flicker hold window.

        Drain holders are NOT locked — any EV preempts a drain immediately.
        """
        if holder.requester_id.startswith("drain:"):
            return False
        if holder.phase != Phase.EV_GREEN or holder.ev_green_started_at is None:
            return False
        return (self.sumo.get_time() - holder.ev_green_started_at) < self._min_ev_green_hold

    def _enqueue(
        self,
        holder: _Allocation,
        requester_id: str,
        priority_edge: str,
        priority_value: float,
        severity: str,
    ) -> None:
        # Idempotent on requester_id; refresh fields in case they changed.
        for p in holder.pending:
            if p.requester_id == requester_id:
                p.priority_value = priority_value
                p.severity = severity
                p.priority_edge = priority_edge
                break
        else:
            holder.pending.append(
                _PendingRequest(
                    requester_id=requester_id,
                    priority_edge=priority_edge,
                    priority_value=priority_value,
                    severity=severity,
                )
            )
        holder.pending.sort(key=lambda p: p.priority_value)

    def _handoff_or_restore(self, finishing: _Allocation) -> Optional[_Allocation]:
        """If a still-relevant pending requester exists, hand off without restoring the program.
        Otherwise restore the original program. Returns the new allocation, or None."""
        while finishing.pending:
            head = finishing.pending.pop(0)
            if not self._is_still_relevant(finishing.tls_id, head.requester_id):
                continue

            self._clear_highlight(finishing)
            successor = _Allocation(
                tls_id=finishing.tls_id,
                requester_id=head.requester_id,
                priority_value=head.priority_value,
                severity=head.severity,
                # Preserve the original program captured by the very first holder so
                # the program is restored only when the queue truly empties.
                original_program=finishing.original_program,
                controlled_lanes=finishing.controlled_lanes,
                priority_edge=head.priority_edge,
                phase=Phase.CLEARING,
                wait_until=None,
                pending=list(finishing.pending),  # rest of the queue carries over
            )
            self._enter_clearing(successor)
            print(
                f"{self.sumo.get_time()} - Hand-off at TLS {finishing.tls_id}: "
                f"{finishing.requester_id} -> {head.requester_id}"
            )
            return successor

        self._restore(finishing)
        return None

    def _is_still_relevant(self, tls_id: str, requester_id: str) -> bool:
        if requester_id.startswith("drain:"):
            return True  # drain freshness is managed by the strategy, not the pending queue
        return self._ev_currently_in_range(tls_id, requester_id)

    def _ev_currently_in_range(self, tls_id: str, veh_id: str) -> bool:
        try:
            next_tls = self.sumo.vehicle_get_next_tls(veh_id)
        except self.sumo.TraCIException:
            return False
        return any(
            entry[0] == tls_id and entry[2] <= self.settings.VEHICLE_DISTANCE_TO_TLS
            for entry in next_tls
        )

    # -------- helpers --------

    def _find_at_tls(self, tls_id: str) -> Optional[_Allocation]:
        for a in self._allocations:
            if a.tls_id == tls_id:
                return a
        return None

    def _requester_done(self, alloc: _Allocation, now: float) -> bool:
        """Return True when it is time to leave EV_GREEN phase."""
        if alloc.requester_id.startswith("drain:"):
            return self._drain_done(alloc, now)
        return self._ev_has_passed(alloc)

    def _drain_done(self, alloc: _Allocation, now: float) -> bool:
        # Safety cap: drain has been active too long regardless of occupancy.
        if (
            alloc.ev_green_started_at is not None
            and now - alloc.ev_green_started_at >= self.settings.DRAIN_MAX_DURATION
        ):
            return True
        # Hysteresis: occupancy fell below the release threshold.
        return self._max_lane_occupancy(alloc.priority_edge) < self.settings.SPILLBACK_OCCUPANCY_RELEASE_THRESHOLD

    def _max_lane_occupancy(self, edge_id: str) -> float:
        """Return the maximum last-step occupancy across all lanes of edge_id."""
        try:
            n_lanes = self.sumo.edge_get_lane_number(edge_id)
            return max(
                self.sumo.lane_get_last_step_occupancy(f"{edge_id}_{i}")
                for i in range(n_lanes)
            )
        except self.sumo.TraCIException:
            return 0.0

    def _ev_has_passed(self, alloc: _Allocation) -> bool:
        try:
            next_tls = self.sumo.vehicle_get_next_tls(alloc.requester_id)
        except self.sumo.TraCIException:
            return True  # EV gone: wrap the allocation up
        return not any(
            entry[0] == alloc.tls_id
            and entry[2] <= self.settings.VEHICLE_DISTANCE_TO_TLS
            for entry in next_tls
        )

    def _restore(self, alloc: _Allocation) -> None:
        """Restore TLS to its original program. Caller drops the alloc from the list."""
        self._clear_highlight(alloc)
        try:
            self.sumo.trafficlight_set_program(alloc.tls_id, alloc.original_program)
        except self.sumo.TraCIException:
            pass
        label = "Drain" if alloc.requester_id.startswith("drain:") else "Emergency Vehicle"
        print(
            f"{self.sumo.get_time()} - {label} "
            f"{alloc.requester_id} has left TLS {alloc.tls_id}"
        )

    # -------- highlight overlay --------

    def _set_highlight(self, alloc: _Allocation) -> None:
        if not self.settings.HIGHLIGHT_ALLOCATIONS:
            return
        self._clear_highlight(alloc)
        color = self._allocation_color(alloc)

        for lane_id in alloc.controlled_lanes:
            if alloc.priority_edge not in lane_id:
                continue
            try:
                shape = self.sumo.lane_get_shape(lane_id)
            except self.sumo.TraCIException:
                continue
            if len(shape) < 2:
                continue
            poly_id = self._next_highlight_id("lane")
            try:
                self.sumo.polygon_add(
                    poly_id, shape, color,
                    fill=False, layer=_HIGHLIGHT_LAYER, line_width=_LANE_HIGHLIGHT_LINE_WIDTH,
                )
                alloc.highlight_polygon_ids.append(poly_id)
            except self.sumo.TraCIException:
                continue

        try:
            x, y = self.sumo.junction_get_position(alloc.tls_id)
        except self.sumo.TraCIException:
            return
        h = _TLS_MARKER_HALF_SIZE
        marker_shape = [
            (x - h, y - h), (x + h, y - h), (x + h, y + h), (x - h, y + h), (x - h, y - h),
        ]
        poly_id = self._next_highlight_id("tls")
        try:
            self.sumo.polygon_add(
                poly_id, marker_shape, color,
                fill=True, layer=_HIGHLIGHT_LAYER, line_width=1.0,
            )
            alloc.highlight_polygon_ids.append(poly_id)
        except self.sumo.TraCIException:
            pass

    def _clear_highlight(self, alloc: _Allocation) -> None:
        for poly_id in alloc.highlight_polygon_ids:
            try:
                self.sumo.polygon_remove(poly_id, layer=_HIGHLIGHT_LAYER)
            except self.sumo.TraCIException:
                pass
        alloc.highlight_polygon_ids = []

    def _allocation_color(self, alloc: _Allocation) -> Tuple[int, int, int, int]:
        if alloc.requester_id.startswith("drain:"):
            return _DRAIN_HIGHLIGHT_COLOR
        try:
            return self.settings.SEVERITY_COLORS[SeverityEnum(alloc.severity)]
        except (ValueError, KeyError):
            return _DEFAULT_HIGHLIGHT_COLOR

    def _next_highlight_id(self, kind: str) -> str:
        self._highlight_counter += 1
        return f"hl_{kind}_{self._highlight_counter}"
