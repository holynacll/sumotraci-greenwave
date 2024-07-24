import random
from config import (
    traci,
    settings,
)


def assign_random_severity():
    settings.counter_assign_random_severity += 1
    random.seed(settings.SEED)
    severity_values = list(settings.SeverityEnum)
    sample_severity_values = [severity.value for severity in random.sample(severity_values, len(severity_values))]
    print(sample_severity_values)
    return sample_severity_values[(settings.counter_assign_random_severity - 1) % len(severity_values)]


def add_counter_accidents():
    settings.count_accidents += 1


def add_counter_tries_to_create():
    settings.counter_tries_to_create += 1


def create_accident():   
    # se o tempo de bloqueio de criar acidentes for maior que o tempo de simulação, então não cria acidente
    if traci.simulation.getTime() < settings.TIME_FOR_NEXT_ACCIDENT:
        return
    
    add_counter_tries_to_create()

    # se já atingiu o limite de acidentes, então não cria mais acidentes
    if len(settings.buffer_vehicles_accidenteds) >= len(settings.ELIGIBLE_ACCIDENTED_ROADS):
        return

    for _ in range(len(settings.ELIGIBLE_ACCIDENTED_ROADS)):
        accidented_road_id: str = settings.ELIGIBLE_ACCIDENTED_ROADS[(settings.counter_tries_to_create - 1) % len(settings.ELIGIBLE_ACCIDENTED_ROADS)]

        # se a via já está acidentada, então escolhe próxima via elegível
        if accidented_road_is_already_accidented(accidented_road_id=accidented_road_id):
            continue

        vehicle_ids = traci.edge.getLastStepVehicleIDs(edgeID=accidented_road_id)
        for vehicle_id in vehicle_ids:
            # se veículo está em uma posição válida na faixa, longe dos cruzamentos
            if not vehicle_is_in_a_valid_position_lane(vehicle_id):
                continue

            # se veículo escolhido foi um veículo de emergência
            veh_accidented_type_id = traci.vehicle.getTypeID(vehicle_id)
            if veh_accidented_type_id == 'emergency_emergency':
                continue

            # se veículo escolhido foi um já acidentado
            if vehicle_is_already_considered(veh_accidented_id=vehicle_id):
                continue
            
            # se a via está congelada para novos acidentes
            if road_is_freezed_to_new_accidents(accidented_road_id):
                continue

            add_vehicle_to_accident(vehicle_id, accidented_road_id)
            return None


def vehicle_is_in_a_valid_position_lane(veh_accidented_id):
    position = traci.vehicle.getLanePosition(veh_accidented_id)
    return position > 0.2 * settings.LANE_LENGTH and position < 0.4 * settings.LANE_LENGTH


def accidented_road_is_already_accidented(accidented_road_id):
    return (
        any(veh_accidented['accidented_road_id'] == accidented_road_id
        for veh_accidented in settings.buffer_vehicles_accidenteds)
    )


def road_is_freezed_to_new_accidents(accidented_road_id):
    return (
        any(
            road_freezed.road_id == accidented_road_id
            and traci.simulation.getTime() < road_freezed.time
            for road_freezed in settings.buffer_roads_freezed_to_new_accidents
        )
    )

def vehicle_is_already_considered(veh_accidented_id):
    return (
        any(veh_accidented['veh_accidented_id'] == veh_accidented_id
        for veh_accidented in settings.buffer_vehicles_accidenteds)
    )

def road_is_one_of_the_last_accidentds(accidented_road_id):
    return accidented_road_id in settings.last_roads_accidenteds

def add_vehicle_to_accident(veh_accidented_id, accidented_road_id):
    severity = assign_random_severity()
    color_highlight = settings.severity_colors[severity]
    speed_road_accidented = settings.severity_speed_road_accidented[severity]
    deadline = settings.severity_gonden_time[severity] + traci.simulation.getTime()
    traci.edge.setMaxSpeed(accidented_road_id, speed_road_accidented)
    # traci.vehicle.setSpeed(veh_accidented_id, 0)
    traci.vehicle.slowDown(veh_accidented_id, 0.2 * traci.vehicle.getAllowedSpeed(veh_accidented_id), 10.0)
    try:
        traci.vehicle.setStop(
            veh_accidented_id, 
            edgeID=accidented_road_id,
            pos=traci.vehicle.getLanePosition(veh_accidented_id) + (0.1 * settings.LANE_LENGTH),
            laneIndex=traci.vehicle.getLaneIndex(veh_accidented_id),
            duration=settings.ACCIDENT_DURATION
        )
    except:
        return
    traci.vehicle.highlight(veh_accidented_id, color_highlight)
    settings.buffer_vehicles_accidenteds.append(
        {
            'veh_accidented_id': veh_accidented_id,
            'accidented_road_id': accidented_road_id,
            'lane_accidented_id': traci.vehicle.getLaneID(veh_accidented_id),
            'severity': severity,
            'time_accident': traci.simulation.getTime(),
            'deadline': deadline,
            'time_recovered': None,
            'veh_emergency_id': None,
        }
    )
    add_counter_accidents()
    settings.TIME_FOR_NEXT_ACCIDENT = traci.simulation.getTime() + settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
    print(f'{traci.simulation.getTime()} - Vehicle {veh_accidented_id} has been accidented in road {accidented_road_id} with severity {severity}')


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
            # severity = settings.buffer_vehicles_accidenteds[key]['severity']
            # time_accident = settings.buffer_vehicles_accidenteds[key]['time_accident']
            # if settings.buffer_vehicles_accidenteds[key]['time_recovered'] is None:
            settings.buffer_vehicles_accidenteds.pop(key)
            speed_road_recovery(accidented_road_id=accidented_road_id)
            try:
                traci.vehicle.remove(veh_accidented_id)
            except traci.TraCIException:
                pass
            print(f'{traci.simulation.getTime()} - Vehicle {veh_accidented_id} has been removed from the accident')
            return None


def is_deadline_alive(estimated_deadline: float):
    # verifica se passou do tempo de deadline
    # return traci.simulation.getTime() - time_accident < deadline
    print(f'Deadline: {estimated_deadline} - Actual Time: {traci.simulation.getTime()}')
    if estimated_deadline < traci.simulation.getTime():
        return False
    return True


def speed_road_recovery(accidented_road_id):
    traci.edge.setMaxSpeed(accidented_road_id, settings.SPEED_ROAD)
    print(f'{traci.simulation.getTime()} - Road {accidented_road_id} has been recovered')


def generate_elegible_accidented_roads_and_hospital_positions():
    random.seed(settings.SEED)
    road_ids: list[str] = traci.edge.getIDList()
    possible_road_ids = sorted(list(
        set([road_id for road_id in road_ids if not road_id.startswith(':') and len(road_id) == 4])
    ))
    hospital_positions = random.sample(possible_road_ids, 2)
    settings.HOSPITAL_POS_START = hospital_positions[0]
    settings.HOSPITAL_POS_END = hospital_positions[1]
    
    possible_accidented_road_ids = sorted(list(set(possible_road_ids) - set([settings.HOSPITAL_POS_START, settings.HOSPITAL_POS_END])))
    settings.ELIGIBLE_ACCIDENTED_ROADS = random.sample(possible_accidented_road_ids, settings.MAX_ELIGIBLE_ACCIDENTED_ROADS)
    print(f"Eligible accidented roads: {settings.ELIGIBLE_ACCIDENTED_ROADS}")
    print(f"Hospital positions: {settings.HOSPITAL_POS_START} - {settings.HOSPITAL_POS_END}")
