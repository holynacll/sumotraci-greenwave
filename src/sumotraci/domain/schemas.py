from typing import Optional

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


class GreenWaveAllocationView(BaseModel):
    """Read-only snapshot of a TLS allocation, exposed to readers outside the manager."""
    tls_id: str
    veh_emergency_id: str
    deadline: float
    severity: str
    phase: str  # 'CLEARING' | 'EV_GREEN' | 'EXIT_YELLOW'


class RoadFreezed(BaseModel):
    road_id: str
    time: float
