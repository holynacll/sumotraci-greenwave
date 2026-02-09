try:
    import traci
except ImportError:
    traci = None

from ..core.config import Settings
from ..domain.enums import StatusEnum
from .accident_manager import AccidentManager


class EmergencyManager:
    def __init__(self, settings: Settings, accident_manager: AccidentManager):
        self.settings = settings
        self.accident_manager = accident_manager

    def monitor_emergency_vehicles(self):
        self.scan_schedule_to_dispatch_emergency_vehicle()
        self.monitor_change_lane_accidented_vehicle()
        self.monitor_emergency_vehicles_on_the_way()
        self.monitor_emergency_vehicles_in_the_accident()
        self.monitor_emergency_vehicles_to_the_hospital()

    def call_emergency_vehicle(self):
        # Checks if there are any accidents
        if not self.settings.buffer_vehicles_accidenteds:
            return

        # Check if there are accidents without emergency vehicle assigned
        vehicle_to_help = any(
            veh['veh_emergency_id'] is None
            for veh in self.settings.buffer_vehicles_accidenteds
        )

        if not vehicle_to_help:
            return

        # Schedule emergency vehicle for the most severe/urgent accident
        accident = self.find_most_severe_recent_accident()
        if accident is not None:
            self.schedule_emergency_vehicle(accident=accident)

    def schedule_emergency_vehicle(self, accident):
        veh_accidented_id = accident['veh_accidented_id']
        veh_emergency_id = f"veh_emergency_{traci.simulation.getTime()}"

        # Update buffer with assigned emergency vehicle ID
        for veh_accidented in self.settings.buffer_vehicles_accidenteds:
            if veh_accidented['veh_accidented_id'] == veh_accidented_id:
                veh_accidented['veh_emergency_id'] = veh_emergency_id
                accident['veh_emergency_id'] = veh_emergency_id # Update local reference too
                break

        self.create_dispatch_emergency_vehicle(accident=accident)

    def create_dispatch_emergency_vehicle(self, accident):
        veh_accidented_id = accident['veh_accidented_id']
        veh_emergency_id = accident['veh_emergency_id']
        self.settings.buffer_schedule_to_dispatch_emergency_vehicle.append({
            'accident': accident,
            'time': traci.simulation.getTime() + self.settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE,
        })
        print(
            f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} '
            f'has been scheduled to help vehicle {veh_accidented_id}'
        )

    def scan_schedule_to_dispatch_emergency_vehicle(self):
        for key in range(len(self.settings.buffer_schedule_to_dispatch_emergency_vehicle) - 1, -1, -1):
            schedule = self.settings.buffer_schedule_to_dispatch_emergency_vehicle[key]
            if schedule['time'] <= traci.simulation.getTime():
                accident = schedule['accident']
                self.settings.buffer_schedule_to_dispatch_emergency_vehicle.pop(key)
                self.dispatch_emergency_vehicle(accident=accident)

    def dispatch_emergency_vehicle(self, accident):
        emergency_route_id = f"rou_emergency_{traci.simulation.getTime()}"
        veh_emergency_id = accident['veh_emergency_id']
        veh_accidented_id = accident['veh_accidented_id']
        accidented_road_id = accident['accidented_road_id']
        deadline = accident['deadline']
        severity = accident['severity']

        try:
            arrival_pos = traci.vehicle.getLanePosition(veh_accidented_id)
        except traci.TraCIException:
            # Vehicle might have disappeared/teleported, reschedule or handle error
            # Original logic was to reschedule, but if vehicle is gone this might loop.
            # Assuming reschedule is desired behavior as per original code.
            self.create_dispatch_emergency_vehicle(accident=accident)
            return

        route_to_accident = traci.simulation.findRoute(
            fromEdge=self.settings.HOSPITAL_POS_START,
            toEdge=accidented_road_id,
        )
        route_from_accident_to_hospital = traci.simulation.findRoute(
            fromEdge=accidented_road_id,
            toEdge=self.settings.HOSPITAL_POS_END,
        )

        # Combine routes
        route_1_edges_tuple = route_to_accident.edges
        route_2_edges_tuple = route_from_accident_to_hospital.edges[1:] # Skip first edge to avoid duplication
        complete_edge_list = route_1_edges_tuple + route_2_edges_tuple

        traci.route.add(routeID=emergency_route_id, edges=complete_edge_list)

        traci.vehicle.add(
            vehID=veh_emergency_id,
            routeID=emergency_route_id,
            typeID="emergency_emergency",
            depart='now',
            departLane='best',
            departPos='base',
            departSpeed='0',
            arrivalLane='current',
            arrivalPos='max',
            arrivalSpeed='current'
        )

        self.settings.buffer_emergency_vehicles.append({
            'veh_accidented_id': veh_accidented_id,
            'veh_emergency_id': veh_emergency_id,
            'accidented_road_id': accidented_road_id,
            'severity': severity,
            'deadline': deadline,
            'arrival_pos': arrival_pos,
            'hospital_pos_start': self.settings.HOSPITAL_POS_START,
            'hospital_pos_end': self.settings.HOSPITAL_POS_END,
            'status': StatusEnum.ON_THE_WAY.value,
            'duration': self.settings.MAX_STOP_DURATION,
            'departure_time': traci.simulation.getTime(),
            'time_arrival': None,
            'vehicle_removed': False,
        })
        print(
            f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has been dispatched to help vehicle '
            f'{veh_accidented_id} in road {accidented_road_id} with severity {severity}'
        )

    def find_most_severe_recent_accident(self):
        # Filter accidents without emergency vehicle
        filtered_accidents = [
            accident for accident in self.settings.buffer_vehicles_accidenteds
            if accident['veh_emergency_id'] is None
        ]

        if not filtered_accidents:
            return None

        # Sort by deadline (Earliest Deadline First)
        filtered_accidents.sort(key=lambda x: (x['deadline']))

        return filtered_accidents[0]

    def monitor_change_lane_accidented_vehicle(self):
        for _, accidented_vehicle in enumerate(self.settings.buffer_vehicles_accidenteds):
            veh_accidented_id = accidented_vehicle['veh_accidented_id']
            lane_accidented_id = accidented_vehicle['lane_accidented_id']
            try:
                vehicle_follower_obj = traci.vehicle.getFollower(veh_accidented_id, 10.0)
            except traci.TraCIException:
                self.accident_manager.remove_vehicle_from_accident(veh_accidented_id)
                continue

            if not vehicle_follower_obj:
                continue

            vehicle_follower_id = vehicle_follower_obj[0]
            vehicle_follower_distance = vehicle_follower_obj[1]

            if not vehicle_follower_id:
                continue

            if -0.01 < vehicle_follower_distance <= 10.0:
                actual_lane = traci.vehicle.getLaneID(vehicle_follower_id)
                if lane_accidented_id == actual_lane:
                    lane_index = int(lane_accidented_id.split('_')[1])
                    lanes_count = traci.edge.getLaneNumber(traci.vehicle.getRoadID(vehicle_follower_id))

                    new_lane_index = None
                    for offset in [-1, 1]:
                        temp_lane_index = lane_index + offset
                        if 0 <= temp_lane_index < lanes_count:
                            if traci.vehicle.wantsAndCouldChangeLane(vehicle_follower_id, offset):
                                new_lane_index = temp_lane_index
                                break

                    if new_lane_index is not None:
                        traci.vehicle.changeLane(vehicle_follower_id, new_lane_index, 5.0)
                        print(
                            f'{traci.simulation.getTime()} - Vehicle {vehicle_follower_id} '
                            f'has changed lane to {new_lane_index}'
                        )
                    else:
                        traci.vehicle.slowDown(
                            vehicle_follower_id,
                            0.5 * traci.vehicle.getAllowedSpeed(vehicle_follower_id),
                            5.0
                        )

    def monitor_emergency_vehicles_to_the_hospital(self):
        for key in range(len(self.settings.buffer_emergency_vehicles) -1, -1, -1):
            emergency_vehicle = self.settings.buffer_emergency_vehicles[key]
            veh_emergency_id = emergency_vehicle['veh_emergency_id']
            hospital_pos_end = emergency_vehicle['hospital_pos_end']
            status = emergency_vehicle['status']

            if status == StatusEnum.TO_THE_HOSPITAL.value:
                try:
                    actual_road = traci.vehicle.getRoadID(veh_emergency_id)
                except traci.TraCIException:
                    self.settings.buffer_emergency_vehicles.pop(key)
                    actual_road = None

                if actual_road == hospital_pos_end:
                    deadline = emergency_vehicle['deadline']
                    if self._is_deadline_alive(deadline):
                        self.settings.count_saveds += 1
                    self.settings.buffer_emergency_vehicles.pop(key)
                    print(
                        f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} '
                        f'has arrived at the hospital'
                    )

    def monitor_emergency_vehicles_in_the_accident(self):
        for key in range(len(self.settings.buffer_emergency_vehicles) -1, -1, -1):
            emergency_vehicle = self.settings.buffer_emergency_vehicles[key]
            veh_emergency_id = emergency_vehicle['veh_emergency_id']
            veh_accidented_id = emergency_vehicle['veh_accidented_id']
            status = emergency_vehicle['status']

            if status == StatusEnum.IN_THE_ACCIDENT.value:
                self.settings.buffer_emergency_vehicles[key]['status'] = StatusEnum.TO_THE_HOSPITAL.value
                self.accident_manager.remove_vehicle_from_accident(veh_accidented_id)
                print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has left the accident')

    def monitor_emergency_vehicles_on_the_way(self):
        for key in range(len(self.settings.buffer_emergency_vehicles) -1, -1, -1):
            emergency_vehicle = self.settings.buffer_emergency_vehicles[key]
            veh_emergency_id = emergency_vehicle['veh_emergency_id']
            accidented_road_id = emergency_vehicle['accidented_road_id']
            arrival_pos = emergency_vehicle['arrival_pos']
            status = emergency_vehicle['status']

            if status == StatusEnum.ON_THE_WAY.value:
                try:
                    actual_road = traci.vehicle.getRoadID(veh_emergency_id)
                except traci.TraCIException:
                    self.settings.buffer_emergency_vehicles.pop(key)
                    actual_road = None

                if actual_road == accidented_road_id:
                    distance = traci.vehicle.getDrivingDistance(veh_emergency_id, actual_road, arrival_pos)
                    # Check if close enough
                    if distance < self.settings.MIN_ARRIVAL_DISTANCE_EMERGENCY_VEHICLE_AT_THE_ACCIDENT:
                        self.settings.buffer_emergency_vehicles[key]['status'] = StatusEnum.IN_THE_ACCIDENT.value
                        print(
                            f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} '
                            f'has arrived at the accident'
                        )

    def _is_deadline_alive(self, estimated_deadline: float) -> bool:
        print(f'Deadline: {estimated_deadline} - Actual Time: {traci.simulation.getTime()}')
        return estimated_deadline >= traci.simulation.getTime()
