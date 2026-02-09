from typing import List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from .enums import StatusEnum


class Accident(BaseModel):
    veh_accidented_id: str
    accidented_road_id: str
    lane_accidented_id: str
    severity: str  # Could be SeverityEnum if aligned
    time_accident: float
    deadline: float
    time_recovered: Optional[float] = None
    veh_emergency_id: Optional[str] = None


class EmergencyDispatchSchedule(BaseModel):
    accident: Accident
    time: float


class EmergencyVehicle(BaseModel):
    veh_accidented_id: str
    veh_emergency_id: str
    accidented_road_id: str
    severity: str
    deadline: float
    arrival_pos: float
    hospital_pos_start: str
    hospital_pos_end: str
    status: str = Field(default=StatusEnum.ON_THE_WAY.value)
    duration: int
    departure_time: float
    time_arrival: Optional[float] = None
    vehicle_removed: bool = False


class GreenWaveTLS(BaseModel):
    tls_id: str
    veh_emergency_id: str
    severity: str
    deadline: float
    original_tl_program: str
    ryg_state: Optional[str] = None
    status: str = 'INITIAL_TRANSITION'
    controlled_lanes: List[str]
    controlled_edges: Set[str]
    next_edges: List[str]
    first_edge_on_route_to_reach_tls_id: str
    change_transition: bool = False
    time_limit: float
    arrival_position: Tuple[float, float]
    starting_position: Tuple[float, float]


class RoadFreezed(BaseModel):
    road_id: str
    time: float
