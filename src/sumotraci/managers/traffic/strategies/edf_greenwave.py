from typing import List

from ....core.config import Settings
from ....core.sumo_interface import SumoInterface
from ....domain.schemas import GreenWaveAllocationView
from ...emergency_manager import EmergencyManager
from ..green_wave import GreenWaveManager, compute_priority_value, first_route_edge_at_tls
from .base import TrafficControlStrategy


class EDFGreenWaveStrategy(TrafficControlStrategy):
    """
    ETA-based EV preemption (the original 'proposto' algorithm, refactored).

    Each step:
        1. tick() advances active green-wave allocations.
        2. For every emergency vehicle (sorted by mission deadline, EDF outer
           ordering), request a green wave at every TLS within
           VEHICLE_DISTANCE_TO_TLS. The per-TLS priority_value is computed via
           compute_priority_value (ETA + severity penalty), so a closer or
           faster-arriving EV beats a farther one regardless of mission deadline
           differences. The manager arbitrates conflicts via its ArbitrationPolicy
           with a delta-threshold for anti-flicker.
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
                current_speed = self.sumo.vehicle_get_speed(ev.veh_emergency_id)
            except self.sumo.TraCIException:
                continue

            for tls_id, _tls_index, distance, _state in next_tls:
                if distance > self.settings.VEHICLE_DISTANCE_TO_TLS:
                    continue
                try:
                    controlled_lanes = self.sumo.trafficlight_get_controlled_lanes(tls_id)
                except self.sumo.TraCIException:
                    continue
                priority_edge = first_route_edge_at_tls(
                    self.sumo, ev.veh_emergency_id, controlled_lanes
                )
                if priority_edge is None:
                    continue
                self._green_wave.request(
                    tls_id=tls_id,
                    requester_id=ev.veh_emergency_id,
                    priority_edge=priority_edge,
                    priority_value=compute_priority_value(
                        distance, current_speed, ev.severity, self.settings
                    ),
                    severity=ev.severity,
                )

    def active_allocations(self) -> List[GreenWaveAllocationView]:
        return self._green_wave.allocations
