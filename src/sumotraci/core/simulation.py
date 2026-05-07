import os
import sys
import traceback

# Setup SUMO path before importing SUMO libs
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ.get('SUMO_HOME'), 'tools')
    sys.path.append(tools)
    print(f"Pasta tools adicionada ao sys.path: {tools}")
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

from sumolib import checkBinary

from ..managers.accident_manager import AccidentManager
from ..managers.emergency_manager import EmergencyManager
from ..managers.traffic import TrafficManager
from ..utils.sumo_utils import generate_roadfile, generate_routefile, update_sumo_config
from ..utils.xml_utils import lanedata_xml_to_csv, tripinfo_xml_to_csv
from .config import Settings
from .sumo_interface import SumoInterface


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

        self.sumo = SumoInterface()
        self.accident_manager = AccidentManager(settings, self.sumo)
        self.emergency_manager = EmergencyManager(settings, self.accident_manager, self.sumo)
        self.traffic_manager = TrafficManager(settings, self.sumo, self.emergency_manager)

    def prepare_simulation(self) -> None:
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

    def run(self) -> None:
        self.prepare_simulation()

        if self.nogui:
            sumoBinary = checkBinary('sumo')
        else:
            sumoBinary = checkBinary('sumo-gui')

        self.sumo.start([
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
                self.sumo.simulation_step()
                self.emergency_manager.monitor_emergency_vehicles()

                actual_time = self.sumo.get_time()
                if actual_time < self.settings.SIMULATION_END_TIME:
                    if actual_time % 10 == 0:
                        self.accident_manager.create_accident()
                    if actual_time % 10 == 0:
                        self.emergency_manager.call_emergency_vehicle()

                self.traffic_manager.improve_traffic_for_emergency_vehicle()

                step += 1

                if (
                    actual_time > self.settings.SIMULATION_END_TIME
                    and len(self.emergency_manager.buffer_emergency_vehicles) == 0
                    and len(self.accident_manager.vehicles_accidenteds) == 0
                ):
                    break

            print('Simulation finished!')
            print(f'Saveds: {self.emergency_manager.count_saveds}')
            print(f'Unsaveds: {self.accident_manager.count_accidents - self.emergency_manager.count_saveds}')

            print('Generating CSV files...')
            saveds = self.emergency_manager.count_saveds
            un_saveds = self.accident_manager.count_accidents - saveds

            if self.tripinfo_filepath:
                tripinfo_xml_to_csv(
                    f'data/{self.tripinfo_filepath}',
                    f'data/{self.tripinfo_filepath[:-4]}.csv',
                    self.settings,
                    saveds,
                    un_saveds
                )

            if self.lanedata_filepath:
                lanedata_xml_to_csv(
                    f'data/{self.lanedata_filepath}',
                    f'data/{self.lanedata_filepath[:-4]}.csv',
                    self.settings,
                    saveds,
                    un_saveds
                )

            print('CSV files generated!')

        except Exception:
            print(traceback.format_exc())
        finally:
            self.sumo.close()

    def _should_continue_sim(self) -> bool:
        numVehicles = self.sumo.get_min_expected_number()
        return numVehicles > 0
