from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional

from ...core.config import Settings
from ...core.sumo_interface import SumoInterface


@dataclass
class SpillbackSignal:
    ev_id: str
    at_tls_id: str            # TLS the EV is approaching where this outgoing was scanned
    saturated_edge: str       # an outgoing edge from at_tls_id that is saturated
    downstream_tls_id: str    # TLS controlling exit from saturated_edge (where to issue drain)
    occupancy: float          # max lane occupancy on saturated_edge (0–1)
    on_ev_path: bool          # True if saturated_edge is the EV's own outgoing edge at at_tls_id


class SpillbackDetector:
    """
    Detects saturated outgoing edges in a topological neighbourhood of the EV's
    immediate-next TLS (the root), expanding via outgoing-edge connectivity in
    BFS up to ``SPILLBACK_GRAPH_DEPTH`` hops.

    evaluate(ev_id) returns a list of SpillbackSignal, one per saturated outgoing
    edge of any TLS visited by the BFS. The strategy issues request_drain() for
    each, draining bottlenecks before the EV arrives. Signals where saturated_edge
    equals the EV's own outgoing AT a given TLS carry on_ev_path=True so the
    strategy can skip the EV preempt only at THAT TLS.

    Why BFS instead of "all TLSs on EV's path within X meters":
      - Local, deterministic neighbourhood independent of EV's path geometry.
      - Configurable depth gives a clear knob (depth=1: root only; depth=2: also
        1-hop neighbours; etc.) instead of a meters-based heuristic.
      - Depth ≥ 2 detects cascading spillback (a saturated outgoing whose own
        downstream is also blocked), which the previous path+distance approach
        missed.

    Caches are keyed by TLS / edge and built lazily; topology is assumed stable
    over the simulation lifetime.
    """

    def __init__(self, settings: Settings, sumo: SumoInterface):
        self.settings = settings
        self.sumo = sumo
        self._tls_incoming_cache: Dict[str, FrozenSet[str]] = {}
        self._tls_outgoing_cache: Dict[str, FrozenSet[str]] = {}
        self._edge_to_controlling_tls: Optional[Dict[str, str]] = None

    def evaluate(self, ev_id: str) -> List[SpillbackSignal]:
        root_tls_id = self._root_tls(ev_id)
        if root_tls_id is None:
            return []

        signals: List[SpillbackSignal] = []
        seen_outgoings: set = set()
        visited_tls: set = {root_tls_id}
        frontier: List[str] = [root_tls_id]

        for _ in range(max(1, self.settings.SPILLBACK_GRAPH_DEPTH)):
            next_frontier: List[str] = []
            for tls_id in frontier:
                ev_outgoing_edge = self._ev_outgoing_at_tls(ev_id, tls_id)
                for outgoing_edge in self._outgoing_edges(tls_id):
                    if outgoing_edge in seen_outgoings:
                        continue
                    seen_outgoings.add(outgoing_edge)
                    downstream_tls_id = self._tls_at_end_of(outgoing_edge)
                    # Always queue downstream for BFS expansion regardless of
                    # saturation — the topology, not the congestion, drives the walk.
                    if downstream_tls_id and downstream_tls_id not in visited_tls:
                        visited_tls.add(downstream_tls_id)
                        next_frontier.append(downstream_tls_id)
                    occupancy = self._max_lane_occupancy(outgoing_edge)
                    if occupancy < self.settings.SPILLBACK_OCCUPANCY_THRESHOLD:
                        continue
                    if downstream_tls_id is None:
                        continue
                    signals.append(
                        SpillbackSignal(
                            ev_id=ev_id,
                            at_tls_id=tls_id,
                            saturated_edge=outgoing_edge,
                            downstream_tls_id=downstream_tls_id,
                            occupancy=occupancy,
                            on_ev_path=(outgoing_edge == ev_outgoing_edge),
                        )
                    )
            frontier = next_frontier
            if not frontier:
                break
        return signals

    def _root_tls(self, ev_id: str) -> Optional[str]:
        try:
            next_tls_list = self.sumo.vehicle_get_next_tls(ev_id)
        except self.sumo.TraCIException:
            return None
        for entry in next_tls_list:
            if entry[2] <= self.settings.VEHICLE_DISTANCE_TO_TLS:
                return entry[0]
        return None

    # -------- helpers --------

    def _ev_outgoing_at_tls(self, ev_id: str, tls_id: str) -> Optional[str]:
        try:
            route = self.sumo.vehicle_get_route(ev_id)
            route_idx = self.sumo.vehicle_get_route_index(ev_id)
        except self.sumo.TraCIException:
            return None
        incoming_edges = self._incoming_edges(tls_id)
        passed_tls = False
        for edge in route[route_idx:]:
            if edge in incoming_edges:
                passed_tls = True
            elif passed_tls:
                return edge
        return None

    def _incoming_edges(self, tls_id: str) -> FrozenSet[str]:
        if tls_id in self._tls_incoming_cache:
            return self._tls_incoming_cache[tls_id]
        try:
            lanes = self.sumo.trafficlight_get_controlled_lanes(tls_id)
            edges = frozenset(self.sumo.lane_get_edge_id(lane) for lane in lanes)
        except self.sumo.TraCIException:
            return frozenset()
        self._tls_incoming_cache[tls_id] = edges
        return edges

    def _outgoing_edges(self, tls_id: str) -> FrozenSet[str]:
        if tls_id in self._tls_outgoing_cache:
            return self._tls_outgoing_cache[tls_id]
        try:
            links = self.sumo.trafficlight_get_controlled_links(tls_id)
        except self.sumo.TraCIException:
            return frozenset()
        edges = set()
        for signal_links in links:
            for link in signal_links:
                if not link or len(link) < 2:
                    continue
                out_lane = link[1]
                if not out_lane or out_lane.startswith(":"):
                    continue
                try:
                    edge = self.sumo.lane_get_edge_id(out_lane)
                except self.sumo.TraCIException:
                    continue
                if edge.startswith(":"):
                    continue
                edges.add(edge)
        result = frozenset(edges)
        self._tls_outgoing_cache[tls_id] = result
        return result

    def _tls_at_end_of(self, edge_id: str) -> Optional[str]:
        if self._edge_to_controlling_tls is None:
            self._build_edge_to_tls_map()
        return self._edge_to_controlling_tls.get(edge_id)  # type: ignore[union-attr]

    def _build_edge_to_tls_map(self) -> None:
        mapping: Dict[str, str] = {}
        try:
            tls_ids = self.sumo.trafficlight_get_id_list()
        except self.sumo.TraCIException:
            self._edge_to_controlling_tls = {}
            return
        for tls_id in tls_ids:
            for edge in self._incoming_edges(tls_id):
                mapping.setdefault(edge, tls_id)
        self._edge_to_controlling_tls = mapping

    def _max_lane_occupancy(self, edge_id: str) -> float:
        try:
            n_lanes = self.sumo.edge_get_lane_number(edge_id)
            return max(
                self.sumo.lane_get_last_step_occupancy(f"{edge_id}_{i}")
                for i in range(n_lanes)
            )
        except self.sumo.TraCIException:
            return 0.0
