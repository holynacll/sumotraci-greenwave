from typing import List

from ...domain.schemas import GreenWaveTLS


class EDFManager:
    """
    Manages the Earliest Deadline First (EDF) prioritization logic for traffic lights.
    """
    def __init__(self):
        pass

    def check_conflict(
        self,
        tls_id: str,
        current_vehicle_id: str,
        current_deadline: float,
        active_allocations: List[GreenWaveTLS]
    ) -> bool:
        """
        Check if the TLS is already allocated to a vehicle with a higher priority (earlier deadline).
        Returns True if there is a conflict that prevents utilization (i.e. occupied by higher priority).
        Returns False if available or occupied by lower priority (preemption allowed).
        """
        for allocation in active_allocations:
            if allocation.tls_id == tls_id:
                # If it's the same vehicle, no conflict
                if allocation.veh_emergency_id == current_vehicle_id:
                    return False

                # If the existing allocation has an earlier (smaller) deadline, it has higher priority.
                # We cannot preempt it.
                if allocation.deadline < current_deadline:
                    return True

                # If we are here, there is an allocation but it has a LATER deadline (lower priority).
                # We CAN preempt it. effectively "No Conflict" for the current requester,
                # but implicit cleanup needed for the preempted one (handled by Orchestrator or GreenWaveManager).
                return False

        # No allocation found for this TLS
        return False
