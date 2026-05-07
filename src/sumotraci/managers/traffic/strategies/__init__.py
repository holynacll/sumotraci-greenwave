from ....core.config import Settings
from ....core.sumo_interface import SumoInterface
from ...emergency_manager import EmergencyManager
from .base import TrafficControlStrategy
from .default import NoOpStrategy
from .edf_greenwave import EDFGreenWaveStrategy


def make_strategy(
    name: str,
    settings: Settings,
    sumo: SumoInterface,
    emergency_manager: EmergencyManager,
) -> TrafficControlStrategy:
    if name == "default":
        return NoOpStrategy()
    if name in ("proposto", "edf_greenwave"):
        return EDFGreenWaveStrategy(settings, sumo, emergency_manager)
    if name == "mpc":
        raise NotImplementedError("MPCStrategy not yet implemented (see docs/MPC_PLAN.md Phase 1+)")
    raise ValueError(f"Unknown algorithm: '{name}'. Accepted: default, proposto, edf_greenwave, mpc.")
