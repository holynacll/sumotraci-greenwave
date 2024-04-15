from config import (
    traci,
    settings,
)


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
        print("max speed road recovered")


def monitor_emergency_vehicles():
    monitor_emergency_vehicles_on_the_way()
    monitor_emergency_vehicles_in_the_accident()
    monitor_emergency_vehicles_to_the_hospital()


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
                # remove tls alocados para esse veículo de emergência
                for key in range(len(settings.buffer_tls_on_green_wave) - 1, -1, -1):
                    tls_on_green_wave = settings.buffer_tls_on_green_wave[key]
                    if tls_on_green_wave['veh_emergency_id'] == veh_emergency_id:
                        settings.buffer_tls_on_green_wave.pop(key)


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
                traci.vehicle.remove(veh_accidented_id)
                traci.vehicle.changeTarget(veh_emergency_id, hospital_pos_end)
                settings.buffer_emergency_vehicles[key]['status'] = settings.StatusEnum.TO_THE_HOSPITAL.value
                speed_road_recovery(accidented_road_id)
                traci.vehicle.setSpeed(veh_emergency_id, -1)
                # traci.vehicle.setSpeedMode(veh_emergency_id, 0)


def monitor_emergency_vehicles_on_the_way():
    for key, emergency_vehicle in enumerate(settings.buffer_emergency_vehicles):
        veh_emergency_id = emergency_vehicle['veh_emergency_id']
        accidented_road_id = emergency_vehicle['accidented_road_id']
        arrival_pos = emergency_vehicle['arrival_pos']
        status = emergency_vehicle['status']
        if status == settings.StatusEnum.ON_THE_WAY.value:
            actual_road = traci.vehicle.getRoadID(veh_emergency_id)
            if actual_road == accidented_road_id:
                distance = traci.vehicle.getDrivingDistance(veh_emergency_id, actual_road, arrival_pos)
                if  distance < settings.MIN_ARRIVAL_DISTANCE_EMERGENCY_VEHICLE_AT_THE_ACCIDENT:
                    # stop emergency vehicle for some duration
                    traci.vehicle.setSpeedMode(veh_emergency_id, 31)
                    traci.vehicle.setSpeed(veh_emergency_id, 0)
                    settings.buffer_emergency_vehicles[key]['status'] = settings.StatusEnum.IN_THE_ACCIDENT.value
