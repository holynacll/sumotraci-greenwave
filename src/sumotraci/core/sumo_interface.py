from typing import Any, List, Optional, Tuple

try:
    import traci
    from sumolib import checkBinary  # noqa
except ImportError:
    traci = None

class SumoInterface:
    """
    Abstracts interactions with the SUMO TraCI API.
    Provides a typed interface for simulation control and object management.
    """

    def __init__(self):
        if traci is None:
            raise ImportError("TraCI module not found. Please ensure SUMO/TraCI is installed.")

    # --- Simulation Control ---
    def start(self, cmd: List[str]) -> None:
        traci.start(cmd)

    def close(self) -> None:
        traci.close()

    def simulation_step(self) -> None:
        traci.simulationStep()

    def get_time(self) -> float:
        return traci.simulation.getTime()

    def get_min_expected_number(self) -> int:
        return traci.simulation.getMinExpectedNumber()

    def find_route(self, from_edge: str, to_edge: str) -> Any:
        # Returns a Stage object (traci.simulation.Stage) which has .edges attribute
        return traci.simulation.findRoute(fromEdge=from_edge, toEdge=to_edge)

    # --- Vehicle Management ---
    def vehicle_get_id_list(self) -> List[str]:
        return traci.vehicle.getIDList()

    def vehicle_get_type_id(self, veh_id: str) -> str:
        return traci.vehicle.getTypeID(veh_id)

    def vehicle_get_lane_position(self, veh_id: str) -> float:
        return traci.vehicle.getLanePosition(veh_id)

    def vehicle_get_lane_id(self, veh_id: str) -> str:
        return traci.vehicle.getLaneID(veh_id)

    def vehicle_get_road_id(self, veh_id: str) -> str:
        return traci.vehicle.getRoadID(veh_id)

    def vehicle_get_allowed_speed(self, veh_id: str) -> float:
        return traci.vehicle.getAllowedSpeed(veh_id)

    def vehicle_get_lane_index(self, veh_id: str) -> int:
        return traci.vehicle.getLaneIndex(veh_id)

    def vehicle_get_position(self, veh_id: str) -> Tuple[float, float]:
        return traci.vehicle.getPosition(veh_id)

    def vehicle_get_route(self, veh_id: str) -> List[str]:
        return traci.vehicle.getRoute(veh_id)

    def vehicle_get_route_index(self, veh_id: str) -> int:
        return traci.vehicle.getRouteIndex(veh_id)

    def vehicle_get_next_tls(self, veh_id: str) -> List[Tuple[str, int, float, str]]:
        # Returns list of (tlsID, tlsIndex, distance, state)
        return traci.vehicle.getNextTLS(veh_id)

    def vehicle_get_follower(self, veh_id: str, dist: float) -> Tuple[str, float]:
        # Returns (followerID, dist)
        return traci.vehicle.getFollower(veh_id, dist)

    def vehicle_wants_and_could_change_lane(self, veh_id: str, direction: int) -> bool:
        # direction: -1 (right), 1 (left)
        state_int = traci.vehicle.wantsAndCouldChangeLane(veh_id, direction)
        # Returns int but interpreted as bool availability in many contexts,
        # though strictly check docs: returns state bitset.
        # The calling code checks implicit bool of the return.
        # Let's keep it consistent with original usage.
        return bool(state_int)

    def vehicle_get_driving_distance(self, veh_id: str, edge_id: str, pos: float, lane_index: int = 0) -> float:
        return traci.vehicle.getDrivingDistance(veh_id, edge_id, pos, lane_index)

    def vehicle_add(self, veh_id: str, route_id: str, type_id: str = "default",
                    depart: str = 'now', depart_lane: str = 'first',
                    depart_pos: str = 'base', depart_speed: str = '0',
                    arrival_lane: str = 'current', arrival_pos: str = 'max',
                    arrival_speed: str = 'current') -> None:
        traci.vehicle.add(
            vehID=veh_id, routeID=route_id, typeID=type_id, depart=depart,
            departLane=depart_lane, departPos=depart_pos, departSpeed=depart_speed,
            arrivalLane=arrival_lane, arrivalPos=arrival_pos, arrivalSpeed=arrival_speed
        )

    def vehicle_remove(self, veh_id: str) -> None:
        traci.vehicle.remove(veh_id)

    def vehicle_set_stop(self, veh_id: str, edge_id: str, pos: float,
                         lane_index: int, duration: float, flags: int = 0) -> None:
        traci.vehicle.setStop(veh_id, edgeID=edge_id, pos=pos, laneIndex=lane_index, duration=duration, flags=flags)

    def vehicle_slow_down(self, veh_id: str, speed: float, duration: float) -> None:
        traci.vehicle.slowDown(veh_id, speed, duration)

    def vehicle_change_lane(self, veh_id: str, lane_index: int, duration: float) -> None:
        traci.vehicle.changeLane(veh_id, lane_index, duration)

    def vehicle_highlight(self, veh_id: str, color: Tuple[int, int, int, int] = (255, 0, 0, 255),
                          size: float = -1, alpha_max: float = -1, duration: float = -1, type_id: int = 0) -> None:
        traci.vehicle.highlight(veh_id, color, size, alpha_max, duration, type_id)

    def vehicle_set_color(self, veh_id: str, color: Tuple[int, int, int]) -> None:
        traci.vehicle.setColor(veh_id, color)

    def vehicle_reroute_traveltime(self, veh_id: str, current_travel_times: bool = True) -> None:
        traci.vehicle.rerouteTraveltime(veh_id, current_travel_times)

    # --- Edge/Road Management ---
    def edge_get_id_list(self) -> List[str]:
        return traci.edge.getIDList()

    def edge_get_lane_number(self, edge_id: str) -> int:
        return traci.edge.getLaneNumber(edge_id)

    def edge_get_last_step_vehicle_ids(self, edge_id: str) -> List[str]:
        return traci.edge.getLastStepVehicleIDs(edge_id)

    def edge_set_max_speed(self, edge_id: str, speed: float) -> None:
        traci.edge.setMaxSpeed(edge_id, speed)

    def edge_get_travel_time(self, edge_id: str) -> float:
        return traci.edge.getTraveltime(edge_id)

    def edge_adapt_travel_time(
        self, edge_id: str, time: float, begin: Optional[float] = None, end: Optional[float] = None
    ) -> None:
        traci.edge.adaptTraveltime(edge_id, time, begin, end)

    # --- Lane Management ---
    def lane_get_edge_id(self, lane_id: str) -> str:
        return traci.lane.getEdgeID(lane_id)

    # --- Traffic Light Management ---
    def trafficlight_get_controlled_lanes(self, tls_id: str) -> List[str]:
        return traci.trafficlight.getControlledLanes(tls_id)

    def trafficlight_get_program(self, tls_id: str) -> str:
        return traci.trafficlight.getProgram(tls_id)

    def trafficlight_set_program(self, tls_id: str, program_id: str) -> None:
        traci.trafficlight.setProgram(tls_id, program_id)

    def trafficlight_get_red_yellow_green_state(self, tls_id: str) -> str:
        return traci.trafficlight.getRedYellowGreenState(tls_id)

    def trafficlight_set_red_yellow_green_state(self, tls_id: str, state: str) -> None:
        traci.trafficlight.setRedYellowGreenState(tls_id, state)

    # --- Junction Management ---
    def junction_get_position(self, junction_id: str) -> Tuple[float, float]:
        return traci.junction.getPosition(junction_id)

    # --- Route Management ---
    def route_add(self, route_id: str, edges: List[str]) -> None:
        traci.route.add(route_id, edges)

    # --- Exception Handling ---
    @property
    def TraCIException(self):
        return traci.TraCIException
