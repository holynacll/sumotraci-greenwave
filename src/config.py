from enum import Enum
from collections import deque, namedtuple
import os
import sys
# Dynamically adjust sys.path to include the root directory where setup_environment.py is located
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# import setup_environment # Carrega o ambiente de configuração

# os.environ['SUMO_HOME'] = "/home/acll/workspace/sumotraci-greenwave/.venv/lib/python3.11/site-packages/sumo"
os.environ['SUMO_HOME'] = "/home/acll/workspace/sumo-env/.venv/lib/python3.11/site-packages/sumo"
# os.environ['SUMO_HOME'] = "/home/alexandre-cury/workspace/sumotraci-greenwave/.venv/lib/python3.11/site-packages/sumo"


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

# Enums
class SeverityEnum(str, Enum):
    CRITICAL = 'CRITICAL'
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'


class StatusEnum(str, Enum):
    ON_THE_WAY = 'ON_THE_WAY'
    IN_THE_ACCIDENT = 'IN_THE_ACCIDENT'
    TO_THE_HOSPITAL = 'TO_THE_HOSPITAL'


class Config:
    def __init__(self):
        # args to run
        self.count_saveds = 0
        self.count_accidents = 0
        self.counter_tries_to_create = 0
        self.counter_assign_random_severity = 0
        self.sum_time_to_block_create_accidents = 0.0

        self.SEED: int = 99
        self.VEHICLE_NUMBER: int = 7200 # Number of vehicles in the simulation
        self.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE = 20.0 # seconds to dispatch emergency vehicle
        self.CAR_FOLLOW_MODEL: str = 'EIDM' # Krauss or IDM or EIDM
        self.ALGORITHM = 'proposto' # default or proposto

        self.TIME_TO_RELEASE_FOR_NEW_ACCIDENTEDS_ON_THE_ROAD = 50.0 # seconds
        self.SIMULATION_END_TIME = 3600.0 # seconds
        self.TIME_TO_BLOCK_CREATE_ACCIDENTS = 60.0 # seconds to block create accidents
        self.LANE_LENGTH = 200.0 # The length of the lane in meters
        self.VEHICLE_DISTANCE_TO_TLS = 300 # Cooperative traffic management for emergency vehicles in the city of bologna, SUMO2017
        self.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT = 10.0 # GreenWave Transition time on seconds
        self.MAX_STOP_DURATION = 10 # not working
        self.SPEED_ROAD = 13.89 # The default speed on an edge (in m/s); default: 13.89
        self.MIN_ARRIVAL_DISTANCE_EMERGENCY_VEHICLE_AT_THE_ACCIDENT = 15.0 # The minimum distance to the accident for the emergency vehicle to arrive
        self.HOSPITAL_POS_START = 'A1B1'
        self.HOSPITAL_POS_END = 'B1A1'
        # self.ELIGIBLE_ACCIDENTED_ROADS = ['B2C2', 'D2C2', 'A2B2', 'C0B0', 'D1D0' ] # Roads that can have accidents
        # self.ELIGIBLE_ACCIDENTED_ROADS = ['A3A4', 'B3C3', 'D3C3', 'E1E2', 'D0C0'] # Roads that can have accidents
        self.ELIGIBLE_ACCIDENTED_ROADS = ['B3C3', 'D3C3'] # Roads that can have accidents

        self.buffer_vehicles_accidenteds = []
        self.buffer_emergency_vehicles = []
        self.buffer_tls_on_green_wave = []
        self.buffer_tls_on_transition = []
        self.buffer_schedule_to_dispatch_emergency_vehicle = []
        self.buffer_schedule_to_remove_accidented_vehicle = []
        self.RoadsFreezedToNewAccidents = namedtuple('RoadsFreezedToNewAccidents', ['road_id', 'time'])
        self.buffer_roads_freezed_to_new_accidents: list[self.RoadsFreezedToNewAccidents] = []
        self.last_roads_accidenteds = deque(maxlen=1)
        
        self.SeverityEnum = SeverityEnum
        self.StatusEnum = StatusEnum
        self.severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        self.severity_colors = {
            self.SeverityEnum.CRITICAL: (255, 0, 0, 255),
            self.SeverityEnum.HIGH: (255, 165, 0, 255),
            self.SeverityEnum.MEDIUM: (255, 255, 0, 255),
            self.SeverityEnum.LOW: (0, 255, 0, 255)
        }
        self.severity_speed_road_accidented = {
            self.SeverityEnum.CRITICAL: 0.7,
            self.SeverityEnum.HIGH: 1.0,
            self.SeverityEnum.MEDIUM: 1.3,
            self.SeverityEnum.LOW: 1.6
        }


    # Método para atualizar configurações
    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

# Instância global a ser importada
settings = Config()
