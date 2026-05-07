from abc import ABC, abstractmethod
from typing import List

from ....domain.schemas import GreenWaveAllocationView


class TrafficControlStrategy(ABC):
    @abstractmethod
    def improve(self) -> None:
        """Called every simulation step. Implementations may early-return."""
        ...

    @abstractmethod
    def active_allocations(self) -> List[GreenWaveAllocationView]:
        """Returns current active TLS allocations for external readers."""
        ...
