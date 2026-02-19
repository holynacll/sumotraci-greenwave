from typing import List, Set

from ...core.config import Settings
from ...core.sumo_interface import SumoInterface
from ...domain.schemas import GreenWaveTLS


class GreenWaveManager:
    """
    Base strategy for Green Wave implementation.
    Currently implements the Standard Green Wave logic.
    """
    def __init__(self, settings: Settings, sumo: SumoInterface):
        self.settings = settings
        self.sumo = sumo
        self.active_green_waves: List[GreenWaveTLS] = []

    def apply_green_wave(
        self,
        tls_id: str,
        veh_emergency_id: str,
        severity: str,
        deadline: float,
        current_status: str,
        controlled_lanes: List[str],
        controlled_edges: Set[str],
        next_edges: List[str],
        first_edge_on_route: str
    ) -> None:
        """
        Register or update a Green Wave allocation.
        """
        # Check if already exists and update/preempt if necessary
        existing_index = self._find_allocation_index(tls_id)

        if existing_index != -1:
            # Preemption or Update
            # If we are here, EDF check passed, so we overwrite.
            # If it was a different vehicle, we might want to log preemption.
            self.active_green_waves.pop(existing_index)

        self.active_green_waves.append(
            GreenWaveTLS(
                tls_id=tls_id,
                veh_emergency_id=veh_emergency_id,
                severity=severity,
                deadline=deadline,
                original_tl_program=self.sumo.trafficlight_get_program(tls_id),
                ryg_state=None,
                status=current_status, # Likely 'INITIAL_TRANSITION'
                controlled_lanes=controlled_lanes,
                controlled_edges=controlled_edges,
                next_edges=next_edges,
                first_edge_on_route_to_reach_tls_id=first_edge_on_route,
                change_transition=False,
                time_limit=self.sumo.get_time(),
                arrival_position=self.sumo.junction_get_position(tls_id),
                starting_position=self.sumo.vehicle_get_position(veh_emergency_id),
            )
        )

    def update(self) -> None:
        """
        Main loop to update state of all active green waves.
        """
        if not self.active_green_waves:
            return

        # Iterate backwards to allow safe removal
        for key in range(len(self.active_green_waves) - 1, -1, -1):
            self._monitor_time_to_change_transition(key)
            self._vehicle_passed_tls_green_wave(key)

            if key >= len(self.active_green_waves):
                continue

            if not self.active_green_waves[key].change_transition:
                status = self.active_green_waves[key].status
                if status == 'INITIAL_TRANSITION':
                    self._green_wave_initial_transition(key)
                elif status == 'IN_PROGRESS':
                    self._green_wave_in_progress(key)
                elif status == 'FINAL_TRANSITION':
                    self._green_wave_final_transition(key)
                elif status == 'RETURN_TO_PROGRAM_ORIGINAL':
                    self._green_wave_return_to_program_original(key)

    def _find_allocation_index(self, tls_id: str) -> int:
        for i, gw in enumerate(self.active_green_waves):
            if gw.tls_id == tls_id:
                return i
        return -1

    def _monitor_time_to_change_transition(self, key: int) -> None:
        item = self.active_green_waves[key]
        if item.change_transition and item.time_limit < self.sumo.get_time():
            if item.status == 'INITIAL_TRANSITION':
                item.status = 'IN_PROGRESS'
                item.change_transition = False
            elif item.status == 'IN_PROGRESS':
                item.status = 'FINAL_TRANSITION'
                item.change_transition = False
            elif item.status == 'FINAL_TRANSITION':
                item.status = 'RETURN_TO_PROGRAM_ORIGINAL'
                item.change_transition = False

    def _green_wave_initial_transition(self, key: int) -> None:
        item = self.active_green_waves[key]
        tls_id = item.tls_id
        controlled_lanes = item.controlled_lanes
        first_edge = item.first_edge_on_route_to_reach_tls_id

        tls_state = self.sumo.trafficlight_get_red_yellow_green_state(tls_id)
        ryg_state = ''

        for index, lane in enumerate(controlled_lanes):
            lane_state = tls_state[index]
            if first_edge in lane and lane_state in ('g', 'G'):
                ryg_state += 'G'
            else:
                ryg_state += lane_state

        self.sumo.trafficlight_set_red_yellow_green_state(tls_id, ryg_state)
        item.ryg_state = ryg_state
        item.change_transition = True
        item.time_limit = self.sumo.get_time() + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT

    def _green_wave_in_progress(self, key: int) -> None:
        item = self.active_green_waves[key]
        tls_id = item.tls_id
        controlled_lanes = item.controlled_lanes
        first_edge = item.first_edge_on_route_to_reach_tls_id

        ryg_state = ''
        for lane in controlled_lanes:
            if first_edge in lane:
                ryg_state += 'G'
            else:
                ryg_state += 'r'

        self.sumo.trafficlight_set_red_yellow_green_state(tls_id, ryg_state)
        item.ryg_state = ryg_state

    def _green_wave_final_transition(self, key: int) -> None:
        item = self.active_green_waves[key]
        tls_id = item.tls_id
        controlled_lanes = item.controlled_lanes

        tls_state = self.sumo.trafficlight_get_red_yellow_green_state(tls_id)
        ryg_state = ''
        for index, lane in enumerate(controlled_lanes):
            lane_state = tls_state[index]
            if lane_state in ('g', 'G'):
                ryg_state += 'y'
            else:
                ryg_state += lane_state

        self.sumo.trafficlight_set_red_yellow_green_state(tls_id, ryg_state)
        item.ryg_state = ryg_state
        item.change_transition = True
        item.time_limit = self.sumo.get_time() + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT

    def _green_wave_return_to_program_original(self, key: int) -> None:
        self._remove_tls_on_green_wave(key)

    def _vehicle_passed_tls_green_wave(self, key: int) -> None:
        item = self.active_green_waves[key]
        if item.status == 'IN_PROGRESS':
            try:
                next_tls_set = self.sumo.vehicle_get_next_tls(item.veh_emergency_id)
                if not any(
                    tls[0] == item.tls_id and tls[2] <= self.settings.VEHICLE_DISTANCE_TO_TLS
                    for tls in next_tls_set
                ):
                    item.change_transition = True
            except self.sumo.TraCIException:
                # Vehicle might be gone
                item.change_transition = True

    def _remove_tls_on_green_wave(self, key: int) -> None:
        tls_on_green_wave = self.active_green_waves[key]
        veh_emergency_id = tls_on_green_wave.veh_emergency_id
        tls_id = tls_on_green_wave.tls_id
        original_tl_program = tls_on_green_wave.original_tl_program
        self.sumo.trafficlight_set_program(tls_id, original_tl_program)
        self.active_green_waves.pop(key)
        print(f'{self.sumo.get_time()} - Emergency Vehicle {veh_emergency_id} has left TLS {tls_id}')
