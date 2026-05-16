# Spillback-Aware EV Preemption — Implementation Plan

> **Status: DRAFT.** Supersedes `docs/MPC_PLAN.md` as the master research direction.
> The MPC document remains relevant for shared infrastructure (PuLP/CBC, glossary,
> base architecture) and for Phase B of this plan, which extends the original
> formulation. Read this file first; refer back to MPC_PLAN.md only for the
> reusable parts.

---

## 0. Quick Reference

| Item | Value |
|------|-------|
| **Research question** | Does a spillback-aware preemption strategy outperform spillback-blind preemption (default + EDF Green Wave) under heavy congestion? |
| **Hypothesis** | Yes: detecting downstream saturation and either suspending preempt or actively draining the bottleneck breaks gridlock that pure preemption cannot. |
| **Phase A — Spillback Shield (rule-based)** | Cheap, deterministic, defensible. Implementable in ~1 week. |
| **Phase B — Capacity-aware MPC (LP)** | Same S&F base as MPC_PLAN.md, plus a downstream-capacity constraint. Implementable after Phase A informs the design. |
| **Comparison baselines** | (1) `default` (SUMO stock), (2) `proposto` / `edf_greenwave` (current refactored baseline, with pending queue), (3) `shield` (Phase A), (4) `mpc_capacity` (Phase B). |

**What changed vs. MPC_PLAN.md:**
- The pure signal-split MPC with Store-and-Forward dynamics, as originally planned,
  cannot model spillback by construction. Under congestion (the regime where
  `proposto` already breaks down), it would optimize over a mis-specified model.
- Phase 0 (strategy abstraction) and the EDF + Green Wave refactor are still
  done and remain the baseline — no rewind.
- The MPC is repositioned as Phase B of this plan, with a capacity-aware
  extension. Pure-S&F MPC is no longer a planned deliverable.

---

## 1. Problem Statement

### 1.1 The deadlock

Observed in the `proposto` algorithm under heavy traffic (~4800 vehicles, 5×5 grid):

1. EV approaches TLS_X. Strategy preempts: EV's lane gets green, perpendicular gets red.
2. EV's lane is led by a non-EV vehicle V that cannot move forward because the
   downstream edge (between TLS_X and TLS_Y) is at jam density.
3. Cross-traffic at TLS_X cannot move (held red).
4. Downstream edge cannot drain because TLS_Y isn't releasing it fast enough
   (its own cycle is unaware of the saturation).
5. Result: EV is stuck behind V, V cannot move, perpendicular flow is locked,
   no traffic flows through the corridor. Gridlock persists until SUMO's
   `MAX_STOP_DURATION` removes stuck vehicles by timeout.

### 1.2 Why the current `proposto` cannot fix this

- The Green Wave is **reactive and local** to each TLS the EV is currently near.
  No knowledge of downstream conditions.
- The arbitration signal is the EV's deadline, not the achievability of green.
  Green is granted even when the lane has zero discharge capacity.

### 1.3 Why the originally-planned MPC (S&F) cannot fix this

- Store-and-Forward queue dynamics: `q(t+1) = q(t) + arr − sat·green_share`.
- Implicit assumption: a green lane discharges at saturation flow.
- Under spillback, *effective* discharge is bounded by downstream residual capacity,
  which S&F does not represent. The LP would happily allocate green to a saturated
  approach because in its model, the queue still drops by `sat·green_share`.
- See MPC_PLAN.md §2 (glossary, CTM entry) for the original acknowledgement that
  spillback is out of scope for S&F.

### 1.4 Reframing

Old framing: *"How do we optimize the green-time allocation across an EV's path?"*

New framing: **"When is preemption productive, and when should the controller
drain a saturated downstream link instead?"**

The trade-off is between:
- **Holding green for the EV** (good when the EV can actually move forward),
- **Releasing or draining elsewhere** (good when the EV cannot move forward
  because of downstream gridlock; releasing perpendicular flow lets the
  network unwind).

---

## 2. Design Decisions (Locked)

### 2.1 Two phases, in order

- **Phase A** — rule-based spillback shield over the existing `EDFGreenWaveStrategy`.
- **Phase B** — capacity-aware MPC, designed *after* Phase A's empirical results.

Phase A is the load-bearing experiment. If a simple rule-based shield already
breaks the gridlock and improves the Pareto, Phase B becomes a "smarter optimizer"
extension. If Phase A alone is insufficient, Phase B has a clear gap to address.

### 2.2 Detection by lane occupancy

Spillback signal: the *first downstream edge* the EV will travel after the
current TLS has lane occupancy above a configurable threshold.

- TraCI source: `lane.getLastStepOccupancy(lane_id)` (returns 0–1) or
  `lane.getLastStepHaltingNumber(lane_id) / capacity`.
