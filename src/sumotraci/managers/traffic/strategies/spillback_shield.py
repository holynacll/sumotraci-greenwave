from typing import List

from ....core.config import Settings
from ....core.sumo_interface import SumoInterface
from ....domain.schemas import GreenWaveAllocationView
from ...emergency_manager import EmergencyManager
from ..green_wave import GreenWaveManager, compute_priority_value, first_route_edge_at_tls
from ..spillback import SpillbackDetector
from .base import TrafficControlStrategy


class SpillbackAwareEDFGreenWaveStrategy(TrafficControlStrategy):
    """
    Spillback-aware EV preemption — Phase A++ of docs/SPILLBACK_PLAN.md.

    Wraps the EDFGreenWave strategy with a junction-blockage shield. Each tick,
    for every EV (sorted by mission deadline):

      - SpillbackDetector scans every outgoing edge of EVERY TLS the EV is
        approaching within VEHICLE_DISTANCE_TO_TLS (not just the immediate one).
        For each saturated outgoing — including transversal directions — issues
        a request_drain() at the TLS controlling its exit, draining bottlenecks
        before the EV arrives.
      - For each TLS where the saturated outgoing is on the EV's own path
        (signal.on_ev_path=True with signal.at_tls_id matching), the EV preempt
        at THAT specific TLS is skipped — green there cannot help while the EV's
        downstream is blocked. Other in-range TLSs still receive the EV preempt.
      - Otherwise (no saturation on EV's path at this TLS), priority_value is
        computed via compute_priority_value (ETA + severity penalty) and sent
        to GreenWaveManager.request().

    Drain requests feed the same 3-phase FSM as EV requests via request_drain(),
    with a fixed DRAIN_PRIORITY_VALUE so any EV preempts a drain immediately.
    Anti-flicker (MIN_EV_GREEN_HOLD + PREEMPT_DELTA_THRESHOLD) lives inside
    GreenWaveManager.request() and applies uniformly to both strategies.
    """

    def __init__(self, settings: Settings, sumo: SumoInterface, emergency_manager: EmergencyManager):
        self.settings = settings
        self.sumo = sumo
        self.emergency_manager = emergency_manager
        self._green_wave = GreenWaveManager(settings, sumo)
        self._detector = SpillbackDetector(settings, sumo)

    def improve(self) -> None:
        now = self.sumo.get_time()
        self._green_wave.tick(now)

        evs = sorted(
            self.emergency_manager.buffer_emergency_vehicles,
            key=lambda ev: ev.deadline,
        )

        for ev in evs:
            signals = self._detector.evaluate(ev.veh_emergency_id)

            # Drain every saturated outgoing detected (transversal + EV-path).
            # request_drain is idempotent on requester_id "drain:<edge>" so
            # repeated calls across EVs collapse harmlessly.
            for signal in signals:
                self._green_wave.request_drain(
                    tls_id=signal.downstream_tls_id,
                    saturated_edge=signal.saturated_edge,
                )

            # Per-TLS skip set: at any TLS where the EV's own outgoing is
            # saturated, the preempt is wasted — drain handles it.
            tls_to_skip = {
                s.at_tls_id for s in signals if s.on_ev_path
            }

            try:
                next_tls = self.sumo.vehicle_get_next_tls(ev.veh_emergency_id)
                current_speed = self.sumo.vehicle_get_speed(ev.veh_emergency_id)
            except self.sumo.TraCIException:
                continue

            for tls_id, _tls_index, distance, _state in next_tls:
                if distance > self.settings.VEHICLE_DISTANCE_TO_TLS:
                    continue
                if tls_id in tls_to_skip:
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
