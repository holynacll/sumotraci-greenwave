from config import (
    traci,
    settings,
)
from emergency_call import scan_schedule_to_dispatch_emergency_vehicle


def speed_road_recovery(accidented_road_id):
    traci.edge.setMaxSpeed(accidented_road_id, settings.SPEED_ROAD)
    print(f'{traci.simulation.getTime()} - Road {accidented_road_id} has been recovered')


def remove_vehicle_from_accident(veh_accidented_id):
    for key in range(len(settings.buffer_vehicles_accidenteds) - 1, -1, -1):
        if settings.buffer_vehicles_accidenteds[key]['veh_accidented_id'] == veh_accidented_id:
            accidented_road_id = settings.buffer_vehicles_accidenteds[key]['accidented_road_id']
            settings.buffer_roads_freezed_to_new_accidents.append(
                settings.RoadsFreezedToNewAccidents(
                    road_id=accidented_road_id,
                    time=traci.simulation.getTime() + settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
                )
            )
            settings.buffer_vehicles_accidenteds.pop(key)
            speed_road_recovery(accidented_road_id=accidented_road_id)
            print(f'{traci.simulation.getTime()} - Vehicle {veh_accidented_id} has been removed from the accident')
            try:
                traci.vehicle.remove(veh_accidented_id)
                return True
            except traci.TraCIException:
                return False
    return False


def monitor_emergency_vehicles():
    scan_schedule_to_dispatch_emergency_vehicle()
    monitor_change_lane_accidented_vehicle()
    for key in range(len(settings.buffer_emergency_vehicles) -1, -1, -1):
        monitor_emergency_vehicles_on_the_way(key)
        monitor_emergency_vehicles_in_the_accident(key)
        monitor_emergency_vehicles_to_the_hospital(key)


def monitor_change_lane_accidented_vehicle():
    for _, accidented_vehicle in enumerate(settings.buffer_vehicles_accidenteds):
        veh_accidented_id = accidented_vehicle['veh_accidented_id']
        lane_accidented_id = accidented_vehicle['lane_accidented_id']
        try:
            vehicle_follower_obj = traci.vehicle.getFollower(veh_accidented_id, 10.0)
        except traci.TraCIException:
            remove_vehicle_from_accident(veh_accidented_id)
            continue
        vehicle_follower_id = vehicle_follower_obj[0]
        vehicle_follower_distance = vehicle_follower_obj[1]
        if vehicle_follower_distance > -0.01 and vehicle_follower_distance <= 10.0:
            actual_lane = traci.vehicle.getLaneID(vehicle_follower_id)
            if lane_accidented_id == actual_lane:
                lane_index = int(lane_accidented_id.split('_')[1])
                lanes_count = traci.edge.getLaneNumber(traci.vehicle.getRoadID(vehicle_follower_id))
                
                new_lane_index = None
                for offset in [-1, 1]:  # Check left lane first, then right lane
                    temp_lane_index = lane_index + offset
                    if 0 <= temp_lane_index < lanes_count:
                        if traci.vehicle.wantsAndCouldChangeLane(vehicle_follower_id, offset):
                            new_lane_index = temp_lane_index
                            break
                
                if new_lane_index is not None:
                    traci.vehicle.changeLane(vehicle_follower_id, new_lane_index, 5.0)  # Attempt lane change
                    print(f'{traci.simulation.getTime()} - Vehicle {vehicle_follower_id} has changed lane to {new_lane_index}')
                else:
                    # If no lane is available, reduce speed to avoid collision
                    traci.vehicle.slowDown(vehicle_follower_id, 0.5 * traci.vehicle.getAllowedSpeed(vehicle_follower_id), 5.0)

def monitor_emergency_vehicles_to_the_hospital(key):
    emergency_vehicle = settings.buffer_emergency_vehicles[key]
    veh_emergency_id = emergency_vehicle['veh_emergency_id']
    hospital_pos_end = emergency_vehicle['hospital_pos_end']
    status = emergency_vehicle['status']
    if status == settings.StatusEnum.TO_THE_HOSPITAL.value:
        actual_road = traci.vehicle.getRoadID(veh_emergency_id)
        if actual_road == hospital_pos_end:
            if settings.buffer_emergency_vehicles[key]['vehicle_removed']:
                settings.count_saveds += 1
            settings.buffer_emergency_vehicles.pop(key)
            print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has arrived at the hospital')


def monitor_emergency_vehicles_in_the_accident(key):
    emergency_vehicle = settings.buffer_emergency_vehicles[key]
    veh_emergency_id = emergency_vehicle['veh_emergency_id']
    veh_accidented_id = emergency_vehicle['veh_accidented_id']
    status = emergency_vehicle['status']
    if status == settings.StatusEnum.IN_THE_ACCIDENT.value:
        settings.buffer_emergency_vehicles[key]['status'] = settings.StatusEnum.TO_THE_HOSPITAL.value
        if remove_vehicle_from_accident(veh_accidented_id):
            settings.buffer_emergency_vehicles[key]['vehicle_removed'] = True
        print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has left the accident')


def monitor_emergency_vehicles_on_the_way(key):
    emergency_vehicle = settings.buffer_emergency_vehicles[key]
    veh_emergency_id = emergency_vehicle['veh_emergency_id']
    accidented_road_id = emergency_vehicle['accidented_road_id']
    arrival_pos = emergency_vehicle['arrival_pos']
    status = emergency_vehicle['status']
    if status == settings.StatusEnum.ON_THE_WAY.value:
        try:
            actual_road = traci.vehicle.getRoadID(veh_emergency_id)
        except traci.TraCIException:
            actual_road = None
        if actual_road == accidented_road_id:
            distance = traci.vehicle.getDrivingDistance(veh_emergency_id, actual_road, arrival_pos)
            if distance < settings.MIN_ARRIVAL_DISTANCE_EMERGENCY_VEHICLE_AT_THE_ACCIDENT:
                settings.buffer_emergency_vehicles[key]['status'] = settings.StatusEnum.IN_THE_ACCIDENT.value
                print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has arrived at the accident')
