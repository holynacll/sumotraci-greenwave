from config import (
    traci,
    settings,
)


def improve_traffic_for_emergency_vehicle():
    green_wave_logic()
    # ordena veículos de emergência por gravidade e mais recente
    emergency_vehicles_sorted_by_severity_and_most_recent = sorted(
        settings.buffer_emergency_vehicles,
        key=lambda x: (settings.severity_order[x['severity']], -x['departure_time'])
    )
    for emergency_vehicle in emergency_vehicles_sorted_by_severity_and_most_recent:
        veh_emergency_id = emergency_vehicle['veh_emergency_id']
        severity = emergency_vehicle['severity']
        try:
            next_tls_set = traci.vehicle.getNextTLS(veh_emergency_id)
        except traci.TraCIException:
            continue
        for tls in next_tls_set:
            """
            Return list of upcoming traffic lights [(tlsID, tlsIndex, distance, state), ...]
            """
            tls_id = tls[0]
            vehicle_distance_to_tls = tls[2]
            tls_state = tls[3]
            if vehicle_distance_to_tls <= settings.VEHICLE_DISTANCE_TO_TLS:
                
                if not is_tls_allocated_to_a_more_serious_emergency_vehicle(
                    tls_id=tls_id,
                    veh_emergency_id = veh_emergency_id,
                    severity = severity,
                ):
                    print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has reached TLS {tls_id}')
                    store_green_wave(tls_id, veh_emergency_id, severity)


def store_green_wave(tls_id: str, veh_emergency_id: str, severity: str, status: str = 'INITIAL_TRANSITION'):
    print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has reached TLS {tls_id} - status: {status} - and going to store green wave.')
    next_edges_sorted = get_next_edges(veh_emergency_id)
    controlled_lanes = traci.trafficlight.getControlledLanes(tls_id)
    controlled_edges = {lane.split('_')[0] for lane in controlled_lanes}
    first_edge_on_route_to_reach_tls_id = None
    for edge in next_edges_sorted:
        if edge in controlled_edges:
            first_edge_on_route_to_reach_tls_id = edge
            break
    if first_edge_on_route_to_reach_tls_id is not None:
        settings.buffer_tls_on_green_wave.append({
            'tls_id': tls_id,
            'veh_emergency_id': veh_emergency_id,
            'severity': severity,
            'original_tl_program': traci.trafficlight.getProgram(tls_id),
            'ryg_state': None,
            'status': status,
            'controlled_lanes': controlled_lanes,
            'controlled_edges': controlled_edges,
            'next_edges': next_edges_sorted,
            'first_edge_on_route_to_reach_tls_id': first_edge_on_route_to_reach_tls_id,
            'change_transition': False,
            'time_limit': traci.simulation.getTime(),
        })


def green_wave_logic():
    if len(settings.buffer_tls_on_green_wave) == 0:
        return
    for key in range(len(settings.buffer_tls_on_green_wave) -1, -1, -1):
        # print(f'len buffer_tls_on_green_wave: {len(settings.buffer_tls_on_green_wave)}')
        # print(f'key {key}: {settings.buffer_tls_on_green_wave[key]}')
        monitor_time_to_change_transition(key)
        vehicle_passed_tls_green_wave(key)
        if not settings.buffer_tls_on_green_wave[key]['change_transition']:
            match settings.buffer_tls_on_green_wave[key]['status']:
                case 'INITIAL_TRANSITION':
                    green_wave_initial_transition(key)
                case 'IN_PROGRESS':
                    green_wave_in_progress(key)
                case 'FINAL_TRANSITION':
                    green_wave_final_transition(key)
                case 'RETURN_TO_PROGRAM_ORIGINAL':
                    green_wave_return_to_program_original(key)
                case _:
                    raise Exception("Oops, something was wrong.")


def monitor_time_to_change_transition(key: str):
    if (
        settings.buffer_tls_on_green_wave[key]['change_transition'] and
        settings.buffer_tls_on_green_wave[key]['time_limit'] < traci.simulation.getTime()
    ):
        match settings.buffer_tls_on_green_wave[key]['status']:
            case 'INITIAL_TRANSITION':
                settings.buffer_tls_on_green_wave[key]['status'] = 'IN_PROGRESS'
                settings.buffer_tls_on_green_wave[key]['change_transition'] = False
            case 'IN_PROGRESS':
                settings.buffer_tls_on_green_wave[key]['status'] = 'FINAL_TRANSITION'
                settings.buffer_tls_on_green_wave[key]['change_transition'] = False
            case 'FINAL_TRANSITION':
                settings.buffer_tls_on_green_wave[key]['status'] = 'RETURN_TO_PROGRAM_ORIGINAL'
                settings.buffer_tls_on_green_wave[key]['change_transition'] = False


