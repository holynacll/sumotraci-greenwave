from ....core.config import Settings
from ....core.sumo_interface import SumoInterface
from ...emergency_manager import EmergencyManager
from .base import TrafficControlStrategy
from .baseline import NoOpStrategy
from .greenwave import GreenWaveStrategy
from .legacy_greenwave import LegacyGreenWaveStrategy


def make_strategy(
    name: str,
    settings: Settings,
    sumo: SumoInterface,
    emergency_manager: EmergencyManager,
) -> TrafficControlStrategy:
    if name == "baseline":
        return NoOpStrategy()
    if name == "greenwave_legacy":
        return LegacyGreenWaveStrategy(settings, sumo, emergency_manager)
    if name == "greenwave":
        return GreenWaveStrategy(settings, sumo, emergency_manager)
    if name == "mpc":
        raise NotImplementedError(
            "MPCStrategy not yet implemented (see docs/MPC_PLAN.md Phase B)"
        )
    raise ValueError(
        f"Unknown algorithm: '{name}'. "
        f"Accepted: baseline, greenwave_legacy, greenwave, mpc."
    )
