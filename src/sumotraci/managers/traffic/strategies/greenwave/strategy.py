"""Unified, config-composed green-wave strategy.

Replaces the former `fsm_greenwave`, `edf_greenwave` and `shield` strategy
classes. A single engine (`GreenWaveManager`, 3-phase FSM + highlight) whose
improvements are composed via `Settings`:

  - ``GW_PRIORITY``       — priority policy slot: "deadline" or "eta".
  - ``GW_EV_PREEMPTION``  — toggle: allow a higher-priority EV to preempt a TLS
                            already allocated to another EV (only in EV_GREEN,
                            graceful). Off = rigorous control (hand-off only).
  - ``GW_ANTIFLICKER``    — hysteresis on EV-EV preemption (only effective when
                            GW_EV_PREEMPTION is on): MIN_EV_GREEN_HOLD +
                            PREEMPT_DELTA_THRESHOLD.
  - ``GW_SPILLBACK``      — toggle: BFS spillback detector + drain requests.

The pending-allocation queue with hand-off is intrinsic to the engine (always on):
losers of arbitration queue on the holder and take over at the natural hand-off.

The combinations cover the full ablation study; see docs/ALGORITHMS.md.
Operational improvements (CollisionManager, scenario defaults) are global and
apply regardless of which combination is selected.
"""

from typing import Optional

from .....core.config import Settings
from .....core.sumo_interface import SumoInterface
from .....domain.schemas import GreenWaveAllocationView
from ....emergency_manager import EmergencyManager
from ..base import TrafficControlStrategy
from .edf import EDFArbitration
from .engine import GreenWaveManager, first_route_edge_at_tls
from .priority import PriorityPolicy, make_priority_policy
from .spillback import SpillbackDetector


class GreenWaveStrategy(TrafficControlStrategy):
    def __init__(
        self,
        settings: Settings,
        sumo: SumoInterface,
        emergency_manager: EmergencyManager,
    ):
        self.settings = settings
        self.sumo = sumo
        self.emergency_manager = emergency_manager

        self._priority: PriorityPolicy = make_priority_policy(
            settings.GW_PRIORITY, settings
        )

        # Anti-flicker toggle: zero both knobs when off.
        effective_delta = (
            settings.PREEMPT_DELTA_THRESHOLD if settings.GW_ANTIFLICKER else 0.0
        )
        effective_hold = settings.MIN_EV_GREEN_HOLD if settings.GW_ANTIFLICKER else 0.0

        self._green_wave = GreenWaveManager(
            settings,
            sumo,
            arbitration=EDFArbitration(delta=effective_delta),
            min_ev_green_hold=effective_hold,
            ev_preemption=settings.GW_EV_PREEMPTION,
        )

        self._detector: Optional[SpillbackDetector] = (
            SpillbackDetector(settings, sumo) if settings.GW_SPILLBACK else None
        )

    def improve(self) -> None:
        self._green_wave.tick(self.sumo.get_time())

        evs = sorted(
            self.emergency_manager.buffer_emergency_vehicles,
            key=lambda ev: ev.deadline,
        )

        for ev in evs:
            tls_to_skip: set = set()
            if self._detector is not None:
                signals = self._detector.evaluate(ev.veh_emergency_id)
                # Drain every saturated outgoing detected. request_drain is
                # idempotent on requester_id "drain:<edge>".
                for signal in signals:
                    self._green_wave.request_drain(
                        tls_id=signal.downstream_tls_id,
                        saturated_edge=signal.saturated_edge,
                    )
                # Skip the EV preempt only at TLSs where the EV's own outgoing
                # is saturated — green there is wasted, the drain handles it.
                tls_to_skip = {s.at_tls_id for s in signals if s.on_ev_path}

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
                    controlled_lanes = self.sumo.trafficlight_get_controlled_lanes(
                        tls_id
                    )
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
                    priority_value=self._priority.compute(ev, distance, current_speed),
                    severity=ev.severity,
                )

    def active_allocations(self) -> list[GreenWaveAllocationView]:
        return self._green_wave.allocations
