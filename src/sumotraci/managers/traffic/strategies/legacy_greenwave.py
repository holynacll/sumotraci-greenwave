"""Original (pre-refactor) green-wave strategy.

Direct port of commit 664cef5's monolithic ``TrafficManager._green_wave_logic``
into the strategy interface. Kept as a comparison baseline so the value of the
later improvements (3-phase FSM, ETA-based priority, anti-flicker, pending
queue with hand-off, spillback shield, visual highlight) can be ablated.

Behaviour preserved verbatim:

  - 4-status FSM: INITIAL_TRANSITION → IN_PROGRESS → FINAL_TRANSITION
    → RETURN_TO_PROGRAM_ORIGINAL.
  - Deadline-based arbitration: a more-serious EV (smaller deadline) preempts
    the holder by force-cutting it to FINAL_TRANSITION. No anti-flicker.
  - Safe-guard proportion: if the holder is past
    ``SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA`` of the Euclidean distance to
    the TLS, it is not preemptable.
  - No pending queue (losers are dropped; they may re-request next tick).
  - No spillback awareness, no drain mechanism.
  - No visual overlay.
"""
import math
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from ....core.config import Settings
from ....core.sumo_interface import SumoInterface
from ....domain.schemas import GreenWaveAllocationView
from ...emergency_manager import EmergencyManager
from .base import TrafficControlStrategy


@dataclass
class _LegacyAllocation:
    tls_id: str
    veh_emergency_id: str
    severity: str
    deadline: float
    original_tl_program: str
    controlled_lanes: List[str]
    controlled_edges: Set[str]
    first_edge_on_route_to_reach_tls_id: str
    status: str  # 'INITIAL_TRANSITION' | 'IN_PROGRESS' | 'FINAL_TRANSITION' | 'RETURN_TO_PROGRAM_ORIGINAL'
    change_transition: bool
    time_limit: float
    arrival_position: Tuple[float, float]
    starting_position: Tuple[float, float]
    ryg_state: Optional[str] = None
    next_edges: List[str] = field(default_factory=list)


