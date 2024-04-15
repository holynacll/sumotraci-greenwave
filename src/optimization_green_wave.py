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
        next_tls_set = traci.vehicle.getNextTLS(veh_emergency_id)
        for tls in next_tls_set:
            tls_id = tls[0]
            tls_state = tls[3]
            vehicle_distance_to_tls = tls[2]
            if vehicle_distance_to_tls <= settings.VEHICLE_DISTANCE_TO_TLS:
                # se tls já está alocado para algum veículo de emergência mais grave
                if is_tls_allocated_to_a_more_serious_emergency_vehicle(
                    tls_id=tls_id,
                    veh_emergency_id = veh_emergency_id,
                    severity = severity,
                ):
                    continue
                # green wave solution
                if tls_state in ('g', 'G'):
                    traci.trafficlight.setPhaseDuration(tls_id, settings.TLJ_PHASE_GREEN_DURATION)
                elif any(
                    tls_on_transition['tls_id'] == tls_id
                    for tls_on_transition in settings.buffer_tls_on_transition
                ):
                    for key in range(len(settings.buffer_tls_on_transition) - 1):
                        tls_on_transition = settings.buffer_tls_on_transition[key]
                        if tls_on_transition['tls_id'] == tls_id:
                            # print(tls_on_transition['time_limit'] < traci.simulation.getTime())
                            if tls_on_transition['time_limit'] < traci.simulation.getTime():
                                traci.trafficlight.setPhaseDuration(tls_id, settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT)
                                settings.buffer_tls_on_transition[key]['time_limit'] = traci.simulation.getTime() + settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT
                else:
                    traci.trafficlight.setPhaseDuration(tls_id, settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT)
                    settings.buffer_tls_on_transition.append({
                        'tls_id': tls_id,
                        'time_limit': traci.simulation.getTime() + settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT
                    })
                if not any(
                    tls_on_green_wave['tls_id'] == tls_id
                    for tls_on_green_wave in settings.buffer_tls_on_green_wave
                ):
                    settings.buffer_tls_on_green_wave.append({
                        'tls_id': tls_id,
                        'veh_emergency_id': veh_emergency_id,
                        'severity': severity,
                    })


def is_tls_allocated_to_a_more_serious_emergency_vehicle(
    tls_id,
    veh_emergency_id,
    severity,
):
    for key, tls_on_green_wave in enumerate(settings.buffer_tls_on_green_wave):
        if tls_on_green_wave['tls_id'] == tls_id:
            # verifica se o veículo de emergência atual é mais grave que o veículo de emergência alocado
            if tls_on_green_wave and tls_on_green_wave['veh_emergency_id'] != veh_emergency_id:
                if settings.severity_order[tls_on_green_wave['severity']] < settings.severity_order[severity]:
                    settings.buffer_tls_on_green_wave.pop(key)
                    return False
                return True
    return False
