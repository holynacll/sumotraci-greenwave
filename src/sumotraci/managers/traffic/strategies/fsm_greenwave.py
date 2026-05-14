"""Intermediate green-wave strategy: 3-phase FSM + visual highlight only.

Sits between ``legacy_greenwave`` (no improvements) and ``edf_greenwave`` (FSM +
ETA + queue + anti-flicker). Adds **only** the structural improvements:

  - Clean 3-phase FSM (CLEARING → EV_GREEN → EXIT_YELLOW), event-driven exit
    from EV_GREEN.
  - Visual highlight overlay (lane stripe + TLS marker, severity-coloured).
  - Strategy-pattern architecture (this file).

What it intentionally does **not** include (so the ablation is meaningful):

  - ETA-based priority — uses **deadline-based** arbitration (smaller deadline
    wins immediately, like legacy).
  - Anti-flicker (no MIN_EV_GREEN_HOLD, no PREEMPT_DELTA_THRESHOLD).
  - Pending queue with hand-off — losers are dropped and may re-request next
    tick (like legacy).
  - Spillback shield / drain mechanism.

Operational improvements (CollisionManager with EV preservation, scenario
defaults, ``--collision.action warn``) are global and apply to every strategy
including this one.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from ....core.config import Settings
from ....core.sumo_interface import SumoInterface
from ....domain.enums import SeverityEnum
from ....domain.schemas import GreenWaveAllocationView
from ...emergency_manager import EmergencyManager
from ..green_wave import first_route_edge_at_tls
from .base import TrafficControlStrategy

_DEFAULT_HIGHLIGHT_COLOR: Tuple[int, int, int, int] = (255, 255, 255, 255)
_TLS_MARKER_HALF_SIZE: float = 4.0
_LANE_HIGHLIGHT_LINE_WIDTH: float = 3.0
_HIGHLIGHT_LAYER: int = 10


class _Phase(str, Enum):
    CLEARING = "CLEARING"
    EV_GREEN = "EV_GREEN"
    EXIT_YELLOW = "EXIT_YELLOW"


@dataclass
class _Allocation:
    tls_id: str
    requester_id: str
    deadline: float
    severity: str
    original_program: str
    controlled_lanes: List[str]
    priority_edge: str
    phase: _Phase
    wait_until: Optional[float]
    highlight_polygon_ids: List[str] = field(default_factory=list)


class _FSMGreenWaveManager:
    """Stripped-down GreenWaveManager: FSM + viz, deadline-based arbitration, no queue."""

    def __init__(self, settings: Settings, sumo: SumoInterface):
        self.settings = settings
        self.sumo = sumo
        self._allocations: List[_Allocation] = []
        self._highlight_counter: int = 0

    # -------- public API --------

    def request(
        self,
        tls_id: str,
        requester_id: str,
        priority_edge: str,
        deadline: float,
        severity: str,
    ) -> bool:
        existing = self._find_at_tls(tls_id)
        if existing is not None:
            if existing.requester_id == requester_id:
                existing.deadline = deadline  # idempotent refresh
                return True
            # Deadline-based arbitration: smaller deadline wins immediately.
            # No anti-flicker, no delta threshold.
            if existing.deadline <= deadline:
                return False  # incumbent stays — loser is dropped (no queue)
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
            deadline=deadline,
            severity=severity,
            original_program=original_program,
            controlled_lanes=controlled_lanes,
            priority_edge=priority_edge,
            phase=_Phase.CLEARING,
            wait_until=None,
        )
        self._enter_clearing(alloc)
        self._allocations.append(alloc)
        return True

    def tick(self, now: float) -> None:
        survivors: List[_Allocation] = []
        for alloc in self._allocations:
            if self._ready_to_advance(alloc, now):
                if alloc.phase == _Phase.CLEARING:
                    self._enter_ev_green(alloc)
                elif alloc.phase == _Phase.EV_GREEN:
                    self._enter_exit_yellow(alloc, now)
                elif alloc.phase == _Phase.EXIT_YELLOW:
                    self._restore(alloc)
                    continue
            survivors.append(alloc)
        self._allocations = survivors

    @property
    def allocations(self) -> List[GreenWaveAllocationView]:
        return [
            GreenWaveAllocationView(
                tls_id=a.tls_id,
                requester_id=a.requester_id,
                priority_value=a.deadline,
                severity=a.severity,
                phase=a.phase.value,
            )
            for a in self._allocations
        ]

    # -------- phase logic --------

    def _ready_to_advance(self, alloc: _Allocation, now: float) -> bool:
        if alloc.phase == _Phase.EV_GREEN:
            return self._ev_has_passed(alloc)
        return alloc.wait_until is not None and now >= alloc.wait_until

    def _enter_clearing(self, alloc: _Allocation) -> None:
        try:
            current = self.sumo.trafficlight_get_red_yellow_green_state(alloc.tls_id)
        except self.sumo.TraCIException:
            return
        new_state = "".join(
            ch if alloc.priority_edge in lane
            else ("y" if ch in ("g", "G") else ch)
            for ch, lane in zip(current, alloc.controlled_lanes)
        )
        if new_state != current:
            try:
                self.sumo.trafficlight_set_red_yellow_green_state(alloc.tls_id, new_state)
            except self.sumo.TraCIException:
                return
        alloc.phase = _Phase.CLEARING
        alloc.wait_until = (
            self.sumo.get_time() + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT
        )
        self._set_highlight(alloc)

    def _enter_ev_green(self, alloc: _Allocation) -> None:
        new_state = "".join(
            "G" if alloc.priority_edge in lane else "r"
            for lane in alloc.controlled_lanes
        )
        try:
            self.sumo.trafficlight_set_red_yellow_green_state(alloc.tls_id, new_state)
        except self.sumo.TraCIException:
            return
        alloc.phase = _Phase.EV_GREEN
        alloc.wait_until = None

    def _enter_exit_yellow(self, alloc: _Allocation, now: float) -> None:
        try:
            current = self.sumo.trafficlight_get_red_yellow_green_state(alloc.tls_id)
        except self.sumo.TraCIException:
            return
        new_state = "".join("y" if ch in ("g", "G") else ch for ch in current)
        try:
            self.sumo.trafficlight_set_red_yellow_green_state(alloc.tls_id, new_state)
        except self.sumo.TraCIException:
            return
        alloc.phase = _Phase.EXIT_YELLOW
        alloc.wait_until = now + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT

    def _ev_has_passed(self, alloc: _Allocation) -> bool:
        try:
            next_tls = self.sumo.vehicle_get_next_tls(alloc.requester_id)
        except self.sumo.TraCIException:
            return True
        return not any(
            entry[0] == alloc.tls_id
            and entry[2] <= self.settings.VEHICLE_DISTANCE_TO_TLS
            for entry in next_tls
        )

    def _restore(self, alloc: _Allocation) -> None:
        self._clear_highlight(alloc)
        try:
            self.sumo.trafficlight_set_program(alloc.tls_id, alloc.original_program)
        except self.sumo.TraCIException:
            pass
        print(
            f"{self.sumo.get_time()} - Emergency Vehicle "
            f"{alloc.requester_id} has left TLS {alloc.tls_id} (fsm)"
        )

    # -------- helpers --------

    def _find_at_tls(self, tls_id: str) -> Optional[_Allocation]:
        for a in self._allocations:
            if a.tls_id == tls_id:
                return a
        return None

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
        try:
            return self.settings.SEVERITY_COLORS[SeverityEnum(alloc.severity)]
        except (ValueError, KeyError):
            return _DEFAULT_HIGHLIGHT_COLOR

    def _next_highlight_id(self, kind: str) -> str:
        self._highlight_counter += 1
        return f"hl_fsm_{kind}_{self._highlight_counter}"


class FSMGreenWaveStrategy(TrafficControlStrategy):
    def __init__(
        self,
        settings: Settings,
        sumo: SumoInterface,
        emergency_manager: EmergencyManager,
    ):
        self.settings = settings
        self.sumo = sumo
        self.emergency_manager = emergency_manager
        self._green_wave = _FSMGreenWaveManager(settings, sumo)

    def improve(self) -> None:
        self._green_wave.tick(self.sumo.get_time())

        evs_sorted = sorted(
            self.emergency_manager.buffer_emergency_vehicles,
            key=lambda ev: ev.deadline,
        )
        for ev in evs_sorted:
            try:
                next_tls = self.sumo.vehicle_get_next_tls(ev.veh_emergency_id)
            except self.sumo.TraCIException:
                continue

            for tls_id, _tls_index, distance, _state in next_tls:
                if distance > self.settings.VEHICLE_DISTANCE_TO_TLS:
                    continue
                try:
                    controlled_lanes = self.sumo.trafficlight_get_controlled_lanes(tls_id)
                except self.sumo.TraCIException:
                    continue
                priority_edge = first_route_edge_at_tls(
                    self.sumo, ev.veh_emergency_id, controlled_lanes
                )
                if priority_edge is None:
                    continue
                self._green_wave.request(
                    tls_id=tls_id,
                    requester_id=ev.veh_emergency_id,
                    priority_edge=priority_edge,
                    deadline=ev.deadline,
                    severity=ev.severity,
                )

    def active_allocations(self) -> List[GreenWaveAllocationView]:
        return self._green_wave.allocations