class LegacyGreenWaveStrategy(TrafficControlStrategy):
    def __init__(
        self,
        settings: Settings,
        sumo: SumoInterface,
        emergency_manager: EmergencyManager,
    ):
        self.settings = settings
        self.sumo = sumo
        self.emergency_manager = emergency_manager
        self._allocations: List[_LegacyAllocation] = []

    # -------- public API --------

    def improve(self) -> None:
        self._green_wave_logic()

        evs_sorted = sorted(
            self.emergency_manager.buffer_emergency_vehicles,
            key=lambda ev: ev.deadline,
        )
        for ev in evs_sorted:
            try:
                next_tls_set = self.sumo.vehicle_get_next_tls(ev.veh_emergency_id)
            except self.sumo.TraCIException:
                continue

            for tls in next_tls_set:
                tls_id = tls[0]
                vehicle_distance_to_tls = tls[2]
                if vehicle_distance_to_tls > self.settings.VEHICLE_DISTANCE_TO_TLS:
                    continue
                if not self._is_tls_allocated_to_a_more_serious_emergency_vehicle(
                    tls_id=tls_id,
                    veh_emergency_id=ev.veh_emergency_id,
                    severity=ev.severity,
                    deadline=ev.deadline,
                ):
                    self._store_green_wave(tls_id, ev.veh_emergency_id, ev.severity, ev.deadline)

    def active_allocations(self) -> List[GreenWaveAllocationView]:
        return [
            GreenWaveAllocationView(
                tls_id=a.tls_id,
                requester_id=a.veh_emergency_id,
                priority_value=a.deadline,
                severity=a.severity,
                phase=a.status,
            )
            for a in self._allocations
        ]

    # -------- store allocation --------

    def _store_green_wave(
        self,
        tls_id: str,
        veh_emergency_id: str,
        severity: str,
        deadline: float,
        status: str = "INITIAL_TRANSITION",
    ) -> None:
        next_edges_sorted = self._get_next_edges(veh_emergency_id)
        try:
            controlled_lanes = self.sumo.trafficlight_get_controlled_lanes(tls_id)
        except self.sumo.TraCIException:
            return
        controlled_edges = {lane.split("_")[0] for lane in controlled_lanes}

        first_edge_on_route: Optional[str] = None
        for edge in next_edges_sorted:
            if edge in controlled_edges:
                first_edge_on_route = edge
                break
        if first_edge_on_route is None:
            return

        try:
            original_tl_program = self.sumo.trafficlight_get_program(tls_id)
            arrival_position = self.sumo.junction_get_position(tls_id)
            starting_position = self.sumo.vehicle_get_position(veh_emergency_id)
        except self.sumo.TraCIException:
            return

        self._allocations.append(
            _LegacyAllocation(
                tls_id=tls_id,
                veh_emergency_id=veh_emergency_id,
                severity=severity,
                deadline=deadline,
                original_tl_program=original_tl_program,
                controlled_lanes=controlled_lanes,
                controlled_edges=controlled_edges,
                first_edge_on_route_to_reach_tls_id=first_edge_on_route,
                status=status,
                change_transition=False,
                time_limit=self.sumo.get_time(),
                arrival_position=arrival_position,
                starting_position=starting_position,
                next_edges=next_edges_sorted,
            )
        )

    # -------- per-tick FSM driver --------

    def _green_wave_logic(self) -> None:
        if not self._allocations:
            return

        for key in range(len(self._allocations) - 1, -1, -1):
            self._monitor_time_to_change_transition(key)
            self._vehicle_passed_tls_green_wave(key)

            if key >= len(self._allocations):
                continue

            if not self._allocations[key].change_transition:
                status = self._allocations[key].status
                if status == "INITIAL_TRANSITION":
                    self._green_wave_initial_transition(key)
                elif status == "IN_PROGRESS":
                    self._green_wave_in_progress(key)
                elif status == "FINAL_TRANSITION":
                    self._green_wave_final_transition(key)
                elif status == "RETURN_TO_PROGRAM_ORIGINAL":
                    self._remove_tls_on_green_wave(key)

    def _monitor_time_to_change_transition(self, key: int) -> None:
        item = self._allocations[key]
        if item.change_transition and item.time_limit < self.sumo.get_time():
            if item.status == "INITIAL_TRANSITION":
                item.status = "IN_PROGRESS"
                item.change_transition = False
            elif item.status == "IN_PROGRESS":
                item.status = "FINAL_TRANSITION"
                item.change_transition = False
            elif item.status == "FINAL_TRANSITION":
                item.status = "RETURN_TO_PROGRAM_ORIGINAL"
                item.change_transition = False

    def _green_wave_initial_transition(self, key: int) -> None:
        item = self._allocations[key]
        try:
            tls_state = self.sumo.trafficlight_get_red_yellow_green_state(item.tls_id)
        except self.sumo.TraCIException:
            return
        first_edge = item.first_edge_on_route_to_reach_tls_id
        ryg_state = ""
        for index, lane in enumerate(item.controlled_lanes):
            lane_state = tls_state[index]
            if first_edge in lane and lane_state in ("g", "G"):
                ryg_state += "G"
            else:
                ryg_state += lane_state
        try:
            self.sumo.trafficlight_set_red_yellow_green_state(item.tls_id, ryg_state)
        except self.sumo.TraCIException:
            return
        item.ryg_state = ryg_state
        item.change_transition = True
        item.time_limit = self.sumo.get_time() + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT

    def _green_wave_in_progress(self, key: int) -> None:
        item = self._allocations[key]
        first_edge = item.first_edge_on_route_to_reach_tls_id
        ryg_state = "".join(
            "G" if first_edge in lane else "r" for lane in item.controlled_lanes
        )
        try:
            self.sumo.trafficlight_set_red_yellow_green_state(item.tls_id, ryg_state)
        except self.sumo.TraCIException:
            return
        item.ryg_state = ryg_state

    def _green_wave_final_transition(self, key: int) -> None:
        item = self._allocations[key]
        try:
            tls_state = self.sumo.trafficlight_get_red_yellow_green_state(item.tls_id)
        except self.sumo.TraCIException:
            return
        ryg_state = ""
        for index, _lane in enumerate(item.controlled_lanes):
            lane_state = tls_state[index]
            if lane_state in ("g", "G"):
                ryg_state += "y"
            else:
                ryg_state += lane_state
        try:
            self.sumo.trafficlight_set_red_yellow_green_state(item.tls_id, ryg_state)
        except self.sumo.TraCIException:
            return
        item.ryg_state = ryg_state
        item.change_transition = True
        item.time_limit = self.sumo.get_time() + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT

    # -------- arbitration --------

    def _is_tls_allocated_to_a_more_serious_emergency_vehicle(
        self, tls_id: str, veh_emergency_id: str, severity: str, deadline: float
    ) -> bool:
        for key, alloc in enumerate(self._allocations):
            if alloc.tls_id != tls_id:
                continue
            if alloc.veh_emergency_id == veh_emergency_id:
                return True
            if (
                self._proportion_to_conclude_green_wave(key)
                >= self.settings.SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA
            ):
                return True
            if alloc.deadline < deadline:
                return True
            if alloc.status in ("IN_PROGRESS", "INITIAL_TRANSITION"):
                self._allocations[key].status = "FINAL_TRANSITION"
            return True
        return False

    # -------- exit conditions --------

    def _vehicle_passed_tls_green_wave(self, key: int) -> None:
        item = self._allocations[key]
        if item.status != "IN_PROGRESS":
            return
        try:
            next_tls_set = self.sumo.vehicle_get_next_tls(item.veh_emergency_id)
            if not any(
                tls[0] == item.tls_id
                and tls[2] <= self.settings.VEHICLE_DISTANCE_TO_TLS
                for tls in next_tls_set
            ):
                item.change_transition = True
        except self.sumo.TraCIException:
            item.change_transition = True

    def _remove_tls_on_green_wave(self, key: int) -> None:
        item = self._allocations[key]
        try:
            self.sumo.trafficlight_set_program(item.tls_id, item.original_tl_program)
        except self.sumo.TraCIException:
            pass
        self._allocations.pop(key)
        print(
            f"{self.sumo.get_time()} - Emergency Vehicle {item.veh_emergency_id} "
            f"has left TLS {item.tls_id} (legacy)"
        )

    # -------- helpers --------

    def _get_next_edges(self, veh_id: str) -> List[str]:
        try:
            route = self.sumo.vehicle_get_route(veh_id)
            route_index = self.sumo.vehicle_get_route_index(veh_id)
        except self.sumo.TraCIException:
            return []
        route_index = max(route_index, 0)
        return route[route_index:]

    def _proportion_to_conclude_green_wave(self, key: int) -> float:
        item = self._allocations[key]
        x1, y1 = item.starting_position
        x2, y2 = item.arrival_position
        try:
            x3, y3 = self.sumo.vehicle_get_position(item.veh_emergency_id)
        except self.sumo.TraCIException:
            return 1.0  # vehicle gone: treat as completed

        euclidian_distance_arrival = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        euclidian_distance_current = math.sqrt((x3 - x1) ** 2 + (y3 - y1) ** 2)
        if euclidian_distance_arrival == 0:
            return 1.0
        return euclidian_distance_current / euclidian_distance_arrival
