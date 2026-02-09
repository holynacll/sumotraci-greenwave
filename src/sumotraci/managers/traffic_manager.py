import math

try:
    import traci
except ImportError:
    traci = None

from ..core.config import Settings


class TrafficManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def improve_traffic_for_emergency_vehicle(self):
        self._green_wave_logic()

        # Sort emergency vehicles by deadline
        emergency_vehicles_sorted = sorted(
            self.settings.buffer_emergency_vehicles,
            key=lambda x: (x['deadline'])
        )

        for emergency_vehicle in emergency_vehicles_sorted:
            veh_emergency_id = emergency_vehicle['veh_emergency_id']
            severity = emergency_vehicle['severity']
            deadline = emergency_vehicle['deadline']

            try:
                next_tls_set = traci.vehicle.getNextTLS(veh_emergency_id)
            except traci.TraCIException:
                continue

            for tls in next_tls_set:
                tls_id = tls[0]
                vehicle_distance_to_tls = tls[2]

                if vehicle_distance_to_tls <= self.settings.VEHICLE_DISTANCE_TO_TLS:
                    if not self._is_tls_allocated_to_a_more_serious_emergency_vehicle(
                        tls_id=tls_id,
                        veh_emergency_id=veh_emergency_id,
                        severity=severity,
                        deadline=deadline,
                    ):
                        print(
                            f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} '
                            f'has reached TLS {tls_id}'
                        )
                        self._store_green_wave(tls_id, veh_emergency_id, severity, deadline)

    def improve_traffic_on_accidented_road(self):
        if not self.settings.buffer_emergency_vehicles:
            return

        vehicles = traci.vehicle.getIDList()
        # Optimization: Don't iterate all vehicles for every emergency vehicle if possible,
        # but sticking to original logic for now which seems to try to reroute everyone around accident spots.

        # Actually original logic iterates emergency vehicles then all vehicles.
        # Rerouting should be done based on accident location, not necessarily emergency vehicle presence,
        # but original code checks if buffer_emergency_vehicles > 0.

        for emergency_vehicle in self.settings.buffer_emergency_vehicles:
            accidented_road_id = emergency_vehicle['accidented_road_id']
            # Re-fetch vehicles might be expensive, done once outside loop

            for veh_id in vehicles:
                try:
                    type_id = traci.vehicle.getTypeID(veh_id)
                except traci.TraCIException:
                    continue

                if type_id != 'emergency_emergency':
                    next_roads_list = traci.vehicle.getRoute(veh_id)
                    if accidented_road_id in next_roads_list:
                        try:
                            # Verify if edge has travel time set, otherwise default?
                            # Original code: traci.edge.adaptTraveltime(
                            #    accidented_road_id, traci.edge.getTraveltime(accidented_road_id)
                            # )
                            # This line in original code seems effectively no-op unless
                            # getTraveltime returns updated value from simulation
                            # and adaptTraveltime sets it for routing.
                            current_travel_time = traci.edge.getTraveltime(accidented_road_id)
                            traci.edge.adaptTraveltime(accidented_road_id, current_travel_time)

                            traci.vehicle.rerouteTraveltime(veh_id)

                            # Coloring for debug
                            if next_roads_list[-1] == accidented_road_id:
                                traci.vehicle.setColor(veh_id, (0, 100, 100))
                            elif next_roads_list[0] == accidented_road_id:
                                traci.vehicle.setColor(veh_id, (100, 0, 100))
                            else:
                                traci.vehicle.setColor(veh_id, (0, 255, 0))
                        except traci.TraCIException:
                            pass

    def _store_green_wave(
        self, tls_id: str, veh_emergency_id: str, severity: str, deadline, status: str = 'INITIAL_TRANSITION'
    ):
        print(
            f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} '
            f'has reached TLS {tls_id} - status: {status} - and going to store green wave.'
        )
        next_edges_sorted = self._get_next_edges(veh_emergency_id)
        controlled_lanes = traci.trafficlight.getControlledLanes(tls_id)
        controlled_edges = {lane.split('_')[0] for lane in controlled_lanes}

        first_edge_on_route = None
        for edge in next_edges_sorted:
            if edge in controlled_edges:
                first_edge_on_route = edge
                break

        if first_edge_on_route is not None:
            self.settings.buffer_tls_on_green_wave.append({
                'tls_id': tls_id,
                'veh_emergency_id': veh_emergency_id,
                'severity': severity,
                'deadline': deadline,
                'original_tl_program': traci.trafficlight.getProgram(tls_id),
                'ryg_state': None,
                'status': status,
                'controlled_lanes': controlled_lanes,
                'controlled_edges': controlled_edges,
                'next_edges': next_edges_sorted,
                'first_edge_on_route_to_reach_tls_id': first_edge_on_route,
                'change_transition': False,
                'time_limit': traci.simulation.getTime(),
                'arrival_position': traci.junction.getPosition(tls_id),
                'starting_position': traci.vehicle.getPosition(veh_emergency_id),
            })

    def _green_wave_logic(self):
        if not self.settings.buffer_tls_on_green_wave:
            return

        for key in range(len(self.settings.buffer_tls_on_green_wave) - 1, -1, -1):
            self._monitor_time_to_change_transition(key)
            self._vehicle_passed_tls_green_wave(key)

            # Double check if item still exists (vehicle_passed_tls_green_wave might affect it? No, but logic safety)
            # Actually _monitor_time_to_change_transition modifies status.

            if key >= len(self.settings.buffer_tls_on_green_wave):
                continue

            if not self.settings.buffer_tls_on_green_wave[key]['change_transition']:
                status = self.settings.buffer_tls_on_green_wave[key]['status']
                if status == 'INITIAL_TRANSITION':
                    self._green_wave_initial_transition(key)
                elif status == 'IN_PROGRESS':
                    self._green_wave_in_progress(key)
                elif status == 'FINAL_TRANSITION':
                    self._green_wave_final_transition(key)
                elif status == 'RETURN_TO_PROGRAM_ORIGINAL':
                    self._green_wave_return_to_program_original(key)

    def _monitor_time_to_change_transition(self, key: int):
        item = self.settings.buffer_tls_on_green_wave[key]
        if item['change_transition'] and item['time_limit'] < traci.simulation.getTime():
            if item['status'] == 'INITIAL_TRANSITION':
                item['status'] = 'IN_PROGRESS'
                item['change_transition'] = False
            elif item['status'] == 'IN_PROGRESS':
                item['status'] = 'FINAL_TRANSITION'
                item['change_transition'] = False
            elif item['status'] == 'FINAL_TRANSITION':
                item['status'] = 'RETURN_TO_PROGRAM_ORIGINAL'
                item['change_transition'] = False

    def _green_wave_initial_transition(self, key: int):
        item = self.settings.buffer_tls_on_green_wave[key]
        tls_id = item['tls_id']
        controlled_lanes = item['controlled_lanes']
        first_edge = item['first_edge_on_route_to_reach_tls_id']

        tls_state = traci.trafficlight.getRedYellowGreenState(tls_id)
        ryg_state = ''

        for index, lane in enumerate(controlled_lanes):
            lane_state = tls_state[index]
            if first_edge in lane and lane_state in ('g', 'G'):
                ryg_state += 'G'
            else:
                ryg_state += lane_state

        traci.trafficlight.setRedYellowGreenState(tls_id, ryg_state)
        item['ryg_state'] = ryg_state
        item['change_transition'] = True
        item['time_limit'] = traci.simulation.getTime() + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT

    def _green_wave_in_progress(self, key: int):
        item = self.settings.buffer_tls_on_green_wave[key]
        tls_id = item['tls_id']
        controlled_lanes = item['controlled_lanes']
        first_edge = item['first_edge_on_route_to_reach_tls_id']

        ryg_state = ''
        for lane in controlled_lanes:
            if first_edge in lane:
                ryg_state += 'G'
            else:
                ryg_state += 'r'

        traci.trafficlight.setRedYellowGreenState(tls_id, ryg_state)
        item['ryg_state'] = ryg_state

    def _green_wave_final_transition(self, key: int):
        item = self.settings.buffer_tls_on_green_wave[key]
        tls_id = item['tls_id']
        controlled_lanes = item['controlled_lanes']

        tls_state = traci.trafficlight.getRedYellowGreenState(tls_id)
        ryg_state = ''
        for index, lane in enumerate(controlled_lanes):
            lane_state = tls_state[index]
            if lane_state in ('g', 'G'):
                ryg_state += 'y'
            else:
                ryg_state += lane_state

        traci.trafficlight.setRedYellowGreenState(tls_id, ryg_state)
        item['ryg_state'] = ryg_state
        item['change_transition'] = True
        item['time_limit'] = traci.simulation.getTime() + self.settings.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT

    def _green_wave_return_to_program_original(self, key: int):
        self._remove_tls_on_green_wave(key)

    def _is_tls_allocated_to_a_more_serious_emergency_vehicle(
        self, tls_id, veh_emergency_id, severity, deadline
    ):
        for key, tls_on_green_wave in enumerate(self.settings.buffer_tls_on_green_wave):
            if tls_on_green_wave['tls_id'] == tls_id:
                if tls_on_green_wave['veh_emergency_id'] == veh_emergency_id:
                    return True

                if (
                    self._proportion_to_conclude_green_wave(key) >=
                    self.settings.SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA
                ):
                    return True

                if tls_on_green_wave['deadline'] < deadline:
                    return True

                if tls_on_green_wave['status'] in ('IN_PROGRESS', 'INITIAL_TRANSITION'):
                    self.settings.buffer_tls_on_green_wave[key]['status'] = 'FINAL_TRANSITION'
                return True
        return False

    def _vehicle_passed_tls_green_wave(self, key: int):
        item = self.settings.buffer_tls_on_green_wave[key]
        if item['status'] == 'IN_PROGRESS':
            try:
                next_tls_set = traci.vehicle.getNextTLS(item['veh_emergency_id'])
                if not any(
                    tls[0] == item['tls_id'] and tls[2] <= self.settings.VEHICLE_DISTANCE_TO_TLS
                    for tls in next_tls_set
                ):
                    item['change_transition'] = True
            except traci.TraCIException:
                # Vehicle might be gone
                item['change_transition'] = True

    def _get_next_edges(self, veh_id: str):
        route = traci.vehicle.getRoute(veh_id)
        route_index = traci.vehicle.getRouteIndex(veh_id)
        route_index = max(route_index, 0)
        return route[route_index:]

    def _remove_tls_on_green_wave(self, key: int):
        tls_on_green_wave = self.settings.buffer_tls_on_green_wave[key]
        veh_emergency_id = tls_on_green_wave['veh_emergency_id']
        tls_id = tls_on_green_wave['tls_id']
        original_tl_program = tls_on_green_wave['original_tl_program']
        traci.trafficlight.setProgram(tls_id, original_tl_program)
        self.settings.buffer_tls_on_green_wave.pop(key)
        print(f'{traci.simulation.getTime()} - Emergency Vehicle {veh_emergency_id} has left TLS {tls_id}')

    def _proportion_to_conclude_green_wave(self, key: int):
        item = self.settings.buffer_tls_on_green_wave[key]
        x1, y1 = item['starting_position']
        x2, y2 = item['arrival_position']
        try:
            x3, y3 = traci.vehicle.getPosition(item['veh_emergency_id'])
        except traci.TraCIException:
            return 1.0 # Assume completed if vehicle gone

        euclidian_distance_arrival = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        euclidian_distance_current = math.sqrt((x3 - x1)**2 + (y3 - y1)**2)

        if euclidian_distance_arrival == 0:
            return 1.0

        return euclidian_distance_current / euclidian_distance_arrival
