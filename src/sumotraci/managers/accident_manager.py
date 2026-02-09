import random
from typing import List

from ..core.config import Settings
from ..core.sumo_interface import SumoInterface
from ..domain.enums import SeverityEnum
from ..domain.schemas import Accident, RoadFreezed


class AccidentManager:
    def __init__(self, settings: Settings, sumo: SumoInterface):
        self.settings = settings
        self.sumo = sumo
        self.counter_tries_to_create = 0
        self.counter_assign_random_severity = 0
        self.last_roads_accidenteds: List[str] = []

        # State
        self.vehicles_accidenteds: List[Accident] = []
        self.roads_freezed_to_new_accidents: List[RoadFreezed] = []
        self.count_accidents: int = 0
        self.time_for_next_accident: float = 0.0

        # Generated Positions
        self.hospital_pos_start: str = ""
        self.hospital_pos_end: str = ""
        self.eligible_accidented_roads: List[str] = []

    def assign_random_severity(self) -> str:
        self.counter_assign_random_severity += 1
        random.seed(self.settings.SEED)
        severity_values = list(SeverityEnum)
        # Replicating original logic of shuffling and picking based on counter
        sample_severity_values = [severity.value for severity in random.sample(severity_values, len(severity_values))]
        return sample_severity_values[(self.counter_assign_random_severity - 1) % len(severity_values)]

    def create_accident(self) -> None:
        # Check time for next accident
        if self.sumo.get_time() < self.time_for_next_accident:
            return

        self.counter_tries_to_create += 1

        # Check limit of accidents
        if len(self.vehicles_accidenteds) >= self.settings.MAX_ELIGIBLE_ACCIDENTED_ROADS:
           return

        if not self.eligible_accidented_roads:
             return

        for _ in range(len(self.eligible_accidented_roads)):
            # Pick a road based on tries counter
            accidented_road_id = self.eligible_accidented_roads[
                (self.counter_tries_to_create - 1) % len(self.eligible_accidented_roads)
            ]

            if self._accidented_road_is_already_accidented(accidented_road_id):
                continue

            vehicle_ids = self.sumo.edge_get_last_step_vehicle_ids(edge_id=accidented_road_id)
            for vehicle_id in vehicle_ids:
                if not self._vehicle_is_in_a_valid_position_lane(vehicle_id):
                    continue

                veh_type_id = self.sumo.vehicle_get_type_id(vehicle_id)
                if veh_type_id == 'emergency_emergency':
                    continue

                if self._vehicle_is_already_considered(vehicle_id):
                    continue

                if self._road_is_freezed_to_new_accidents(accidented_road_id):
                    continue

                self._add_vehicle_to_accident(vehicle_id, accidented_road_id)
                return None

    def _vehicle_is_in_a_valid_position_lane(self, veh_id: str) -> bool:
        position = self.sumo.vehicle_get_lane_position(veh_id)
        return (position > 0.2 * self.settings.LANE_LENGTH) and (position < 0.4 * self.settings.LANE_LENGTH)

    def _accidented_road_is_already_accidented(self, road_id: str) -> bool:
        return any(v.accidented_road_id == road_id for v in self.vehicles_accidenteds)

    def _road_is_freezed_to_new_accidents(self, road_id: str) -> bool:
        current_time = self.sumo.get_time()
        return any(
            rf.road_id == road_id and current_time < rf.time
            for rf in self.roads_freezed_to_new_accidents
        )

    def _vehicle_is_already_considered(self, veh_id: str) -> bool:
        return any(v.veh_accidented_id == veh_id for v in self.vehicles_accidenteds)

    def _add_vehicle_to_accident(self, veh_id: str, road_id: str) -> None:
        severity = self.assign_random_severity()
        color_highlight = self.settings.SEVERITY_COLORS[SeverityEnum(severity)]
        speed_road_accidented = self.settings.SEVERITY_SPEED_ROAD_ACCIDENTED[SeverityEnum(severity)]
        deadline = self.settings.SEVERITY_GOLDEN_TIME[SeverityEnum(severity)] + self.sumo.get_time()

        self.sumo.edge_set_max_speed(road_id, speed_road_accidented)
        self.sumo.vehicle_slow_down(veh_id, 0.2 * self.sumo.vehicle_get_allowed_speed(veh_id), 10.0)

        try:
            self.sumo.vehicle_set_stop(
                veh_id,
                edge_id=road_id,
                pos=self.sumo.vehicle_get_lane_position(veh_id) + (0.1 * self.settings.LANE_LENGTH),
                lane_index=self.sumo.vehicle_get_lane_index(veh_id),
                duration=self.settings.ACCIDENT_DURATION
            )
        except Exception:
            return

        self.sumo.vehicle_highlight(veh_id, color_highlight)

        self.vehicles_accidenteds.append(
            Accident(
                veh_accidented_id=veh_id,
                accidented_road_id=road_id,
                lane_accidented_id=self.sumo.vehicle_get_lane_id(veh_id),
                severity=severity,
                time_accident=self.sumo.get_time(),
                deadline=deadline,
                time_recovered=None,
                veh_emergency_id=None,
            )
        )
        self.count_accidents += 1
        self.time_for_next_accident = (
            self.sumo.get_time() + self.settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
        )
        print(
            f'{self.sumo.get_time()} - Vehicle {veh_id} '
            f'has been accidented in road {road_id} with severity {severity}'
        )

    def remove_vehicle_from_accident(self, veh_id: str) -> None:
        for key in range(len(self.vehicles_accidenteds) - 1, -1, -1):
            if self.vehicles_accidenteds[key].veh_accidented_id == veh_id:
                accidented_road_id = self.vehicles_accidenteds[key].accidented_road_id

                self.roads_freezed_to_new_accidents.append(
                    RoadFreezed(
                        road_id=accidented_road_id,
                        time=self.sumo.get_time() + self.settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
                    )
                )

                self.vehicles_accidenteds.pop(key)
                self._speed_road_recovery(accidented_road_id)
                try:
                    self.sumo.vehicle_remove(veh_id)
                except self.sumo.TraCIException:
                    pass
                print(f'{self.sumo.get_time()} - Vehicle {veh_id} has been removed from the accident')
                return None

    def _speed_road_recovery(self, road_id: str) -> None:
        self.sumo.edge_set_max_speed(road_id, self.settings.SPEED_ROAD)
        print(f'{self.sumo.get_time()} - Road {road_id} has been recovered')

    def generate_elegible_accidented_roads_and_hospital_positions(self) -> None:
        random.seed(self.settings.SEED)
        road_ids: List[str] = self.sumo.edge_get_id_list()
        possible_road_ids = sorted(list(
            set([road_id for road_id in road_ids if not road_id.startswith(':') and len(road_id) == 4])
        ))

        if len(possible_road_ids) < 2:
            print("Not enough roads to generate hospitals and accidents.")
            return

        hospital_positions = random.sample(possible_road_ids, 2)
        self.hospital_pos_start = hospital_positions[0]
        self.hospital_pos_end = hospital_positions[1]

        possible_accidented_road_ids = sorted(list(
            set(possible_road_ids) - set([self.hospital_pos_start, self.hospital_pos_end])
        ))

        # Ensure we don't try to sample more than available
        k = min(self.settings.MAX_ELIGIBLE_ACCIDENTED_ROADS, len(possible_accidented_road_ids))
        self.eligible_accidented_roads = random.sample(possible_accidented_road_ids, k)

        print(f"Eligible accidented roads: {self.eligible_accidented_roads}")
        print(f"Hospital positions: {self.hospital_pos_start} - {self.hospital_pos_end}")
