from config import (
    traci,
    settings,
)


def improve_traffic_for_emergency_vehicle():
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
        next_edges = get_next_edges(veh_emergency_id)
        remove_remaining_tls_on_green_wave(veh_emergency_id, next_tls_set)
        for tls in next_tls_set:
            """
            Return list of upcoming traffic lights [(tlsID, tlsIndex, distance, state), ...]
            """
            tls_id = tls[0]
            vehicle_distance_to_tls = tls[2]
            tls_state = tls[3]
            # controller_links = traci.trafficlight.getControlledLinks(tls_id)
            # ryg_state = traci.trafficlight.getRedYellowGreenState(tls_id)
            # phase = traci.trafficlight.getPhase(tls_id)
            # complete_ryg_state = traci.trafficlight.getAllProgramLogics(tls_id)
            # print(f'{traci.simulation.getTime()} - TLS {tls_id} - vehicle_distance_to_tls: {vehicle_distance_to_tls} - tls_state: {tls_state} - controlled_lanes: {controlled_lanes} - controller_links: {controller_links} - ryg_state: {ryg_state} - phase: {phase} - complete_ryg_state: {complete_ryg_state}')
            # quit()
            if vehicle_distance_to_tls <= settings.VEHICLE_DISTANCE_TO_TLS:
                controlled_lanes = traci.trafficlight.getControlledLanes(tls_id)
                controlled_edges = set([lane.split('_')[0] for lane in controlled_lanes])
                edge_at_tls = None
                for edge in next_edges:
                    if edge in controlled_edges:
                        edge_at_tls = edge
                        break
                if edge_at_tls is None:
                    continue
                # print(next_edges, edge_at_tls, controlled_lanes, controlled_edges)
                # print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} is close to TLS {tls_id} at edge {edge_at_tls}')
                # print(f'buffer_tls_on_transition: {settings.buffer_tls_on_transition}')
                print(f'buffer_tls_on_green_wave: {settings.buffer_tls_on_green_wave}')
                # se tls já está alocado para algum veículo de emergência mais grave
                if is_tls_allocated_to_a_more_serious_emergency_vehicle(
                    tls_id=tls_id,
                    veh_emergency_id = veh_emergency_id,
                    severity = severity,
                ):
                    continue
                # green wave solution
                if not any(
                    tls_on_green_wave['tls_id'] == tls_id
                    for tls_on_green_wave in settings.buffer_tls_on_green_wave
                ):
                    settings.buffer_tls_on_green_wave.append({
                        'tls_id': tls_id,
                        'veh_emergency_id': veh_emergency_id,
                        'severity': severity,
                        'original_tl_program': traci.trafficlight.getProgram(tls_id),
                        'new_ryg_state': None,
                        'edge_at_tls': edge_at_tls,
                        'controlled_lanes': controlled_lanes,
                        'controlled_edges': controlled_edges,
                    })
                if tls_state in ('G'):
                    # traci.trafficlight.setPhaseDuration(tls_id, settings.TLJ_PHASE_GREEN_DURATION)
                    new_ryg_state = ''.join(['G' if edge_at_tls in lane else 'r' for lane in controlled_lanes])
                    traci.trafficlight.setRedYellowGreenState(tls_id, new_ryg_state)
                    for key in range(len(settings.buffer_tls_on_green_wave) - 1):
                        tls_on_green_wave = settings.buffer_tls_on_green_wave[key]
                        if tls_on_green_wave['tls_id'] == tls_id:
                            tls_on_green_wave['new_ryg_state'] = new_ryg_state
                elif any(
                    tls_on_transition['tls_id'] == tls_id
                    for tls_on_transition in settings.buffer_tls_on_transition
                ):
                    for key in range(len(settings.buffer_tls_on_transition) - 1):
                        tls_on_transition = settings.buffer_tls_on_transition[key]
                        if tls_on_transition['tls_id'] == tls_id:
                            # print(tls_on_transition['time_limit'] < traci.simulation.getTime())
                            if tls_on_transition['time_limit'] < traci.simulation.getTime():
                                settings.buffer_tls_on_transition.pop(key)
                                # traci.trafficlight.setPhaseDuration(tls_id, settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT)
                                # settings.buffer_tls_on_transition[key]['time_limit'] = traci.simulation.getTime() + settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT
                else:
                    traci.trafficlight.setPhaseDuration(tls_id, settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT)
                    settings.buffer_tls_on_transition.append({
                        'tls_id': tls_id,
                        'time_limit': traci.simulation.getTime() + settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT
                    })



def is_tls_allocated_to_a_more_serious_emergency_vehicle(
    tls_id,
    veh_emergency_id,
    severity,
):
    for key, tls_on_green_wave in enumerate(settings.buffer_tls_on_green_wave):
        if tls_on_green_wave['tls_id'] == tls_id:
            # verifica se o veículo de emergência atual é mais grave que o veículo de emergência alocado
            if tls_on_green_wave['veh_emergency_id'] != veh_emergency_id:
                if settings.severity_order[tls_on_green_wave['severity']] < settings.severity_order[severity]:
                    settings.buffer_tls_on_green_wave.pop(key)
                    return False
                return True
    return False


def remove_remaining_tls_on_green_wave(veh_emergency_id, next_tls_set):
    for key in range(len(settings.buffer_tls_on_green_wave) - 1, -1, -1):
        tls_on_green_wave = settings.buffer_tls_on_green_wave[key]
        if tls_on_green_wave['veh_emergency_id'] == veh_emergency_id:
            # print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} is not close to TLS {tls_on_green_wave["tls_id"]} - next_tls_set: {next_tls_set}')
            if not any(
                tls[0] == tls_on_green_wave['tls_id'] and
                tls[2] <= settings.VEHICLE_DISTANCE_TO_TLS
                for tls in next_tls_set
            ):
                traci.trafficlight.setProgram(tls_on_green_wave['tls_id'], tls_on_green_wave['original_tl_program'])
                settings.buffer_tls_on_green_wave.pop(key)
                print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has left TLS {tls_on_green_wave["tls_id"]}')


def get_next_edges(veh_id: str):
    actual_edge = traci.vehicle.getRoadID(veh_id)
    next_edges = [actual_edge]
    next_links_set = traci.vehicle.getNextLinks(veh_id)
    for link in next_links_set:
        edge = link[0].split('_')[0]
        next_edges.append(edge)
    return next_edges
