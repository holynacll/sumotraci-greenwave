import random
from config import (
    traci,
    settings,
)

def assign_random_severity():
    return random.choice(list(settings.SeverityEnum)).value
        
def create_accident():
    vehicles = traci.vehicle.getIDList()
    while True:
        random_number = random.randrange(0, len(vehicles))
        veh_accidented_id = vehicles[random_number]
        accidented_road_id: str = traci.vehicle.getRoadID(veh_accidented_id)
        
        # se veículo escolhido foi acidentado em uma via que já está acidentada, então escolhe outro veículo
        if accidented_road_is_already_accidented(accidented_road_id=accidented_road_id):
            continue

        # se veículo escolhido está em uma junção interna da rede (não valida)
        if accidented_road_id.startswith(':'):
            continue
        
        # se veículo está em uma posição válida na faixa, longe dos cruzamentos
        if not vehicle_is_in_a_valid_position_lane(veh_accidented_id):
            continue

        # se veículo escolhido foi um veículo de emergência
        veh_accidented_type_id = traci.vehicle.getTypeID(veh_accidented_id)
        if veh_accidented_type_id == 'emergency_emergency':
            continue

        # se veículo escolhido foi um já acidentado
        if not vehicle_is_already_considered(veh_accidented_id=veh_accidented_id):
            break # Sai do loop se nenhuma das condições para continuar for verdadeira

    add_vehicle_to_accident(veh_accidented_id, accidented_road_id)


def vehicle_is_in_a_valid_position_lane(veh_accidented_id):
    position = traci.vehicle.getLanePosition(veh_accidented_id)
    return position > 0.3 * settings.LANE_LENGTH and position < 0.7 * settings.LANE_LENGTH


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
    traci.edge.setMaxSpeed(accidented_road_id, settings.MAX_SPEED_ROAD_ACCIDENTED)
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
