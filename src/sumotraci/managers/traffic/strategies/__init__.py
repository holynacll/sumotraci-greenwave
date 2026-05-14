from ....core.config import Settings
from ....core.sumo_interface import SumoInterface
from ...emergency_manager import EmergencyManager
from .base import TrafficControlStrategy
from .default import NoOpStrategy
from .edf_greenwave import EDFGreenWaveStrategy
from .fsm_greenwave import FSMGreenWaveStrategy
from .legacy_greenwave import LegacyGreenWaveStrategy
from .spillback_shield import SpillbackAwareEDFGreenWaveStrategy


def make_strategy(
    name: str,
    settings: Settings,
    sumo: SumoInterface,
    emergency_manager: EmergencyManager,
) -> TrafficControlStrategy:
    if name == "default":
        return NoOpStrategy()
    if name == "legacy_greenwave":
        return LegacyGreenWaveStrategy(settings, sumo, emergency_manager)
    if name == "fsm_greenwave":
        return FSMGreenWaveStrategy(settings, sumo, emergency_manager)
    if name in ("proposto", "edf_greenwave"):
        return EDFGreenWaveStrategy(settings, sumo, emergency_manager)
    if name == "shield":
        return SpillbackAwareEDFGreenWaveStrategy(settings, sumo, emergency_manager)
    if name == "mpc":
        raise NotImplementedError("MPCStrategy not yet implemented (see docs/SPILLBACK_PLAN.md Phase B)")
    raise ValueError(
        f"Unknown algorithm: '{name}'. "
        f"Accepted: default, legacy_greenwave, fsm_greenwave, proposto, edf_greenwave, shield, mpc."
    )
