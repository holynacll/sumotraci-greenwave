import math
from typing import List

from ..core.config import Settings
from ..core.sumo_interface import SumoInterface
from ..domain.schemas import GreenWaveTLS
from .emergency_manager import EmergencyManager


class TrafficManager:
    def __init__(self, settings: Settings, sumo: SumoInterface, emergency_manager: EmergencyManager):
        self.settings = settings
        self.sumo = sumo
        self.emergency_manager = emergency_manager

        # State
        self.buffer_tls_on_green_wave: list[GreenWaveTLS] = []

    def improve_traffic_for_emergency_vehicle(self) -> None:
        self._green_wave_logic()

        # Sort emergency vehicles by deadline
        emergency_vehicles_sorted = sorted(
            self.emergency_manager.buffer_emergency_vehicles,
            key=lambda x: (x.deadline)
        )

        for emergency_vehicle in emergency_vehicles_sorted:
            veh_emergency_id = emergency_vehicle.veh_emergency_id
            severity = emergency_vehicle.severity
            deadline = emergency_vehicle.deadline

            try:
                next_tls_set = self.sumo.vehicle_get_next_tls(veh_emergency_id)
            except self.sumo.TraCIException:
                continue

            for tls in next_tls_set:
                tls_id = tls[0]
                vehicle_distance_to_tls = tls[2]

                if vehicle_distance_to_tls <= self.settings.VEHICLE_DISTANCE_TO_TLS:
                    if not self._is_tls_allocated_to_a_more_serious_emergency_vehicle(
                        tls_id=tls_id,
                        veh_emergency_id=veh_emergency_id,
                        severity=severity,
                        deadline=deadline,
                    ):
                        print(
                            f'{self.sumo.get_time()} - Emergency Vehicle {veh_emergency_id} '
                            f'has reached TLS {tls_id}'
                        )
                        self._store_green_wave(tls_id, veh_emergency_id, severity, deadline)

    def improve_traffic_on_accidented_road(self) -> None:
        if not self.emergency_manager.buffer_emergency_vehicles:
            return

        vehicles = self.sumo.vehicle_get_id_list()

        for emergency_vehicle in self.emergency_manager.buffer_emergency_vehicles:
            accidented_road_id = emergency_vehicle.accidented_road_id

            for veh_id in vehicles:
                try:
                    type_id = self.sumo.vehicle_get_type_id(veh_id)
                except self.sumo.TraCIException:
                    continue

                if type_id != 'emergency_emergency':
                    next_roads_list = self.sumo.vehicle_get_route(veh_id)
                    if accidented_road_id in next_roads_list:
                        try:
                            current_travel_time = self.sumo.edge_get_travel_time(accidented_road_id)
                            self.sumo.edge_adapt_travel_time(accidented_road_id, current_travel_time)

                            self.sumo.vehicle_reroute_traveltime(veh_id)

                            # Coloring for debug
                            if next_roads_list[-1] == accidented_road_id:
                                self.sumo.vehicle_set_color(veh_id, (0, 100, 100))
                            elif next_roads_list[0] == accidented_road_id:
                                self.sumo.vehicle_set_color(veh_id, (100, 0, 100))
                            else:
                                self.sumo.vehicle_set_color(veh_id, (0, 255, 0))
                        except self.sumo.TraCIException:
                            pass

    def _store_green_wave(
        self, tls_id: str, veh_emergency_id: str, severity: str, deadline: float, status: str = 'INITIAL_TRANSITION'
    ) -> None:
        print(
            f'{self.sumo.get_time()} - Emergency Vehicle {veh_emergency_id} '
            f'has reached TLS {tls_id} - status: {status} - and going to store green wave.'
        )
        next_edges_sorted = self._get_next_edges(veh_emergency_id)
        controlled_lanes = self.sumo.trafficlight_get_controlled_lanes(tls_id)
        controlled_edges = {lane.split('_')[0] for lane in controlled_lanes}

        first_edge_on_route = None
        for edge in next_edges_sorted:
            if edge in controlled_edges:
                first_edge_on_route = edge
                break

        if first_edge_on_route is not None:
            self.buffer_tls_on_green_wave.append(
                GreenWaveTLS(
                    tls_id=tls_id,
                    veh_emergency_id=veh_emergency_id,
                    severity=severity,
                    deadline=deadline,
                    original_tl_program=self.sumo.trafficlight_get_program(tls_id),
                    ryg_state=None,
                    status=status,
                    controlled_lanes=controlled_lanes,
                    controlled_edges=controlled_edges,
                    next_edges=next_edges_sorted,
                    first_edge_on_route_to_reach_tls_id=first_edge_on_route,
                    change_transition=False,
                    time_limit=self.sumo.get_time(),
                    arrival_position=self.sumo.junction_get_position(tls_id),
                    starting_position=self.sumo.vehicle_get_position(veh_emergency_id),
                )
            )

    def _green_wave_logic(self) -> None:
        if not self.buffer_tls_on_green_wave:
            return

        for key in range(len(self.buffer_tls_on_green_wave) - 1, -1, -1):
            self._monitor_time_to_change_transition(key)
            self._vehicle_passed_tls_green_wave(key)

            if key >= len(self.buffer_tls_on_green_wave):
                continue

            if not self.buffer_tls_on_green_wave[key].change_transition:
                status = self.buffer_tls_on_green_wave[key].status
                if status == 'INITIAL_TRANSITION':
                    self._green_wave_initial_transition(key)
                elif status == 'IN_PROGRESS':
                    self._green_wave_in_progress(key)
                elif status == 'FINAL_TRANSITION':
                    self._green_wave_final_transition(key)
                elif status == 'RETURN_TO_PROGRAM_ORIGINAL':
                    self._green_wave_return_to_program_original(key)

    def _monitor_time_to_change_transition(self, key: int) -> None:
        item = self.buffer_tls_on_green_wave[key]
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
        item = self.buffer_tls_on_green_wave[key]
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
        item = self.buffer_tls_on_green_wave[key]
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
        item = self.buffer_tls_on_green_wave[key]
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

    def _is_tls_allocated_to_a_more_serious_emergency_vehicle(
        self, tls_id: str, veh_emergency_id: str, severity: str, deadline: float
    ) -> bool:
        for key, tls_on_green_wave in enumerate(self.buffer_tls_on_green_wave):
            if tls_on_green_wave.tls_id == tls_id:
                if tls_on_green_wave.veh_emergency_id == veh_emergency_id:
                    return True

                if (
                    self._proportion_to_conclude_green_wave(key) >=
                    self.settings.SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA
                ):
                    return True

                if tls_on_green_wave.deadline < deadline:
                    return True

                if tls_on_green_wave.status in ('IN_PROGRESS', 'INITIAL_TRANSITION'):
                    self.buffer_tls_on_green_wave[key].status = 'FINAL_TRANSITION'
                return True
        return False

    def _vehicle_passed_tls_green_wave(self, key: int) -> None:
        item = self.buffer_tls_on_green_wave[key]
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

    def _get_next_edges(self, veh_id: str) -> List[str]:
        route = self.sumo.vehicle_get_route(veh_id)
        route_index = self.sumo.vehicle_get_route_index(veh_id)
        route_index = max(route_index, 0)
        return route[route_index:]

    def _remove_tls_on_green_wave(self, key: int) -> None:
        tls_on_green_wave = self.buffer_tls_on_green_wave[key]
        veh_emergency_id = tls_on_green_wave.veh_emergency_id
        tls_id = tls_on_green_wave.tls_id
        original_tl_program = tls_on_green_wave.original_tl_program
        self.sumo.trafficlight_set_program(tls_id, original_tl_program)
        self.buffer_tls_on_green_wave.pop(key)
        print(f'{self.sumo.get_time()} - Emergency Vehicle {veh_emergency_id} has left TLS {tls_id}')

    def _proportion_to_conclude_green_wave(self, key: int) -> float:
        item = self.buffer_tls_on_green_wave[key]
        x1, y1 = item.starting_position
        x2, y2 = item.arrival_position
        try:
            x3, y3 = self.sumo.vehicle_get_position(item.veh_emergency_id)
        except self.sumo.TraCIException:
            return 1.0 # Assume completed if vehicle gone

        euclidian_distance_arrival = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        euclidian_distance_current = math.sqrt((x3 - x1)**2 + (y3 - y1)**2)

        if euclidian_distance_arrival == 0:
            return 1.0

        return euclidian_distance_current / euclidian_distance_arrival
