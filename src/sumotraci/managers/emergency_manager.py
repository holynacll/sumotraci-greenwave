from ..core.config import Settings
from ..core.sumo_interface import SumoInterface
from ..domain.enums import StatusEnum
from ..domain.schemas import Accident, EmergencyDispatchSchedule, EmergencyVehicle
from .accident_manager import AccidentManager


class EmergencyManager:
    def __init__(
        self, settings: Settings, accident_manager: AccidentManager, sumo: SumoInterface
    ):
        self.settings = settings
        self.accident_manager = accident_manager
        self.sumo = sumo

        # State
        self.buffer_schedule_to_dispatch_emergency_vehicle: list[
            EmergencyDispatchSchedule
        ] = []
        self.buffer_emergency_vehicles: list[EmergencyVehicle] = []
        self.count_saveds: int = 0

    def monitor_emergency_vehicles(self) -> None:
        self.scan_schedule_to_dispatch_emergency_vehicle()
        self.monitor_change_lane_accidented_vehicle()
        self.monitor_emergency_vehicles_on_the_way()
        self.monitor_emergency_vehicles_in_the_accident()
        self.monitor_emergency_vehicles_to_the_hospital()

    def call_emergency_vehicle(self) -> None:
        # Checks if there are any accidents
        if not self.accident_manager.vehicles_accidenteds:
            return

        # Check if there are accidents without emergency vehicle assigned
        vehicle_to_help = any(
            veh.veh_emergency_id is None
            for veh in self.accident_manager.vehicles_accidenteds
        )

        if not vehicle_to_help:
            return

        # Schedule emergency vehicle for the most severe/urgent accident
        accident = self.find_most_severe_recent_accident()
        if accident is not None:
            self.schedule_emergency_vehicle(accident=accident)

    def schedule_emergency_vehicle(self, accident: Accident) -> None:
        veh_accidented_id = accident.veh_accidented_id
        veh_emergency_id = f"veh_emergency_{self.sumo.get_time()}"

        # Update buffer with assigned emergency vehicle ID (in AccidentManager)
        for veh_accidented in self.accident_manager.vehicles_accidenteds:
            if veh_accidented.veh_accidented_id == veh_accidented_id:
                veh_accidented.veh_emergency_id = veh_emergency_id
                accident.veh_emergency_id = (
                    veh_emergency_id  # Update local reference too
                )
                break

        self.create_dispatch_emergency_vehicle(accident=accident)

    def create_dispatch_emergency_vehicle(self, accident: Accident) -> None:
        veh_accidented_id = accident.veh_accidented_id
        # We need to handle the case where veh_emergency_id might be None, but logically it should be set by now
        veh_emergency_id = accident.veh_emergency_id
        self.buffer_schedule_to_dispatch_emergency_vehicle.append(
            EmergencyDispatchSchedule(
                accident=accident,
                time=self.sumo.get_time()
                + self.settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE,
            )
        )
        print(
            f"{self.sumo.get_time()} - Emergency Vehicle {veh_emergency_id} "
            f"has been scheduled to help vehicle {veh_accidented_id}"
        )

    def scan_schedule_to_dispatch_emergency_vehicle(self) -> None:
        for key in range(
            len(self.buffer_schedule_to_dispatch_emergency_vehicle) - 1, -1, -1
        ):
            schedule = self.buffer_schedule_to_dispatch_emergency_vehicle[key]
            if schedule.time <= self.sumo.get_time():
                accident = schedule.accident
                self.buffer_schedule_to_dispatch_emergency_vehicle.pop(key)
                self.dispatch_emergency_vehicle(accident=accident)

    def dispatch_emergency_vehicle(self, accident: Accident) -> None:
        emergency_route_id = f"rou_emergency_{self.sumo.get_time()}"
        veh_emergency_id = accident.veh_emergency_id
        veh_accidented_id = accident.veh_accidented_id
        accidented_road_id = accident.accidented_road_id
        deadline = accident.deadline
        severity = accident.severity
        if veh_emergency_id is None:
            # Should not happen if logic is correct, but for safety
            return

        try:
            arrival_pos = self.sumo.vehicle_get_lane_position(veh_accidented_id)
        except self.sumo.TraCIException:
            # Vehicle might have disappeared/teleported, reschedule or handle error
            self.create_dispatch_emergency_vehicle(accident=accident)
            return

        route_to_accident = self.sumo.find_route(
            from_edge=self.accident_manager.hospital_pos_start,
            to_edge=accidented_road_id,
        )
        route_from_accident_to_hospital = self.sumo.find_route(
            from_edge=accidented_road_id,
            to_edge=self.accident_manager.hospital_pos_end,
        )

        # Combine routes
        route_1_edges_tuple = route_to_accident.edges
        route_2_edges_tuple = route_from_accident_to_hospital.edges[
            1:
        ]  # Skip first edge to avoid duplication
        complete_edge_list = list(route_1_edges_tuple + route_2_edges_tuple)

        self.sumo.route_add(route_id=emergency_route_id, edges=complete_edge_list)

        self.sumo.vehicle_add(
            veh_id=veh_emergency_id,
            route_id=emergency_route_id,
            type_id="emergency_emergency",
        )

        self.buffer_emergency_vehicles.append(
            EmergencyVehicle(
                veh_accidented_id=veh_accidented_id,
                veh_emergency_id=veh_emergency_id,
                accidented_road_id=accidented_road_id,
                severity=severity,
                deadline=deadline,
                arrival_pos=arrival_pos,
                hospital_pos_start=self.accident_manager.hospital_pos_start,
                hospital_pos_end=self.accident_manager.hospital_pos_end,
                status=StatusEnum.ON_THE_WAY.value,
                duration=self.settings.MAX_STOP_DURATION,
                departure_time=self.sumo.get_time(),
                time_arrival=None,
                vehicle_removed=False,
            )
        )
        print(
            f"{self.sumo.get_time()} - Emergency Vehicle {veh_emergency_id} has been dispatched to help vehicle "
            f"{veh_accidented_id} in road {accidented_road_id} with severity {severity}"
        )

    def find_most_severe_recent_accident(self) -> Accident | None:
        # Filter accidents without emergency vehicle
        filtered_accidents = [
            accident
            for accident in self.accident_manager.vehicles_accidenteds
            if accident.veh_emergency_id is None
        ]

        if not filtered_accidents:
            return None

        # Sort by deadline (Earliest Deadline First)
        filtered_accidents.sort(key=lambda x: x.deadline)

        return filtered_accidents[0]

    def monitor_change_lane_accidented_vehicle(self) -> None:
        for _, accidented_vehicle in enumerate(
            self.accident_manager.vehicles_accidenteds
        ):
            veh_accidented_id = accidented_vehicle.veh_accidented_id
            lane_accidented_id = accidented_vehicle.lane_accidented_id
            try:
                vehicle_follower_obj = self.sumo.vehicle_get_follower(
                    veh_accidented_id, 10.0
                )
            except self.sumo.TraCIException:
                self.accident_manager.remove_vehicle_from_accident(veh_accidented_id)
                continue

            if not vehicle_follower_obj:
                continue

            vehicle_follower_id = vehicle_follower_obj[0]
            vehicle_follower_distance = vehicle_follower_obj[1]

            if not vehicle_follower_id:
                continue

            if -0.01 < vehicle_follower_distance <= 10.0:
                actual_lane = self.sumo.vehicle_get_lane_id(vehicle_follower_id)
                if lane_accidented_id == actual_lane:
                    lane_index = int(lane_accidented_id.split("_")[1])
                    lanes_count = self.sumo.edge_get_lane_number(
                        self.sumo.vehicle_get_road_id(vehicle_follower_id)
                    )

                    new_lane_index = None
                    for offset in [-1, 1]:
                        temp_lane_index = lane_index + offset
                        if 0 <= temp_lane_index < lanes_count:
                            if self.sumo.vehicle_wants_and_could_change_lane(
                                vehicle_follower_id, offset
                            ):
                                new_lane_index = temp_lane_index
                                break

                    if new_lane_index is not None:
                        self.sumo.vehicle_change_lane(
                            vehicle_follower_id, new_lane_index, 5.0
                        )
                        print(
                            f"{self.sumo.get_time()} - Vehicle {vehicle_follower_id} "
                            f"has changed lane to {new_lane_index}"
                        )
                    else:
                        self.sumo.vehicle_slow_down(
                            vehicle_follower_id,
                            0.5
                            * self.sumo.vehicle_get_allowed_speed(vehicle_follower_id),
                            5.0,
                        )

    def monitor_emergency_vehicles_to_the_hospital(self) -> None:
        for key in range(len(self.buffer_emergency_vehicles) - 1, -1, -1):
            emergency_vehicle = self.buffer_emergency_vehicles[key]
            veh_emergency_id = emergency_vehicle.veh_emergency_id
            veh_accidented_id = emergency_vehicle.veh_accidented_id
            hospital_pos_end = emergency_vehicle.hospital_pos_end
            status = emergency_vehicle.status

            if status == StatusEnum.TO_THE_HOSPITAL.value:
                try:
                    actual_road = self.sumo.vehicle_get_road_id(veh_emergency_id)
                except self.sumo.TraCIException:
                    self.buffer_emergency_vehicles.pop(key)
                    self.accident_manager.remove_vehicle_from_accident(
                        veh_accidented_id
                    )
                    actual_road = None

                if actual_road == hospital_pos_end:
                    deadline = emergency_vehicle.deadline
                    if self._is_deadline_alive(deadline):
                        self.count_saveds += 1
                    self.buffer_emergency_vehicles.pop(key)
                    print(
                        f"{self.sumo.get_time()} - Emergency Vehicle {veh_emergency_id} "
                        f"has arrived at the hospital"
                    )

    def monitor_emergency_vehicles_in_the_accident(self) -> None:
        for key in range(len(self.buffer_emergency_vehicles) - 1, -1, -1):
            emergency_vehicle = self.buffer_emergency_vehicles[key]
            veh_emergency_id = emergency_vehicle.veh_emergency_id
            veh_accidented_id = emergency_vehicle.veh_accidented_id
            status = emergency_vehicle.status

            if status == StatusEnum.IN_THE_ACCIDENT.value:
                self.buffer_emergency_vehicles[
                    key
                ].status = StatusEnum.TO_THE_HOSPITAL.value
                self.accident_manager.remove_vehicle_from_accident(veh_accidented_id)
                print(
                    f"{self.sumo.get_time()} - Emergency Vehicle {veh_emergency_id} has left the accident"
                )

    def monitor_emergency_vehicles_on_the_way(self) -> None:
        for key in range(len(self.buffer_emergency_vehicles) - 1, -1, -1):
            emergency_vehicle = self.buffer_emergency_vehicles[key]
            veh_emergency_id = emergency_vehicle.veh_emergency_id
            veh_accidented_id = emergency_vehicle.veh_accidented_id
            accidented_road_id = emergency_vehicle.accidented_road_id
            arrival_pos = emergency_vehicle.arrival_pos
            status = emergency_vehicle.status

            if status == StatusEnum.ON_THE_WAY.value:
                try:
                    actual_road = self.sumo.vehicle_get_road_id(veh_emergency_id)
                except self.sumo.TraCIException:
                    self.buffer_emergency_vehicles.pop(key)
                    self.accident_manager.remove_vehicle_from_accident(
                        veh_accidented_id
                    )
                    actual_road = None

                if actual_road == accidented_road_id:
                    distance = self.sumo.vehicle_get_driving_distance(
                        veh_emergency_id, actual_road, arrival_pos
                    )
                    # Check if close enough
                    if (
                        distance
                        < self.settings.MIN_ARRIVAL_DISTANCE_EMERGENCY_VEHICLE_AT_THE_ACCIDENT
                    ):
                        self.buffer_emergency_vehicles[
                            key
                        ].status = StatusEnum.IN_THE_ACCIDENT.value
                        print(
                            f"{self.sumo.get_time()} - Emergency Vehicle {veh_emergency_id} "
                            f"has arrived at the accident"
                        )

    def _is_deadline_alive(self, estimated_deadline: float) -> bool:
        print(f"Deadline: {estimated_deadline} - Actual Time: {self.sumo.get_time()}")
        return estimated_deadline >= self.sumo.get_time()
