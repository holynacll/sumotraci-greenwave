from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from ...core.config import Settings
from ...core.sumo_interface import SumoInterface
from ...domain.schemas import GreenWaveAllocationView
from .edf import ArbitrationPolicy, EDFArbitration


class Phase(str, Enum):
    CLEARING = "CLEARING"        # yellow on opposing greens; wait T_clear
    EV_GREEN = "EV_GREEN"        # green for EV's lane, red elsewhere; wait until EV passes
    EXIT_YELLOW = "EXIT_YELLOW"  # yellow on EV greens; wait T_clear, then restore or hand off


@dataclass
class _PendingRequest:
    veh_emergency_id: str
    deadline: float
    severity: str


@dataclass
class _Allocation:
    tls_id: str
    veh_emergency_id: str
    deadline: float
    severity: str
    original_program: str
    controlled_lanes: List[str]
    ev_edge: str                                       # edge name; substring-matched against lane IDs
    phase: Phase
    wait_until: Optional[float]                        # absolute sim time; None means event-driven exit
    pending: List[_PendingRequest] = field(default_factory=list)  # EDF-sorted waiters


class GreenWaveManager:
    """
    Drives a 3-phase preemption per active allocation:

        CLEARING    → yellow on opposing greens, wait T_clear
        EV_GREEN    → green for EV's lane, red elsewhere, wait until EV is past TLS
        EXIT_YELLOW → yellow on EV greens, wait T_clear, then either hand off to the
                      next pending EV (no program restore) or restore the original program

    Public surface: request(), tick(), allocations.

    Pending queue: when a request loses arbitration to the current holder, it joins
    the holder's pending list (EDF-sorted) instead of being dropped. On natural finish
    of the holder, the next pending EV takes over directly — avoiding a wasteful
    round-trip through the original program. The pending list is wiped each tick and
    refilled by the strategy's request() calls within the same step, so stale entries
    (EVs that moved out of range) cannot accumulate.
    """

    def __init__(
        self,
        settings: Settings,
        sumo: SumoInterface,
        arbitration: Optional[ArbitrationPolicy] = None,
    ):
        self.settings = settings
        self.sumo = sumo
        self.arbitration: ArbitrationPolicy = arbitration or EDFArbitration()
        self._allocations: List[_Allocation] = []

    # -------- public API --------

    def request(
        self,
        tls_id: str,
        veh_emergency_id: str,
        deadline: float,
        severity: str = "",
    ) -> bool:
        """Register a green-wave allocation, preempt the current holder, or queue.

        Returns True if accepted (newly created, idempotent re-request, preemption,
        or queued). Returns False only when the EV's route does not pass through
        this TLS (or the TLS state cannot be read).
        """
        existing = self._find_at_tls(tls_id)
        if existing is not None:
            if existing.veh_emergency_id == veh_emergency_id:
                return True  # idempotent: this EV is already the holder
            if not self.arbitration.can_preempt(existing.deadline, deadline):
                self._enqueue(existing, veh_emergency_id, deadline, severity)
                return True
            # Preempt: tear down the holder and fall through to install the new one.
            # The displaced holder's pending list is discarded — the strategy will
            # refill it within this same tick (it iterates EVs in EDF order).
            self._restore(existing)
            self._allocations.remove(existing)

        try:
            controlled_lanes = self.sumo.trafficlight_get_controlled_lanes(tls_id)
            ev_edge = self._first_route_edge_at_tls(veh_emergency_id, controlled_lanes)
            if ev_edge is None:
                return False
            original_program = self.sumo.trafficlight_get_program(tls_id)
        except self.sumo.TraCIException:
            return False

        alloc = _Allocation(
            tls_id=tls_id,
            veh_emergency_id=veh_emergency_id,
            deadline=deadline,
            severity=severity,
            original_program=original_program,
            controlled_lanes=controlled_lanes,
            ev_edge=ev_edge,
            phase=Phase.CLEARING,
            wait_until=None,
        )
        self._enter_clearing(alloc)
        self._allocations.append(alloc)
        return True

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
                    self._enter_ev_green(alloc)
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
                veh_emergency_id=a.veh_emergency_id,
                deadline=a.deadline,
                severity=a.severity,
                phase=a.phase.value,
            )
            for a in self._allocations
        ]

    # -------- phase logic --------

    def _ready_to_advance(self, alloc: _Allocation, now: float) -> bool:
        if alloc.phase == Phase.EV_GREEN:
            return self._ev_has_passed(alloc)
        # CLEARING and EXIT_YELLOW are time-gated.
        return alloc.wait_until is not None and now >= alloc.wait_until

    def _enter_clearing(self, alloc: _Allocation) -> None:
        # Set yellow on lanes currently green on conflicting approaches; preserve the
        # EV lane so SUMO advances it naturally to red while we wait the clearing window.
        current = self.sumo.trafficlight_get_red_yellow_green_state(alloc.tls_id)
        new_state = "".join(
            ch if alloc.ev_edge in lane
            else ("y" if ch in ("g", "G") else ch)
            for ch, lane in zip(current, alloc.controlled_lanes)
        )
        if new_state != current:
            self.sumo.trafficlight_set_red_yellow_green_state(alloc.tls_id, new_state)
        alloc.phase = Phase.CLEARING
        alloc.wait_until = (
            self.sumo.get_time() + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT
        )

    def _enter_ev_green(self, alloc: _Allocation) -> None:
        new_state = "".join(
            "G" if alloc.ev_edge in lane else "r"
            for lane in alloc.controlled_lanes
        )
        self.sumo.trafficlight_set_red_yellow_green_state(alloc.tls_id, new_state)
        alloc.phase = Phase.EV_GREEN
        alloc.wait_until = None  # exit is event-driven (EV passes the TLS)

    def _enter_exit_yellow(self, alloc: _Allocation, now: float) -> None:
        current = self.sumo.trafficlight_get_red_yellow_green_state(alloc.tls_id)
        new_state = "".join("y" if ch in ("g", "G") else ch for ch in current)
        self.sumo.trafficlight_set_red_yellow_green_state(alloc.tls_id, new_state)
        alloc.phase = Phase.EXIT_YELLOW
        alloc.wait_until = now + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT

    # -------- handoff & queue --------

    def _enqueue(
        self,
        holder: _Allocation,
        veh_emergency_id: str,
        deadline: float,
        severity: str,
    ) -> None:
        # Idempotent on veh_emergency_id; refresh the deadline in case it changed.
        for p in holder.pending:
            if p.veh_emergency_id == veh_emergency_id:
                p.deadline = deadline
                p.severity = severity
                break
        else:
            holder.pending.append(
                _PendingRequest(
                    veh_emergency_id=veh_emergency_id,
                    deadline=deadline,
                    severity=severity,
                )
            )
        holder.pending.sort(key=lambda p: p.deadline)

    def _handoff_or_restore(self, finishing: _Allocation) -> Optional[_Allocation]:
        """If a still-relevant pending EV exists, hand off without restoring the program.
        Otherwise restore the original program. Returns the new allocation, or None."""
        while finishing.pending:
            head = finishing.pending.pop(0)
            if not self._ev_currently_in_range(finishing.tls_id, head.veh_emergency_id):
                continue
            try:
                ev_edge = self._first_route_edge_at_tls(
                    head.veh_emergency_id, finishing.controlled_lanes
                )
            except self.sumo.TraCIException:
                continue
            if ev_edge is None:
                continue

            successor = _Allocation(
                tls_id=finishing.tls_id,
                veh_emergency_id=head.veh_emergency_id,
                deadline=head.deadline,
                severity=head.severity,
                # Preserve the original program captured by the very first holder so
                # the program is restored only when the queue truly empties.
                original_program=finishing.original_program,
                controlled_lanes=finishing.controlled_lanes,
                ev_edge=ev_edge,
                phase=Phase.CLEARING,
                wait_until=None,
                pending=list(finishing.pending),  # rest of the queue carries over
            )
            self._enter_clearing(successor)
            print(
                f"{self.sumo.get_time()} - Hand-off at TLS {finishing.tls_id}: "
                f"{finishing.veh_emergency_id} -> {head.veh_emergency_id}"
            )
            return successor

        self._restore(finishing)
        return None

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

    def _first_route_edge_at_tls(
        self, veh_id: str, controlled_lanes: List[str]
    ) -> Optional[str]:
        controlled_edges = {self.sumo.lane_get_edge_id(lane) for lane in controlled_lanes}
        route = self.sumo.vehicle_get_route(veh_id)
        idx = self.sumo.vehicle_get_route_index(veh_id)
        for edge in route[idx:]:
            if edge in controlled_edges:
                return edge
        return None

    def _ev_has_passed(self, alloc: _Allocation) -> bool:
        try:
            next_tls = self.sumo.vehicle_get_next_tls(alloc.veh_emergency_id)
        except self.sumo.TraCIException:
            return True  # EV gone: wrap the allocation up
        return not any(
            entry[0] == alloc.tls_id
            and entry[2] <= self.settings.VEHICLE_DISTANCE_TO_TLS
            for entry in next_tls
        )

    def _restore(self, alloc: _Allocation) -> None:
        """Restore TLS to its original program. Caller drops the alloc from the list."""
        try:
            self.sumo.trafficlight_set_program(alloc.tls_id, alloc.original_program)
        except self.sumo.TraCIException:
            pass
        print(
            f"{self.sumo.get_time()} - Emergency Vehicle "
            f"{alloc.veh_emergency_id} has left TLS {alloc.tls_id}"
        )
