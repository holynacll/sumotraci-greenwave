from typing import List

from ...core.config import Settings
from ...core.sumo_interface import SumoInterface
from ...domain.schemas import GreenWaveAllocationView
from ..emergency_manager import EmergencyManager
from .strategies import make_strategy
from .strategies.base import TrafficControlStrategy


class TrafficManager:
    # Control strategy is selected via Settings.ALGORITHM.
    # See docs/MPC_PLAN.md for the full implementation roadmap.
    def __init__(self, settings: Settings, sumo: SumoInterface, emergency_manager: EmergencyManager):
        self.settings = settings
        self.sumo = sumo
        self.emergency_manager = emergency_manager
        self.strategy: TrafficControlStrategy = make_strategy(
            settings.ALGORITHM, settings, sumo, emergency_manager
        )

    @property
    def buffer_tls_on_green_wave(self) -> List[GreenWaveAllocationView]:
        return self.strategy.active_allocations()

    def improve_traffic_for_emergency_vehicle(self) -> None:
        self.strategy.improve()

    def improve_traffic_on_accidented_road(self) -> None:
        if not self.emergency_manager.buffer_emergency_vehicles:
            return

        vehicles = self.sumo.vehicle_get_id_list()

        for emergency_vehicle in self.emergency_manager.buffer_emergency_vehicles:
            accidented_road_id = emergency_vehicle.accidented_road_id

            for veh_id in vehicles:
                try:
                    type_id = self.sumo.vehicle_get_type_id(veh_id)
                except self.sumo.TraCIException:
                    continue

                if type_id != 'emergency_emergency':
                    next_roads_list = self.sumo.vehicle_get_route(veh_id)
                    if accidented_road_id in next_roads_list:
                        try:
                            current_travel_time = self.sumo.edge_get_travel_time(accidented_road_id)
                            self.sumo.edge_adapt_travel_time(accidented_road_id, current_travel_time)
                            self.sumo.vehicle_reroute_traveltime(veh_id)

                            if next_roads_list[-1] == accidented_road_id:
                                self.sumo.vehicle_set_color(veh_id, (0, 100, 100))
                            elif next_roads_list[0] == accidented_road_id:
                                self.sumo.vehicle_set_color(veh_id, (100, 0, 100))
                            else:
                                self.sumo.vehicle_set_color(veh_id, (0, 255, 0))
                        except self.sumo.TraCIException:
                            pass
