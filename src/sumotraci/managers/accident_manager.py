import random
from typing import List

try:
    import traci
except ImportError:
    traci = None # Mock or handle gracefully during testing if needed

from ..core.config import Settings
from ..domain.enums import SeverityEnum


class AccidentManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.counter_tries_to_create = 0
        self.counter_assign_random_severity = 0
        self.last_roads_accidenteds = [] # Keep track if needed, though not fully used in original

    def assign_random_severity(self) -> str:
        self.counter_assign_random_severity += 1
        random.seed(self.settings.SEED)
        severity_values = list(SeverityEnum)
        # Replicating original logic of shuffling and picking based on counter
        sample_severity_values = [severity.value for severity in random.sample(severity_values, len(severity_values))]
        # print(sample_severity_values) # Removed print for cleaner output
        return sample_severity_values[(self.counter_assign_random_severity - 1) % len(severity_values)]

    def create_accident(self) -> None:
        # Check time for next accident
        if traci.simulation.getTime() < self.settings.TIME_FOR_NEXT_ACCIDENT:
            return

        self.counter_tries_to_create += 1

        # Check limit of accidents
        if len(self.settings.buffer_vehicles_accidenteds) >= self.settings.MAX_ELIGIBLE_ACCIDENTED_ROADS:
           # Note: Original code used len(ELIGIBLE_ACCIDENTED_ROADS) which might be dynamic or static.
           # Using dynamic check based on buffer size vs eligible limit
           return

        if not self.settings.ELIGIBLE_ACCIDENTED_ROADS:
             return

        for _ in range(len(self.settings.ELIGIBLE_ACCIDENTED_ROADS)):
            # Pick a road based on tries counter
            accidented_road_id = self.settings.ELIGIBLE_ACCIDENTED_ROADS[
                (self.counter_tries_to_create - 1) % len(self.settings.ELIGIBLE_ACCIDENTED_ROADS)
            ]

            if self._accidented_road_is_already_accidented(accidented_road_id):
                continue

            vehicle_ids = traci.edge.getLastStepVehicleIDs(edgeID=accidented_road_id)
            for vehicle_id in vehicle_ids:
                if not self._vehicle_is_in_a_valid_position_lane(vehicle_id):
                    continue

                veh_type_id = traci.vehicle.getTypeID(vehicle_id)
                if veh_type_id == 'emergency_emergency':
                    continue

                if self._vehicle_is_already_considered(vehicle_id):
                    continue

                if self._road_is_freezed_to_new_accidents(accidented_road_id):
                    continue

                self._add_vehicle_to_accident(vehicle_id, accidented_road_id)
                return None

    def _vehicle_is_in_a_valid_position_lane(self, veh_id: str) -> bool:
        position = traci.vehicle.getLanePosition(veh_id)
        return (position > 0.2 * self.settings.LANE_LENGTH) and (position < 0.4 * self.settings.LANE_LENGTH)

    def _accidented_road_is_already_accidented(self, road_id: str) -> bool:
        return any(v['accidented_road_id'] == road_id for v in self.settings.buffer_vehicles_accidenteds)

    def _road_is_freezed_to_new_accidents(self, road_id: str) -> bool:
        current_time = traci.simulation.getTime()
        return any(
            rf.road_id == road_id and current_time < rf.time
            for rf in self.settings.buffer_roads_freezed_to_new_accidents
        )

    def _vehicle_is_already_considered(self, veh_id: str) -> bool:
        return any(v['veh_accidented_id'] == veh_id for v in self.settings.buffer_vehicles_accidenteds)

    def _add_vehicle_to_accident(self, veh_id: str, road_id: str) -> None:
        severity = self.assign_random_severity()
        color_highlight = self.settings.SEVERITY_COLORS[severity]
        speed_road_accidented = self.settings.SEVERITY_SPEED_ROAD_ACCIDENTED[severity]
        deadline = self.settings.SEVERITY_GOLDEN_TIME[severity] + traci.simulation.getTime()

        traci.edge.setMaxSpeed(road_id, speed_road_accidented)
        traci.vehicle.slowDown(veh_id, 0.2 * traci.vehicle.getAllowedSpeed(veh_id), 10.0)

        try:
            traci.vehicle.setStop(
                veh_id,
                edgeID=road_id,
                pos=traci.vehicle.getLanePosition(veh_id) + (0.1 * self.settings.LANE_LENGTH),
                laneIndex=traci.vehicle.getLaneIndex(veh_id),
                duration=self.settings.ACCIDENT_DURATION
            )
        except Exception:
            return

        traci.vehicle.highlight(veh_id, color_highlight)

        self.settings.buffer_vehicles_accidenteds.append({
            'veh_accidented_id': veh_id,
            'accidented_road_id': road_id,
            'lane_accidented_id': traci.vehicle.getLaneID(veh_id),
            'severity': severity,
            'time_accident': traci.simulation.getTime(),
            'deadline': deadline,
            'time_recovered': None,
            'veh_emergency_id': None,
        })
        self.settings.count_accidents += 1
        self.settings.TIME_FOR_NEXT_ACCIDENT = (
            traci.simulation.getTime() + self.settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
        )
        print(
            f'{traci.simulation.getTime()} - Vehicle {veh_id} '
            f'has been accidented in road {road_id} with severity {severity}'
        )

    def remove_vehicle_from_accident(self, veh_id: str) -> None:
        for key in range(len(self.settings.buffer_vehicles_accidenteds) - 1, -1, -1):
            if self.settings.buffer_vehicles_accidenteds[key]['veh_accidented_id'] == veh_id:
                accidented_road_id = self.settings.buffer_vehicles_accidenteds[key]['accidented_road_id']

                # Freezing road logic
                # We need a struct for freezed roads.
                # In config it was a namedtuple, implementing as simple object or dict here?
                # Using the defined buffer in settings.
                from collections import namedtuple
                RoadsFreezed = namedtuple('RoadsFreezedToNewAccidents', ['road_id', 'time'])

                self.settings.buffer_roads_freezed_to_new_accidents.append(
                    RoadsFreezed(
                        road_id=accidented_road_id,
                        time=traci.simulation.getTime() + self.settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
                    )
                )

                self.settings.buffer_vehicles_accidenteds.pop(key)
                self._speed_road_recovery(accidented_road_id)
                try:
                    traci.vehicle.remove(veh_id)
                except traci.TraCIException:
                    pass
                print(f'{traci.simulation.getTime()} - Vehicle {veh_id} has been removed from the accident')
                return None

    def _speed_road_recovery(self, road_id: str) -> None:
        traci.edge.setMaxSpeed(road_id, self.settings.SPEED_ROAD)
        print(f'{traci.simulation.getTime()} - Road {road_id} has been recovered')

    def generate_elegible_accidented_roads_and_hospital_positions(self) -> None:
        random.seed(self.settings.SEED)
        road_ids: List[str] = traci.edge.getIDList()
        possible_road_ids = sorted(list(
            set([road_id for road_id in road_ids if not road_id.startswith(':') and len(road_id) == 4])
        ))

        if len(possible_road_ids) < 2:
            print("Not enough roads to generate hospitals and accidents.")
            return

        hospital_positions = random.sample(possible_road_ids, 2)
        self.settings.HOSPITAL_POS_START = hospital_positions[0]
        self.settings.HOSPITAL_POS_END = hospital_positions[1]

        possible_accidented_road_ids = sorted(list(
            set(possible_road_ids) - set([self.settings.HOSPITAL_POS_START, self.settings.HOSPITAL_POS_END])
        ))

        # Ensure we don't try to sample more than available
        k = min(self.settings.MAX_ELIGIBLE_ACCIDENTED_ROADS, len(possible_accidented_road_ids))
        self.settings.ELIGIBLE_ACCIDENTED_ROADS = random.sample(possible_accidented_road_ids, k)

        print(f"Eligible accidented roads: {self.settings.ELIGIBLE_ACCIDENTED_ROADS}")
        print(f"Hospital positions: {self.settings.HOSPITAL_POS_START} - {self.settings.HOSPITAL_POS_END}")
