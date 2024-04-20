from config import (
    traci,
    settings,
)


def call_emergency_vehicle():
    # Se não houver veículos acidentados, não chama veículo de emergência
    if len(settings.buffer_vehicles_accidenteds) == 0:
            return "Se não houver veículos acidentados, não chama veículo de emergência"

    # Se não houver veículos acidentados sem veículo de emergência associado, não chama veículo de emergência
    vehicle_to_help = any(veh_accidented['veh_emergency_id'] is None
                        for veh_accidented in settings.buffer_vehicles_accidenteds)
    
    if not vehicle_to_help:
        return "Não há veículos acidentados sem veículo de emergência associado"

    # Chama veículo de emergência para o acidente mais grave e mais recente
    accident = find_most_severe_recent_accident()
    if accident is not None:
        add_emergency_vehicle(accident['veh_accidented_id'], accident['accidented_road_id'], accident['severity'])


def add_emergency_vehicle(veh_accidented_id, accidented_road_id, severity):
    emergency_route_id = f"rou_emergency_{traci.simulation.getTime()}"
    veh_emergency_id = f"veh_emergency_{traci.simulation.getTime()}"
    
    arrival_pos = traci.vehicle.getLanePosition(veh_accidented_id)
    route_to_accident = traci.simulation.findRoute(
        fromEdge=settings.HOSPITAL_POS_START,
        toEdge=accidented_road_id,
    )
    route_from_accident_to_hospital = traci.simulation.findRoute(
        fromEdge=accidented_road_id,
        toEdge=settings.HOSPITAL_POS_END,
    )
    route_1_edges_tuple = route_to_accident.edges
    route_2_edges_tuple = route_from_accident_to_hospital.edges[1:]
    complete_edge_list = route_1_edges_tuple + route_2_edges_tuple
    traci.route.add(routeID=emergency_route_id, edges=complete_edge_list)
    # for e in complete_edge_list:
    #     traci.gui.toggleSelection(e, "edge")
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
    # traci.vehicle.setSpeedMode(veh_emergency_id, 0)
    settings.buffer_emergency_vehicles.append({
        'veh_accidented_id': veh_accidented_id,
        'veh_emergency_id':veh_emergency_id,
        'accidented_road_id': accidented_road_id,
        'severity': severity,
        'arrival_pos': arrival_pos,
        'hospital_pos_start': settings.HOSPITAL_POS_START,
        'hospital_pos_end': settings.HOSPITAL_POS_END,
        'status': settings.StatusEnum.ON_THE_WAY.value,
        'duration': settings.MAX_STOP_DURATION,
        'departure_time': traci.simulation.getTime(),
        'time_arrival': None
    })
    for key, veh_accidented in enumerate(settings.buffer_vehicles_accidenteds):
        if veh_accidented['veh_accidented_id'] == veh_accidented_id:
            settings.buffer_vehicles_accidenteds[key]['veh_emergency_id'] = veh_emergency_id
    print(
        f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has been added to help vehicle '
        f'{veh_accidented_id} in road {accidented_road_id} with severity {severity}'
    )


def find_most_severe_recent_accident(): # EDF - Earliest Deadline First with Deadline Severity
    # Filtra acidentes que não possuem veículo de emergência associado
    filtered_accidents = [
        accident for accident in settings.buffer_vehicles_accidenteds
        if accident['veh_emergency_id'] is None
    ]
    
    # Se não encontrar acidentes sem veículo de emergência, retorna None
    if not filtered_accidents:
        return None
    
    # Ordena os acidentes filtrados primeiro pela gravidade e então pelo tempo do acidente, do mais recente ao mais antigo
    filtered_accidents.sort(key=lambda x: (settings.severity_order[x['severity']], -x['time_accident']))
    
    # Retorna o acidente mais grave e mais recente dentro mesmo nível de gravidade
    return filtered_accidents[0]
