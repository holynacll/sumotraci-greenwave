from pydantic import field_validator
from pydantic_settings import BaseSettings

from ..domain.enums import SeverityEnum

_VALID_ALGORITHMS = {
    "baseline",
    "greenwave_legacy",
    "greenwave",
    "mpc",
}
_VALID_GW_PRIORITY = {"deadline", "eta"}


class Settings(BaseSettings):
    # Simulation Parameters
    SEED: int = 217492
    SEEDS: list[int] = [
        428956419,
        1954324947,
        1145661099,
        1835732737,
        794161987,
        1329531353,
        200496737,
        633816299,
        1410143363,
        1282538739,
    ]
    VEHICLE_NUMBER: int = 4800
    TIME_TO_BLOCK_CREATE_ACCIDENTS: float = 50.0
    DELAY_TO_DISPATCH_EMERGENCY_VEHICLE: float = 120.0
    CAR_FOLLOW_MODEL: str = "Krauss"
    # Control algorithm. Accepted:
    #   'baseline'          — no preemption (SUMO default behaviour)
    #   'greenwave_legacy'  — original pre-refactor green-wave, frozen as a
    #                          comparison baseline (4-status FSM, deadline-based,
    #                          no queue/anti-flicker/spillback). No plugins.
    #   'greenwave'         — unified engine; improvements composed via the GW_*
    #                          toggles below.
    #   'mpc'               — Phase B (not implemented).
    # See docs/ALGORITHMS.md for the full evolution table and ablation guide.
    ALGORITHM: str = "greenwave"

    # 'greenwave' composition. Defaults reproduce the former 'shield' algorithm.
    #   GW_PRIORITY: priority policy slot — "deadline" (raw mission deadline) or
    #               "eta" (ETA at TLS + severity penalty). Exactly one is active.
    #   GW_ANTIFLICKER: toggle MIN_EV_GREEN_HOLD + PREEMPT_DELTA_THRESHOLD.
    #   GW_PENDING_QUEUE: toggle the pending-allocation queue with hand-off.
    #   GW_SPILLBACK: toggle the BFS spillback detector + drain mechanism.
    GW_PRIORITY: str = "eta"
    GW_ANTIFLICKER: bool = True
    GW_PENDING_QUEUE: bool = True
    GW_SPILLBACK: bool = True

    # Traffic Management
    SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA: float = 0.8
    MAX_ELIGIBLE_ACCIDENTED_ROADS: int = 4
    VEHICLE_DISTANCE_TO_TLS: int = 400
    TIME_FOR_NEXT_ACCIDENT: float = 300.0
    SIMULATION_END_TIME: float = 900.0

    # Network Properties
    LANE_LENGTH: float = 300.0
    LANE_NUMBER: int = 3
    GRID_NUMBER: int = 5
    TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT: float = 8.0
    MAX_STOP_DURATION: int = 10

    # Spillback shield (Phase A)
    SPILLBACK_OCCUPANCY_THRESHOLD: float = 0.5  # detect saturation
    SPILLBACK_OCCUPANCY_RELEASE_THRESHOLD: float = 0.2  # hysteresis release
    DRAIN_MAX_DURATION: float = 30.0  # safety cap (s) for a single drain
    # BFS depth from EV's immediate-next TLS (root). 1 = only root scanned;
    # 2 = root + 1-hop neighbors via outgoing edges; 3 = +2-hop; etc.
    # In a 5x5 grid: depth=2 covers ~5 TLSs, depth=3 covers ~17.
    SPILLBACK_GRAPH_DEPTH: int = 1

    # ETA-based priority (Phase A++ / 2026-05-08)
    # Arbitration metric: priority_value = ETA_at_TLS + SEVERITY_ETA_PENALTY[severity].
    # Smaller value = higher priority (wins arbitration).
    # ETA_at_TLS = distance / max(current_speed, MIN_SPEED_FLOOR_FOR_ETA).
    MIN_SPEED_FLOOR_FOR_ETA: float = 5.0  # m/s; floor for ETA when EV is slow/stopped
    SEVERITY_ETA_PENALTY: dict[SeverityEnum, float] = {
        SeverityEnum.CRITICAL: 0.0,
        SeverityEnum.HIGH: 5.0,
        SeverityEnum.MEDIUM: 10.0,
        SeverityEnum.LOW: 15.0,
    }
    DRAIN_PRIORITY_VALUE: float = 100.0  # fixed priority for drain allocations
    # Anti-flicker: blindar EV_GREEN recém-iniciado e exigir delta mínimo para preemptar.
    # s; preemption locked-out for first MIN_EV_GREEN_HOLD seconds of EV_GREEN
    MIN_EV_GREEN_HOLD: float = 5.0
    # s; new requester must be at least this much better in priority_value to preempt
    PREEMPT_DELTA_THRESHOLD: float = 2.0

    # Visual: paint the priority edge lanes and a marker at the TLS junction with
    # the EV's severity color (or cyan for drain allocations) while the
    # allocation is active. Set to False for headless runs or to reduce GUI load.
    HIGHLIGHT_ALLOCATIONS: bool = True
    ACCIDENT_DURATION: int = 1500
    SPEED_ROAD: float = 13.89

    # Emergency Vehicle Constraints
    MIN_ARRIVAL_DISTANCE_EMERGENCY_VEHICLE_AT_THE_ACCIDENT: float = 15.0
    LATERAL_RESOLUTION: float = 1.8
    BLUE_LIGHT_REACTION_DIST: float = 40.0
    MIN_GAP_EV: float = 3.0
    # Severity Metadata
    SEVERITY_ORDER: dict[str, int] = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    SEVERITY_GOLDEN_TIME: dict[SeverityEnum, int] = {
        SeverityEnum.CRITICAL: 700,
        SeverityEnum.HIGH: 850,
        SeverityEnum.MEDIUM: 1000,
        SeverityEnum.LOW: 1300,
    }
    SEVERITY_COLORS: dict[SeverityEnum, tuple[int, int, int, int]] = {
        SeverityEnum.CRITICAL: (255, 0, 0, 255),
        SeverityEnum.HIGH: (255, 165, 0, 255),
        SeverityEnum.MEDIUM: (255, 255, 0, 255),
        SeverityEnum.LOW: (0, 255, 0, 255),
    }
    SEVERITY_SPEED_ROAD_ACCIDENTED: dict[SeverityEnum, float] = {
        SeverityEnum.CRITICAL: 1.0,
        SeverityEnum.HIGH: 1.0,
        SeverityEnum.MEDIUM: 1.0,
        SeverityEnum.LOW: 1.0,
    }

    @field_validator("ALGORITHM")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        if v not in _VALID_ALGORITHMS:
            raise ValueError(
                f"ALGORITHM must be one of {sorted(_VALID_ALGORITHMS)}, got '{v}'"
            )
        return v

    @field_validator("GW_PRIORITY")
    @classmethod
    def validate_gw_priority(cls, v: str) -> str:
        if v not in _VALID_GW_PRIORITY:
            raise ValueError(
                f"GW_PRIORITY must be one of {sorted(_VALID_GW_PRIORITY)}, got '{v}'"
            )
        return v

    model_config = {"env_file": ".env", "case_sensitive": True}


# Create a global instance for now to ease transition, but prefer passing it around
settings = Settings()
