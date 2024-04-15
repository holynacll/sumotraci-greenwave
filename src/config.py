from enum import Enum
import os
import sys
# Dynamically adjust sys.path to include the root directory where setup_environment.py is located
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import setup_environment # Carrega o ambiente de configuração

os.environ['SUMO_HOME'] = "/home/acll/workspace/sumo-env/.venv/lib/python3.11/site-packages/sumo"
# os.environ['SUMO_HOME'] = "/home/alexandre-cury/miniconda3/envs/sumo-env/lib/python3.11/site-packages/sumo"

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import traci
import traci.constants as tc
from sumolib import checkBinary  # noqa

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
        # self.PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT = 1.2
        # self.SIMULATION_END_TIME = 1600
        # self.TRIPS_REPETITION_RATE = 1
        # self.ALGORITHM = 'proposto'
        self.INTERVAL_ACCIDENT_TIME = 150
        # self.INTERVAL_CALL_EMERGENCY_VEHICLE_TIME = self.INTERVAL_ACCIDENT_TIME * self.PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT
        self.LANE_LENGTH = 150.0
        self.VEHICLE_DISTANCE_TO_TLS = 300 # Cooperative traffic management for emergency vehicles in the city of bologna, SUMO2017
        self.TLJ_PHASE_GREEN_DURATION = 5.0
        self.TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT = 7.0 # Seconds
        self.MAX_STOP_DURATION = 10 # not working
        self.MAX_SPEED_ROAD_RECOVERED = 50
        self.MIN_ARRIVAL_DISTANCE_EMERGENCY_VEHICLE_AT_THE_ACCIDENT = 15.0
        self.HOSPITAL_POS_START = 'A1B1'
        self.HOSPITAL_POS_END = 'B1A1'
        self.buffer_vehicles_accidenteds = []
        self.buffer_emergency_vehicles = []
        self.buffer_tls_on_green_wave = []
        self.buffer_tls_on_transition = []
        
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
            self.SeverityEnum.CRITICAL: 0.8,
            self.SeverityEnum.HIGH: 1.1,
            self.SeverityEnum.MEDIUM: 1.4,
            self.SeverityEnum.LOW: 1.7
        }


    # Método para atualizar configurações
    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

# Instância global a ser importada
settings = Config()
