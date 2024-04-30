from config import (
    traci,
    settings,
)
from emergency_call import scan_schedule_to_dispatch_emergency_vehicle
from optimization_green_wave import remove_remaining_tls_on_green_wave

def speed_road_recovery(accidented_road_id):
    can_increase_max_speed = True
    for emergency_vehicle in  settings.buffer_emergency_vehicles:
        # se existe algum acidente em andamento
        if (
            emergency_vehicle['accidented_road_id'] == accidented_road_id and
            (
                emergency_vehicle['status'] == settings.StatusEnum.ON_THE_WAY.value or
                emergency_vehicle['status'] == settings.StatusEnum.IN_THE_ACCIDENT.value
            )
        ):
            can_increase_max_speed = False
    if can_increase_max_speed:
        traci.edge.setMaxSpeed(accidented_road_id, settings.MAX_SPEED_ROAD_RECOVERED)
        print(f'{traci.simulation.getTime()} - Road {accidented_road_id} has been recovered')


def remove_vehicle_from_accident(veh_accidented_id):
    for key in range(len(settings.buffer_vehicles_accidenteds) - 1, -1, -1):
        if settings.buffer_vehicles_accidenteds[key]['veh_accidented_id'] == veh_accidented_id:
            settings.buffer_vehicles_accidenteds.pop(key)
            traci.vehicle.remove(veh_accidented_id)
            break
    print(f'{traci.simulation.getTime()} - Vehicle {veh_accidented_id} has been removed from the accident')


def monitor_emergency_vehicles():
    scan_schedule_to_dispatch_emergency_vehicle()
    monitor_accidented_vehicle()
    monitor_emergency_vehicles_on_the_way()
    monitor_emergency_vehicles_in_the_accident()
    monitor_emergency_vehicles_to_the_hospital()


def monitor_accidented_vehicle():
    for key, accidented_vehicle in enumerate(settings.buffer_vehicles_accidenteds):
        veh_accidented_id = accidented_vehicle['veh_accidented_id']
        lane_accidented_id = accidented_vehicle['lane_accidented_id']
        # accidented_road_id = accidented_vehicle['accidented_road_id']
        # accidented_time = accidented_vehicle['accidented_time']
        vehicle_follower_obj = traci.vehicle.getFollower(veh_accidented_id, 3.0)
        vehicle_follower_id = vehicle_follower_obj[0]
        vehicle_follower_distance = vehicle_follower_obj[1]
        if vehicle_follower_distance > 0.0 and vehicle_follower_distance <= 3.0:
            actual_lane = traci.vehicle.getLaneID(vehicle_follower_id)
            if lane_accidented_id == actual_lane:
                # print(vehicle_follower_obj)
                lane_index = int(lane_accidented_id.split('_')[1])
                if lane_index == 0:
                    lane_index = 1
                else:
                    lane_index = 0
                traci.vehicle.changeLane(vehicle_follower_id, lane_index, 3.0)
                # print(f'{traci.simulation.getTime()} - Vehicle {veh_accidented_id} - follower {vehicle_follower_id} - lane {lane_accidented_id}')
        # duration = accidented_vehicle['duration']
        # if duration > 0:
        #     duration -= 1
        #     settings.buffer_vehicles_accidenteds[key]['duration'] = duration
        # else:
        #     remove_vehicle_from_accident(veh_accidented_id)
        #     speed_road_recovery(accidented_road_id)
        #     settings.buffer_vehicles_accidenteds.pop(key)
        #     print(f'{traci.simulation.getTime()} - Vehicle {veh_accidented_id} has been removed from the accident')


def monitor_emergency_vehicles_to_the_hospital():
    for key in range(len(settings.buffer_emergency_vehicles) -1, -1, -1):
        emergency_vehicle = settings.buffer_emergency_vehicles[key]
        veh_emergency_id = emergency_vehicle['veh_emergency_id']
        hospital_pos_end = emergency_vehicle['hospital_pos_end']
        status = emergency_vehicle['status']
        if status == settings.StatusEnum.TO_THE_HOSPITAL.value:
            actual_road = traci.vehicle.getRoadID(veh_emergency_id)
            if actual_road == hospital_pos_end:
                settings.buffer_emergency_vehicles.pop(key)
                # traci.vehicle.remove(veh_emergency_id)
                remove_remaining_tls_on_green_wave(veh_emergency_id, [])
                # # remove tls alocados para esse veículo de emergência
                # for key in range(len(settings.buffer_tls_on_green_wave) - 1, -1, -1):
                #     tls_on_green_wave = settings.buffer_tls_on_green_wave[key]
                #     if tls_on_green_wave['veh_emergency_id'] == veh_emergency_id:
                #         traci.trafficlight.setProgram(tls_on_green_wave['tls_id'], tls_on_green_wave['original_tl_program'])
                #         settings.buffer_tls_on_green_wave.pop(key)
                print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has arrived at the hospital')


def monitor_emergency_vehicles_in_the_accident():
    for key, emergency_vehicle in enumerate(settings.buffer_emergency_vehicles):
        veh_emergency_id = emergency_vehicle['veh_emergency_id']
        hospital_pos_end = emergency_vehicle['hospital_pos_end']
        veh_accidented_id = emergency_vehicle['veh_accidented_id']
        accidented_road_id = emergency_vehicle['accidented_road_id']
        duration = emergency_vehicle['duration']
        status = emergency_vehicle['status']
        if status == settings.StatusEnum.IN_THE_ACCIDENT.value:
            if duration > 0:
                duration -= 1
                settings.buffer_emergency_vehicles[key]['duration'] = duration
            else:
                remove_vehicle_from_accident(veh_accidented_id)
                # traci.vehicle.changeTarget(veh_emergency_id, hospital_pos_end)
                settings.buffer_emergency_vehicles[key]['status'] = settings.StatusEnum.TO_THE_HOSPITAL.value
                speed_road_recovery(accidented_road_id)
                # traci.vehicle.setSpeed(veh_emergency_id, -1)
                # traci.vehicle.setAcceleration(veh_emergency_id, 50, 0)
                # traci.vehicle.setSpeedMode(veh_emergency_id, 0)
                print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has left the accident')


def monitor_emergency_vehicles_on_the_way():
    for key, emergency_vehicle in enumerate(settings.buffer_emergency_vehicles):
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
                if  distance < settings.MIN_ARRIVAL_DISTANCE_EMERGENCY_VEHICLE_AT_THE_ACCIDENT:
                    # stop emergency vehicle for some duration
                    # traci.vehicle.setStop(vehID=veh_emergency_id, edgeID=actual_road, laneIndex=1, pos=arrival_pos, duration=settings.MAX_STOP_DURATION)
                    # traci.vehicle.setSpeedMode(veh_emergency_id, 31)
                    # traci.vehicle.setSpeed(veh_emergency_id, 0)
                    # traci.vehicle.setAcceleration(vehID=veh_emergency_id, acceleration=0, duration=settings.MAX_STOP_DURATION)
                    settings.buffer_emergency_vehicles[key]['status'] = settings.StatusEnum.IN_THE_ACCIDENT.value
                    print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has arrived at the accident')
