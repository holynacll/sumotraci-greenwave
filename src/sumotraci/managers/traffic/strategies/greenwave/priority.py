"""Priority policies for green-wave EV arbitration.

The priority of an EV request at a TLS is a single float — **lower wins**. How
that float is computed is a *policy slot*: exactly one policy is always active,
selected via ``Settings.GW_PRIORITY``. This is distinct from the optional
toggles (anti-flicker, pending queue, spillback) which add/remove behaviour.

  - ``DeadlinePriority`` — the EV's mission deadline, raw. A more-critical-but-
    distant EV outranks a less-critical-but-close one. (Original behaviour.)
  - ``ETAPriority`` — estimated time of arrival at the TLS plus a small severity
    penalty. Proximity dominates; severity is a fine tie-breaker.
"""

from abc import ABC, abstractmethod
from typing import Any

from .....core.config import Settings
from .....domain.enums import SeverityEnum

_VALID_PRIORITY_POLICIES = ("deadline", "eta")


class PriorityPolicy(ABC):
    @abstractmethod
    def compute(self, ev: Any, distance: float, current_speed: float) -> float:
        """Return the priority value for an EV request at a TLS (lower = more urgent)."""
        ...


class DeadlinePriority(PriorityPolicy):
    """EDF on the raw mission deadline. Ignores distance and speed."""

    def compute(self, ev: Any, distance: float, current_speed: float) -> float:
        return float(ev.deadline)


class ETAPriority(PriorityPolicy):
    """ETA at the TLS + severity penalty.

    priority_value = distance / max(current_speed, MIN_SPEED_FLOOR_FOR_ETA)
                     + SEVERITY_ETA_PENALTY[severity]

    The speed floor prevents divide-by-zero and avoids assigning unbounded ETA
    to a momentarily-stopped EV. The severity penalty is additive so that — for
    similar ETAs — a more critical mission wins, but proximity dominates when
    ETAs differ meaningfully.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def compute(self, ev: Any, distance: float, current_speed: float) -> float:
        speed = max(current_speed, self.settings.MIN_SPEED_FLOOR_FOR_ETA)
        eta = distance / speed
        try:
            penalty = self.settings.SEVERITY_ETA_PENALTY[SeverityEnum(ev.severity)]
        except (ValueError, KeyError):
            penalty = 0.0
        return eta + penalty


def make_priority_policy(name: str, settings: Settings) -> PriorityPolicy:
    if name == "deadline":
        return DeadlinePriority()
    if name == "eta":
        return ETAPriority(settings)
    raise ValueError(
        f"Unknown GW_PRIORITY: '{name}'. Accepted: {list(_VALID_PRIORITY_POLICIES)}."
    )
