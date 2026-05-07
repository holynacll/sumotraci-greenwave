from typing import Protocol


class ArbitrationPolicy(Protocol):
    """Decides whether a new requester may preempt the current TLS allocation."""

    def can_preempt(self, existing_deadline: float, new_deadline: float) -> bool: ...


class EDFArbitration:
    """Earliest Deadline First. New requester wins ties."""

    def can_preempt(self, existing_deadline: float, new_deadline: float) -> bool:
        return new_deadline <= existing_deadline
