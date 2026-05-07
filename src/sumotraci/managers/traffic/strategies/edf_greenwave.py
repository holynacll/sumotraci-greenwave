from typing import List

from ....core.config import Settings
from ....core.sumo_interface import SumoInterface
from ....domain.schemas import GreenWaveAllocationView
from ...emergency_manager import EmergencyManager
from ..green_wave import GreenWaveManager
from .base import TrafficControlStrategy


class EDFGreenWaveStrategy(TrafficControlStrategy):
    """
    Reactive EDF + Green Wave preemption (the original 'proposto' algorithm).

    Each step:
        1. tick() advances active green-wave allocations.
        2. For every emergency vehicle (sorted by deadline, EDF), request a
           green wave at every TLS within VEHICLE_DISTANCE_TO_TLS. The manager
           internally arbitrates conflicts via its ArbitrationPolicy.
    """

    def __init__(self, settings: Settings, sumo: SumoInterface, emergency_manager: EmergencyManager):
        self.settings = settings
        self.sumo = sumo
        self.emergency_manager = emergency_manager
        self._green_wave = GreenWaveManager(settings, sumo)

    def improve(self) -> None:
        self._green_wave.tick(self.sumo.get_time())

        evs = sorted(
            self.emergency_manager.buffer_emergency_vehicles,
            key=lambda ev: ev.deadline,
        )

        for ev in evs:
            try:
                next_tls = self.sumo.vehicle_get_next_tls(ev.veh_emergency_id)
            except self.sumo.TraCIException:
                continue

            for tls_id, _tls_index, distance, _state in next_tls:
                if distance > self.settings.VEHICLE_DISTANCE_TO_TLS:
                    continue
                self._green_wave.request(
                    tls_id=tls_id,
                    veh_emergency_id=ev.veh_emergency_id,
                    deadline=ev.deadline,
                    severity=ev.severity,
                )

    def active_allocations(self) -> List[GreenWaveAllocationView]:
        return self._green_wave.allocations
