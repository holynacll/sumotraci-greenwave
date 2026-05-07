from typing import List

from ....domain.schemas import GreenWaveAllocationView
from .base import TrafficControlStrategy


class NoOpStrategy(TrafficControlStrategy):
    """Used when ALGORITHM='default'. Makes no changes to traffic lights."""

    def improve(self) -> None:
        return

    def active_allocations(self) -> List[GreenWaveAllocationView]:
        return []
