import os
import sys

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ.get('SUMO_HOME'), 'tools')
    sys.path.append(tools)
    print(f"Pasta tools adicionada ao sys.path: {tools}")
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

try:
    import traci
    import traci.constants as tc
    from sumolib import checkBinary  # noqa
    print("traci importado com sucesso.")
except ModuleNotFoundError as e:
    print(f"Erro ao importar módulo: {e}")
    sys.exit("Certifique-se de que o SUMO e o Traci estão instalados corretamente e o caminho do SUMO_HOME está correto.")

import traceback

from ..managers.accident_manager import AccidentManager
from ..managers.emergency_manager import EmergencyManager
from ..managers.traffic_manager import TrafficManager
from ..utils.sumo_utils import generate_roadfile, generate_routefile, update_sumo_config
from ..utils.xml_utils import lanedata_xml_to_csv, tripinfo_xml_to_csv
from .config import Settings


class SimulationEngine:
    def __init__(self, settings: Settings, nogui: bool = False,
                 sumocfg_path: str = "data/config.sumocfg",
                 road_filepath: str = "road.net.xml",
                 route_filepath: str = "route.rou.xml",
                 trips_filepath: str = "data/trips.trips.xml",
                 tripinfo_filepath: str = "tripinfo.xml",
                 lanedata_filepath: str = "lanedata.xml",
                 summary_filepath: str = "summary.xml"):
        self.settings = settings
        self.nogui = nogui
        self.sumocfg_path = sumocfg_path
        self.road_filepath = road_filepath
        self.route_filepath = route_filepath
        self.trips_filepath = trips_filepath
        self.tripinfo_filepath = tripinfo_filepath
        self.lanedata_filepath = lanedata_filepath
        self.summary_filepath = summary_filepath

        self.accident_manager = AccidentManager(settings)
        self.emergency_manager = EmergencyManager(settings, self.accident_manager)
        self.traffic_manager = TrafficManager(settings)

    def prepare_simulation(self):
        print('Generating configuration files...')
        road_file_generated = generate_roadfile(road_filepath=self.road_filepath, settings=self.settings)
        generate_routefile(
            route_filepath=self.route_filepath,
            trips_filepath=self.trips_filepath,
            road_filepath=road_file_generated,
            seed=self.settings.SEED,
            settings=self.settings
        )
        update_sumo_config(
            summary_filename=self.summary_filepath,
            route_filename=self.route_filepath,
            new_sumoconfig_filepath=self.sumocfg_path,
        )

    def run(self):
        self.prepare_simulation()

        if self.nogui:
            sumoBinary = checkBinary('sumo')
        else:
            sumoBinary = checkBinary('sumo-gui')

        traci.start([
            sumoBinary,
            "-c", self.sumocfg_path,
            "--lateral-resolution", str(self.settings.LATERAL_RESOLUTION),
            "--device.bluelight.reactiondist", str(self.settings.BLUE_LIGHT_REACTION_DIST),
            "--tripinfo-output", f'data/{self.tripinfo_filepath}',
            "--lanedata-output", f'data/{self.lanedata_filepath}',
            "-S",
            "-Q",
        ])

        print('Running simulation...')
        print(f'Seed: {self.settings.SEED}')
        print(f'Time to block create accidents: {self.settings.TIME_TO_BLOCK_CREATE_ACCIDENTS}')
        print(f'Algorithm: {self.settings.ALGORITHM}')

        step = 0
        try:
            self.accident_manager.generate_elegible_accidented_roads_and_hospital_positions()

            while self._should_continue_sim():
                traci.simulationStep()
                self.emergency_manager.monitor_emergency_vehicles()

                actual_time = traci.simulation.getTime()
                if actual_time < self.settings.SIMULATION_END_TIME:
                    if actual_time % 10 == 0:
                        self.accident_manager.create_accident()
                    if actual_time % 10 == 0:
                        self.emergency_manager.call_emergency_vehicle()

                if self.settings.ALGORITHM == 'proposto':
                    self.traffic_manager.improve_traffic_for_emergency_vehicle()
                    # Note: Original main.py calls improve_traffic_for_emergency_vehicle (queue 13)
                    # It also imported optimization_reroute but didn't call improve_traffic_on_accidented_road
                    # in the loop. Checking if I should add it.
                    # Original main.py Line 14 imported `improve_traffic_on_accidented_road`
                    # but line 49 only calls `improve_traffic_for_emergency_vehicle`.
                    # I will stick to main.py logic. The reroute logic might be unused or implicitly called?
                    # Ah, traffic_manager.improve_traffic_for_emergency_vehicle only does green wave.
                    # optimization_reroute was imported but NOT used in the provided main.py loop.
                    # I will keep it available in TrafficManager but won't call it unless requested or found otherwise.

                step += 1

                if (
                    actual_time > self.settings.SIMULATION_END_TIME
                    and len(self.settings.buffer_emergency_vehicles) == 0
                    and len(self.settings.buffer_vehicles_accidenteds) == 0
                ):
                    break

            print('Simulation finished!')
            print(f'Saveds: {self.settings.count_saveds}')
            print(f'Unsaveds: {self.settings.count_accidents - self.settings.count_saveds}')

            print('Generating CSV files...')
            if self.tripinfo_filepath:
                tripinfo_xml_to_csv(
                    f'data/{self.tripinfo_filepath}',
                    f'data/{self.tripinfo_filepath[:-4]}.csv',
                    self.settings
                )

            if self.lanedata_filepath:
                lanedata_xml_to_csv(
                    f'data/{self.lanedata_filepath}',
                    f'data/{self.lanedata_filepath[:-4]}.csv',
                    self.settings
                )

            # emission_xml_to_csv? It wasn't in original list of calls in run(),
            # but if implemented I should check if it needs update.
            # Assuming only these two are called here based on context.
            print('CSV files generated!')

        except Exception:
            print(traceback.format_exc())
        finally:
            traci.close()

    def _should_continue_sim(self):
        numVehicles = traci.simulation.getMinExpectedNumber()
        return numVehicles > 0
