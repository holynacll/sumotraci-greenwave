from typing import Dict, List, Tuple

from pydantic_settings import BaseSettings

from ..domain.enums import SeverityEnum


class Settings(BaseSettings):
    # Simulation Parameters
    SEED: int = 217492
    SEEDS: List[int] = [
        428956419, 1954324947, 1145661099, 1835732737, 794161987,
        1329531353, 200496737, 633816299, 1410143363, 1282538739,
    ]
    VEHICLE_NUMBER: int = 4800
    TIME_TO_BLOCK_CREATE_ACCIDENTS: float = 50.0
    DELAY_TO_DISPATCH_EMERGENCY_VEHICLE: float = 120.0
    CAR_FOLLOW_MODEL: str = 'EIDM'
    ALGORITHM: str = 'proposto'

    # Traffic Management
    SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA: float = 0.8
    MAX_ELIGIBLE_ACCIDENTED_ROADS: int = 4
    VEHICLE_DISTANCE_TO_TLS: int = 300
    TIME_FOR_NEXT_ACCIDENT: float = 300.0
    SIMULATION_END_TIME: float = 900.0

    # Network Properties
    LANE_LENGTH: float = 300.0
    LANE_NUMBER: int = 3
    GRID_NUMBER: int = 5
    TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT: float = 8.0
    MAX_STOP_DURATION: int = 10
    ACCIDENT_DURATION: int = 1500
    SPEED_ROAD: float = 13.89

    # Emergency Vehicle Constraints
    MIN_ARRIVAL_DISTANCE_EMERGENCY_VEHICLE_AT_THE_ACCIDENT: float = 15.0
    LATERAL_RESOLUTION: float = 1.8
    BLUE_LIGHT_REACTION_DIST: float = 25.0
    MIN_GAP_EV: float = 3.0
    # Severity Metadata
    SEVERITY_ORDER: Dict[str, int] = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    SEVERITY_GOLDEN_TIME: Dict[SeverityEnum, int] = {
        SeverityEnum.CRITICAL: 700,
        SeverityEnum.HIGH: 850,
        SeverityEnum.MEDIUM: 1000,
        SeverityEnum.LOW: 1300,
    }
    SEVERITY_COLORS: Dict[SeverityEnum, Tuple[int, int, int, int]] = {
        SeverityEnum.CRITICAL: (255, 0, 0, 255),
        SeverityEnum.HIGH: (255, 165, 0, 255),
        SeverityEnum.MEDIUM: (255, 255, 0, 255),
        SeverityEnum.LOW: (0, 255, 0, 255)
    }
    SEVERITY_SPEED_ROAD_ACCIDENTED: Dict[SeverityEnum, float] = {
        SeverityEnum.CRITICAL: 1.0,
        SeverityEnum.HIGH: 1.0,
        SeverityEnum.MEDIUM: 1.0,
        SeverityEnum.LOW: 1.0
    }

    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }

# Create a global instance for now to ease transition, but prefer passing it around
settings = Settings()