- Threshold default: `SPILLBACK_OCCUPANCY_THRESHOLD = 0.7`.
- Aggregation: take the max across all lanes of the downstream edge (any saturated
  lane is enough, since a stuck vehicle in one lane cascades).

### 2.3 Two simultaneous actions when spilled

When detected for an (EV, current TLS) pair:

1. **Suspend preempt at current TLS.** Don't call `request()` for this TLS.
   Let the normal program run so cross-traffic can flow.
2. **Drain at downstream TLS.** Call a new `request_drain()` on the
   `GreenWaveManager` targeting the saturated edge, at the TLS that controls
   its exit. Reuses the existing FSM (CLEARING → GREEN → EXIT_YELLOW) but with
   the saturated edge as the priority edge instead of an EV's lane.

### 2.4 Generalize `GreenWaveManager.request()` to accept an explicit priority edge

The current API derives `priority_edge` from the EV's route via
`_first_route_edge_at_tls`. To support drain, refactor `request()` to take
`priority_edge` directly. The strategy resolves the edge:
- For EV preempt: `priority_edge = first_route_edge_at_tls(ev_id, tls_id)`.
- For drain: `priority_edge = saturated_edge`.

Same FSM, same EDF arbitration, same pending-queue. The manager stops being
EV-specific and becomes a generic "grant green to this edge at this TLS"
service. Drain requests use a synthetic `requester_id` like `"drain:<edge_id>"`
and a deadline derived from how long the saturation has persisted.

### 2.5 Drain priority

Drain requests have lower base priority than EV requests (later deadline).
If an EV arrives at the downstream TLS while a drain is active, EDF lets the
EV preempt the drain. Implementation: `drain_deadline = sim_time + DRAIN_HORIZON`
(default `DRAIN_HORIZON = 60s`).

---

## 3. Phase A — Spillback Shield

**Goal:** new strategy `SpillbackAwareEDFGreenWaveStrategy` (or a wrapper) that
adds spillback detection + drain on top of the existing `EDFGreenWaveStrategy`.

**Estimated effort:** ~1 week including tests and a Pareto run.

### 3.1 New components

```
src/sumotraci/managers/traffic/
├── green_wave.py                       # generalized: priority_edge, request_drain
├── spillback.py                        # NEW: SpillbackDetector
└── strategies/
    ├── edf_greenwave.py                # unchanged (still the baseline)
    └── spillback_shield.py             # NEW: SpillbackAwareEDFGreenWaveStrategy
```

### 3.2 `SpillbackDetector`

```python
@dataclass
class SpillbackSignal:
    ev_id: str
    saturated_edge: str
    downstream_tls_id: str  # the TLS controlling saturated_edge's exit
    occupancy: float         # observed value at detection time

class SpillbackDetector:
    def __init__(self, settings: Settings, sumo: SumoInterface): ...

    def evaluate(self, ev_id: str) -> Optional[SpillbackSignal]:
        """
        Returns a SpillbackSignal if the EV's first downstream edge (after its
        next TLS) is saturated above SPILLBACK_OCCUPANCY_THRESHOLD. Otherwise
        None. Caches the SUMO topology lookups.
        """
```

Implementation notes:
- Identify the EV's *next* TLS via `vehicle.getNextTLS(ev_id)[0]` (closest one in range).
- Identify the downstream edge via `vehicle.getRoute(ev_id)[route_index + 1]` (the edge after the one the EV is currently on).
  - Subtle: if the EV is on edge E_k and approaching TLS at the head of E_k, the downstream edge is E_{k+1}. Verify with `getNextTLS` distance.
- Identify the downstream TLS by walking the route forward and querying
  `vehicle.getNextTLS(ev_id)` for the second TLS, or by network introspection
  on the route edge.
- Lane occupancy: max across `lane.getLastStepOccupancy()` for each lane of
  the downstream edge.

### 3.3 `GreenWaveManager` API changes

Generalize `request()`:

```python
def request(
    self,
    tls_id: str,
    requester_id: str,    # EV id, or "drain:<edge>" for drain
    priority_edge: str,   # explicit edge to grant green to
    deadline: float,
    severity: str = "",
) -> bool: ...
```

Add a thin convenience wrapper:

```python
def request_drain(self, tls_id: str, saturated_edge: str, now: float) -> bool:
    return self.request(
        tls_id=tls_id,
        requester_id=f"drain:{saturated_edge}",
        priority_edge=saturated_edge,
        deadline=now + self.settings.DRAIN_DEADLINE_HORIZON,
        severity="DRAIN",
    )
```

