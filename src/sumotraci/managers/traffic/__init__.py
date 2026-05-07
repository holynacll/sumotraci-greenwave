# To add a new control strategy, see docs/MPC_PLAN.md §4 and §5.
from .edf import ArbitrationPolicy as ArbitrationPolicy
from .edf import EDFArbitration as EDFArbitration
from .green_wave import GreenWaveManager as GreenWaveManager
from .manager import TrafficManager as TrafficManager
