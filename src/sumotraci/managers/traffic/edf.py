from typing import Protocol


class ArbitrationPolicy(Protocol):
    """Decides whether a new requester may preempt the current TLS allocation.

    Both arguments are priority values where lower = more urgent (wins arbitration).
    For EVs, this is `ETA_at_TLS + severity_penalty`; for drains it's a fixed value.
    """

    def can_preempt(self, existing_priority: float, new_priority: float) -> bool: ...


class EDFArbitration:
    """Earliest-priority-first with anti-flicker delta.

    A new requester preempts only if its priority_value is at least `delta`
    smaller than the holder's. Setting `delta=0` reproduces classic EDF where
    new wins on ties.
    """

    def __init__(self, delta: float = 0.0):
        self.delta = delta

    def can_preempt(self, existing_priority: float, new_priority: float) -> bool:
        return new_priority + self.delta <= existing_priority