Internally, `_Allocation.veh_emergency_id` becomes `requester_id` (semantic
rename, no schema break since the field is internal). The `_ev_has_passed`
exit condition is replaced by a more general "is the green still useful?"
check:
- For EV requesters: existing logic (EV no longer in `getNextTLS` within range).
- For drain requesters: lane occupancy of `priority_edge` dropped below
  `SPILLBACK_OCCUPANCY_RELEASE_THRESHOLD` (default 0.4 — hysteresis below the
  detection threshold of 0.7).

### 3.4 `SpillbackAwareEDFGreenWaveStrategy`

```python
class SpillbackAwareEDFGreenWaveStrategy(TrafficControlStrategy):
    def __init__(self, settings, sumo, emergency_manager):
        self._green_wave = GreenWaveManager(settings, sumo)
        self._detector = SpillbackDetector(settings, sumo)
        self._emergency_manager = emergency_manager
        self._sumo = sumo
        self._settings = settings

    def improve(self) -> None:
        now = self._sumo.get_time()
        self._green_wave.tick(now)

        for ev in sorted(self._emergency_manager.buffer_emergency_vehicles,
                         key=lambda e: e.deadline):
            signal = self._detector.evaluate(ev.veh_emergency_id)
            if signal is not None:
                # Spillback: skip current-TLS preempt, drain downstream instead.
                self._green_wave.request_drain(
                    tls_id=signal.downstream_tls_id,
                    saturated_edge=signal.saturated_edge,
                    now=now,
                )
                continue  # do not preempt current TLS for this EV

            # Normal preempt at all TLS in range
            try:
                next_tls = self._sumo.vehicle_get_next_tls(ev.veh_emergency_id)
            except self._sumo.TraCIException:
                continue
            for tls_id, _idx, dist, _state in next_tls:
                if dist > self._settings.VEHICLE_DISTANCE_TO_TLS:
                    continue
                priority_edge = self._green_wave._first_route_edge_at_tls(
                    ev.veh_emergency_id,
                    self._sumo.trafficlight_get_controlled_lanes(tls_id),
                )
                if priority_edge is None:
                    continue
                self._green_wave.request(
                    tls_id=tls_id,
                    requester_id=ev.veh_emergency_id,
                    priority_edge=priority_edge,
                    deadline=ev.deadline,
                    severity=ev.severity,
                )

    def active_allocations(self) -> List[GreenWaveAllocationView]:
        return self._green_wave.allocations
```

Register as `"shield"` in `make_strategy()`. Add `Settings.ALGORITHM` accepted
value.

### 3.5 New Settings

```python
SPILLBACK_OCCUPANCY_THRESHOLD: float = 0.7   # detect saturation
SPILLBACK_OCCUPANCY_RELEASE_THRESHOLD: float = 0.4  # release drain (hysteresis)
DRAIN_DEADLINE_HORIZON: float = 60.0         # how far ahead drain "wants" green
DRAIN_MAX_DURATION: float = 30.0             # safety cap on total drain time per request
```

### 3.6 Acceptance criteria

- [ ] `uv run python -m sumotraci.main --algorithm shield --simulation-end-time 900` runs end-to-end.
- [ ] At least one drain request fires under default scenario congestion (verifiable via debug log or new print).
- [ ] On 10 seeds, **median EV travel time is no worse than `proposto`**, AND on the 3 worst-congestion seeds (where `proposto` shows gridlock), shield strictly improves median EV travel time by >= 10%.
- [ ] Cross-traffic mean delay (non-EV) is **no worse** than `proposto`. Ideally lower in congested seeds.
- [ ] No TLS left in undefined state at simulation end.
- [ ] Lint + smoke imports pass.

### 3.7 Anti-patterns

- ❌ Don't change the EDF `proposto` strategy itself. Phase A is additive.
- ❌ Don't model spillback "more accurately" with kinematics; occupancy is enough for a heuristic.
- ❌ Don't tune thresholds per-seed. The 4 settings (threshold, release, horizon, max duration) are fixed per-experiment.
- ❌ Don't add new TraCI calls into hot paths without caching topology. SpillbackDetector should cache `tls_id → saturated_edge → downstream_tls_id` mappings derived from the EV's route once per route-step.

---

## 4. Phase B — Capacity-Aware MPC (Sketch)

**Goal:** replace the rule-based shield with an LP that has the spillback
constraint baked in. Implementable after Phase A's results inform what the
LP actually needs to express.

**Estimated effort:** ~2–3 weeks.

### 4.1 Same base as MPC_PLAN.md

- Solver: PuLP + CBC (LP).
- Decision variables: continuous green fractions `x[i, p, t] ∈ [0, 1]`.
- Spatial scope: TLS on EV's remaining route (extended to include the *next*
  TLS downstream of each preempt point, so capacity coupling is observable).