def green_wave_initial_transition(key: str):
    tls_id: str = settings.buffer_tls_on_green_wave[key]['tls_id']
    controlled_lanes: list[str] = settings.buffer_tls_on_green_wave[key]['controlled_lanes']
    first_edge_on_route_to_reach_tls_id: str = (
        settings.buffer_tls_on_green_wave[key]['first_edge_on_route_to_reach_tls_id']
    )
    tls_state = traci.trafficlight.getRedYellowGreenState(tls_id)
    ryg_state: str = ''
    for index, lane in enumerate(controlled_lanes):
        lane_state = tls_state[index]
        if first_edge_on_route_to_reach_tls_id in lane and lane_state in ('g', 'G'):
            ryg_state += 'G'
        elif lane_state in ('g', 'G'):
            ryg_state += 'y'
        else:
            ryg_state += lane_state
    print(ryg_state)
    traci.trafficlight.setRedYellowGreenState(tls_id, ryg_state)
    settings.buffer_tls_on_green_wave[key]['ryg_state'] = ryg_state
    settings.buffer_tls_on_green_wave[key]['change_transition'] = True
    settings.buffer_tls_on_green_wave[key]['time_limit'] = (
        traci.simulation.getTime() + settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT
    )


def green_wave_in_progress(key: str):
    tls_id: str = settings.buffer_tls_on_green_wave[key]['tls_id']
    controlled_lanes: list[str] = settings.buffer_tls_on_green_wave[key]['controlled_lanes']
    first_edge_on_route_to_reach_tls_id: str = (
        settings.buffer_tls_on_green_wave[key]['first_edge_on_route_to_reach_tls_id']
    )
    ryg_state: str = ''
    for lane in controlled_lanes:
        if first_edge_on_route_to_reach_tls_id in lane:
            ryg_state += 'G'
        else:
            ryg_state += 'r'
    traci.trafficlight.setRedYellowGreenState(tls_id, ryg_state)
    settings.buffer_tls_on_green_wave[key]['ryg_state'] = ryg_state


def green_wave_final_transition(key: str):
    tls_id: str = settings.buffer_tls_on_green_wave[key]['tls_id']
    controlled_lanes: list[str] = settings.buffer_tls_on_green_wave[key]['controlled_lanes']
    tls_state = traci.trafficlight.getRedYellowGreenState(tls_id)
    ryg_state: str = ''
    for index, lane in enumerate(controlled_lanes):
        lane_state = tls_state[index]
        if lane_state in ('g', 'G'):
            ryg_state += 'y'
        ryg_state += lane_state
    traci.trafficlight.setRedYellowGreenState(tls_id, ryg_state)
    settings.buffer_tls_on_green_wave[key]['ryg_state'] = ryg_state
    settings.buffer_tls_on_green_wave[key]['change_transition'] = True
    settings.buffer_tls_on_green_wave[key]['time_limit'] = (
        traci.simulation.getTime() + settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT
    )


def green_wave_return_to_program_original(key: str):
    remove_tls_on_green_wave(key)


def is_tls_allocated_to_a_more_serious_emergency_vehicle(
    tls_id,
    veh_emergency_id,
    severity,
):
    for key, tls_on_green_wave in enumerate(settings.buffer_tls_on_green_wave):
        if tls_on_green_wave['tls_id'] == tls_id:
            # verifica se o veículo de emergência atual é mais grave que o veículo de emergência alocado
            if tls_on_green_wave['veh_emergency_id'] == veh_emergency_id:
                return True
            if settings.severity_order[tls_on_green_wave['severity']] > settings.severity_order[severity]:
                return True
                # remove_tls_on_green_wave(key)
            settings.buffer_tls_on_green_wave[key]['status'] == 'FINAL_TRANSITION'
            return True
    return False


def vehicle_passed_tls_green_wave(key: str):
    if settings.buffer_tls_on_green_wave[key]['status'] == 'IN_PROGRESS':
        next_tls_set = traci.vehicle.getNextTLS(
            settings.buffer_tls_on_green_wave[key]['veh_emergency_id']
        )
        if not any(
            tls[0] == settings.buffer_tls_on_green_wave[key]['tls_id'] and
            tls[2] <= settings.VEHICLE_DISTANCE_TO_TLS
            for tls in next_tls_set
        ):
            settings.buffer_tls_on_green_wave[key]['change_transition'] = True


def get_next_edges(veh_id: str):
    route: str = traci.vehicle.getRoute(veh_id)
    route_index: str = traci.vehicle.getRouteIndex(veh_id)
    route_index = max(route_index, 0)
    return route[route_index:]


def remove_tls_on_green_wave(key: str):
    tls_on_green_wave = settings.buffer_tls_on_green_wave[key]
    veh_emergency_id = tls_on_green_wave['veh_emergency_id']
    tls_id = tls_on_green_wave['tls_id']
    original_tl_program = tls_on_green_wave['original_tl_program']
    traci.trafficlight.setProgram(tls_id, original_tl_program)
    settings.buffer_tls_on_green_wave.pop(key)
    print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has left TLS {tls_on_green_wave["tls_id"]}')
