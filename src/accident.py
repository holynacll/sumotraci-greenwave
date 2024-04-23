import random
from config import (
    traci,
    settings,
)

counter_accidents = 0
counter_tries_to_create = 0
sum_time_to_block_create_accidents = 0.0
counter_assign_random_severity = 0

def assign_random_severity():
    global counter_assign_random_severity
    counter_assign_random_severity += 1
    random.seed(settings.SEED)
    print(f'settings seed accident.py - {settings.SEED}')
    severity_values = list(settings.SeverityEnum)
    return [severity.value for severity in random.sample(severity_values, len(severity_values))][(counter_assign_random_severity - 1) % len(severity_values)]


def add_counter_accidents():
    global counter_accidents
    counter_accidents += 1


def add_counter_tries_to_create():
    global counter_tries_to_create
    counter_tries_to_create += 1


def create_accident():
    # se o tempo de bloqueio de criar acidentes for maior que o tempo de simulação, então não cria acidente
    global sum_time_to_block_create_accidents, counter_tries_to_create
    add_counter_tries_to_create()

    if traci.simulation.getTime() < sum_time_to_block_create_accidents:
        return

    # se já atingiu o limite de acidentes, então não cria mais acidentes
    if len(settings.buffer_vehicles_accidenteds) >= len(settings.ELIGIBLE_ACCIDENTED_ROADS):
        return

    for _ in range(len(settings.ELIGIBLE_ACCIDENTED_ROADS)):
        accidented_road_id: str = settings.ELIGIBLE_ACCIDENTED_ROADS[(counter_tries_to_create - 1) % len(settings.ELIGIBLE_ACCIDENTED_ROADS)]

    # for accidented_road_id in settings.ELIGIBLE_ACCIDENTED_ROADS:
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

            add_vehicle_to_accident(vehicle_id, accidented_road_id)
            sum_time_to_block_create_accidents = traci.simulation.getTime() + settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
            return None

            
    # accidented_road_id: str = settings.ELIGIBLE_ACCIDENTED_ROADS[counter_tries_to_create % len(settings.ELIGIBLE_ACCIDENTED_ROADS)]
    # # se veículo escolhido foi acidentado em uma via que já está acidentada, então escolhe outro veículo
    # if not accidented_road_is_already_accidented(accidented_road_id=accidented_road_id):
    #     vehicle_ids = traci.edge.getLastStepVehicleIDs(edgeID=accidented_road_id)
    #     for vehicle_id in vehicle_ids:
    #         print(vehicle_id)
    #         # se veículo está em uma posição válida na faixa, longe dos cruzamentos
    #         if not vehicle_is_in_a_valid_position_lane(vehicle_id):
    #             continue
            
    #         # se veículo escolhido foi um veículo de emergência
    #         veh_accidented_type_id = traci.vehicle.getTypeID(vehicle_id)
    #         if veh_accidented_type_id == 'emergency_emergency':
    #             continue
        
    #         # se veículo escolhido foi um já acidentado
    #         if not vehicle_is_already_considered(veh_accidented_id=vehicle_id):
    #             continue # Sai do loop se nenhuma das condições para continuar for verdadeira
            
    #         add_vehicle_to_accident(vehicle_id, accidented_road_id)
    #         return
    # add_counter_tries_to_create()
    # create_accident()


# def create_random_accident():
#     vehicles = traci.vehicle.getIDList()
#     while True:
#         # random.seed(42)
#         random_number = random.randrange(0, len(vehicles))
#         veh_accidented_id = vehicles[random_number]
#         accidented_road_id: str = traci.vehicle.getRoadID(veh_accidented_id)
        
#         # se veículo escolhido foi acidentado em uma via que já está acidentada, então escolhe outro veículo
#         if accidented_road_is_already_accidented(accidented_road_id=accidented_road_id):
#             continue

#         # se veículo escolhido está em uma junção interna da rede (não valida)
#         if accidented_road_id.startswith(':'):
#             continue
        
#         # se veículo está em uma posição válida na faixa, longe dos cruzamentos
#         if not vehicle_is_in_a_valid_position_lane(veh_accidented_id):
#             continue

#         # se veículo escolhido foi um veículo de emergência
#         veh_accidented_type_id = traci.vehicle.getTypeID(veh_accidented_id)
#         if veh_accidented_type_id == 'emergency_emergency':
#             continue

#         # se veículo escolhido foi um já acidentado
#         if not vehicle_is_already_considered(veh_accidented_id=veh_accidented_id):
#             break # Sai do loop se nenhuma das condições para continuar for verdadeira

#     add_vehicle_to_accident(veh_accidented_id, accidented_road_id)


def vehicle_is_in_a_valid_position_lane(veh_accidented_id):
    position = traci.vehicle.getLanePosition(veh_accidented_id)
    return position > 0.4 * settings.LANE_LENGTH and position < 0.6 * settings.LANE_LENGTH


def accidented_road_is_already_accidented(accidented_road_id):
    return (
        any(veh_accidented['accidented_road_id'] == accidented_road_id
        for veh_accidented in settings.buffer_vehicles_accidenteds)
    )


def vehicle_is_already_considered(veh_accidented_id):
    return (
        any(veh_accidented['veh_accidented_id'] == veh_accidented_id
        for veh_accidented in settings.buffer_vehicles_accidenteds)
    )


def add_vehicle_to_accident(veh_accidented_id, accidented_road_id):
    severity = assign_random_severity()
    color_highlight = settings.severity_colors[severity]
    speed_road_accidented = settings.severity_speed_road_accidented[severity]
    traci.edge.setMaxSpeed(accidented_road_id, speed_road_accidented)
    traci.vehicle.setSpeed(veh_accidented_id, 0)
    traci.vehicle.highlight(veh_accidented_id, color_highlight)
    settings.buffer_vehicles_accidenteds.append(
        {
            'veh_accidented_id': veh_accidented_id,
            'accidented_road_id': accidented_road_id,
            'severity': severity,
            'time_accident': traci.simulation.getTime(),
            'time_recovered': None,
            'veh_emergency_id': None,
        }
    )
    add_counter_accidents()
    print(f'{traci.simulation.getTime()} - Vehicle {veh_accidented_id} has been accidented in road {accidented_road_id} with severity {severity}')
