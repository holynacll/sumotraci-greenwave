"""Composed green-wave strategy: 3-phase FSM engine + plugins (EDF arbitration,
priority policy slot, BFS spillback detector). Public API is `GreenWaveStrategy`;
the rest of the subpackage is internal to the algorithm.
"""

from .strategy import GreenWaveStrategy as GreenWaveStrategy