- Re-plan cadence: every 5 simulated seconds.
- Horizon: 30 simulated seconds.

### 4.2 New: capacity coupling constraint

For each upstream lane `l` controlled by TLS `i`, identify the downstream
lane `l'` that `l` discharges into (via `traci.lane.getLinks(l)` at startup).
At step `t`, the actual discharge from `l` cannot exceed the residual capacity
of `l'`:

```
∀ i, l, t:   sat[l] · dt · Σ_p phase_serves(p, l) · x[i, p, t]
              ≤ jam_capacity[l'] − q[downstream_tls_of(l'), l', t]
```

Where:
- `jam_capacity[l'] ≈ lane_length × jam_density` (jam density ~ 150 veh/km).
- `q[..., l', t]` is the predicted queue on `l'` at step `t`, already a
  decision variable in the original MPC.

This is **linear** in `x` and `q`, so the LP stays tractable.

### 4.3 New: drain term in the objective

To match Phase A's "drain" behaviour, augment the objective:

```
minimize    Σ_i d_ev[i]
          + α · Σ_{i, l, t} q[i, l, t] · dt
          + β · Σ_{(i, l) saturated} max(0, q[i, l, t] − release_threshold) · dt
```

The third term penalizes any lane whose queue exceeds the release threshold,
encouraging the LP to allocate green to drain it. `β` is tuned alongside `α`
in the Pareto sweep.

### 4.4 Open questions before implementation

- How sensitive is the LP size to extending scope to "next TLS downstream"?
  Quick estimate: from ~3–7 TLS per EV in MPC_PLAN.md, growing to ~6–12. LP
  vars roughly double. Still solvable in <1s with CBC.
- How accurate is the static `jam_capacity` constant? Maybe needs per-lane
  calibration from a warmup run.
- Does the LP formulation need to model upstream/downstream coupling between
  *different* TLS in the scope (currently each TLS's lanes are independent
  except via the new capacity constraint)?

These resolve after Phase A reveals what congestion patterns actually break
`proposto`.

### 4.5 Acceptance criteria (placeholder)

To be finalized after Phase A. Likely:
- LP solves in <1s.
- Beats Phase A shield on at least 5 of 10 seeds for both EV travel time and
  cross-traffic delay.

---

## 5. Experiments

### 5.1 Strategy matrix

| Algorithm | Description |
|-----------|-------------|
| `default` | SUMO stock |
| `proposto` | Reactive EDF + Green Wave + pending queue (current refactored baseline) |
| `shield` | Phase A: proposto + spillback detection + downstream drain |
| `mpc_capacity` | Phase B: LP with capacity coupling |

### 5.2 Seeds & vehicle counts

- All 10 seeds in `Settings.SEEDS`.
- Vehicle counts: 4800 (default) and 6000 (heavy congestion stress).
- Total runs: 4 × 10 × 2 = 80.

### 5.3 Metrics

Per run, append to `data/spillback_summary.csv`:
- `algo, seed, vehicle_number`
- `ev_mean_travel_time, ev_median, ev_p95`
- `others_mean_delay, others_p95`
- `gridlock_events` — count of (TLS, edge) pairs that hit `MAX_STOP_DURATION` at least once
- `saveds, unsaveds`

### 5.4 Plots

- **Pareto** (already in MPC_PLAN.md §9.4): EV travel time × non-EV delay, one
  point per (algorithm, vehicle_count) averaged across seeds.
- **Gridlock count**: bar chart, `gridlock_events` per algorithm. The headline
  for the "spillback-aware vs spillback-blind" framing.

---

## 6. Out of Scope

- Multi-EV coordination beyond what arbitration handles.
- CTM (full kinematic model). The capacity constraint in Phase B is *enough*
  to capture spillback for our use case; CTM is a future-work upgrade.
- Dynamic EV rerouting (could be a parallel contribution but not part of this plan).
- Calibrated jam density per real-world data. Use SUMO defaults.
- Adaptive thresholds (`SPILLBACK_OCCUPANCY_THRESHOLD` learned from data).

---

## 7. Status

- [x] Phase 0 — Strategy abstraction (from MPC_PLAN.md, done)
- [x] EDF Green Wave refactor + pending queue
- [ ] Phase A — Spillback shield
  - [ ] SpillbackDetector
  - [ ] GreenWaveManager `request_drain` + generalized `priority_edge`
  - [ ] SpillbackAwareEDFGreenWaveStrategy
  - [ ] Pareto experiment vs. `default` and `proposto`
- [ ] Phase B — Capacity-aware MPC
  - [ ] LP formulation finalized post-Phase-A
  - [ ] Implementation
  - [ ] Pareto experiment vs. all baselines
- [ ] Paper draft
