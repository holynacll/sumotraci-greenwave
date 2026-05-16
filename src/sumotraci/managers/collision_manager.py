from typing import Set

from ..core.config import Settings
from ..core.sumo_interface import SumoInterface

_EV_VEHICLE_TYPE_ID = "emergency_emergency"


class CollisionManager:
    """Selective collision cleanup that preserves the EV in simulation.

    Pairs with the SUMO flag ``--collision.action warn``: SUMO only logs
    collisions and leaves both participants in the sim. This manager reads
    ``getCollidingVehiclesIDList()`` each step and:

    - removes civilian participants (so they don't block the EV's path);
    - does NOT remove EVs (so subsequent TraCI calls and the EmergencyManager
      keep working);
    - counts ``ev_collisions`` separately from civilian-civilian collisions.

    Exposed metrics:

    - ``total_vehicles_involved``: cumulative count of *civilians* removed
      due to collisions.
    - ``ev_collisions``: number of distinct collision events in which an EV
      was a participant.
    - ``collision_steps``: number of simulation steps in which at least one
      new collision was registered.
    """

    def __init__(self, settings: Settings, sumo: SumoInterface):
        self.settings = settings
        self.sumo = sumo
        self.total_vehicles_involved: int = 0
        self.ev_collisions: int = 0
        self.collision_steps: int = 0
        self._seen_civilian_ids: Set[str] = set()

    def _is_ev(self, vid: str) -> bool:
        try:
            return self.sumo.vehicle_get_type_id(vid) == _EV_VEHICLE_TYPE_ID
        except Exception:
            return False

    def tick(self) -> None:
        colliding = self.sumo.simulation_get_colliding_vehicles_id_list()
        if not colliding:
            return

        ev_present = any(self._is_ev(vid) for vid in colliding)
        civilians = [vid for vid in colliding if not self._is_ev(vid)]
        new_civilians = [vid for vid in civilians if vid not in self._seen_civilian_ids]
        if not new_civilians:
            return

        self._seen_civilian_ids.update(new_civilians)
        self.collision_steps += 1
        if ev_present:
            self.ev_collisions += 1

        for vid in new_civilians:
            try:
                self.sumo.vehicle_remove(vid)
                self.total_vehicles_involved += 1
            except Exception:
                # Vehicle may have already been removed by SUMO between the
                # collision report and our manual cleanup; treat as a no-op.
                pass
