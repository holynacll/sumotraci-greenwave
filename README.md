# SumoTraCI Greenwave

Simulation framework for evaluating emergency-vehicle (EV) preemption strategies
on a SUMO + TraCI traffic micro-simulation. The codebase compares three traffic-light
control strategies on the same scenario:

- **`default`** — SUMO's stock signal program (no preemption).
- **`proposto` / `edf_greenwave`** — reactive Green Wave with EDF arbitration and a
  per-TLS pending queue (the current paper baseline).
- **`shield`** — spillback-aware preemption: detects downstream saturation and
  drains the bottleneck instead of forcing green for the EV (planned; see
  [`docs/SPILLBACK_PLAN.md`](docs/SPILLBACK_PLAN.md) Phase A).
- **`mpc_capacity`** — capacity-aware Model Predictive Control over a rolling
  horizon (planned; see [`docs/SPILLBACK_PLAN.md`](docs/SPILLBACK_PLAN.md)
  Phase B). The pure-S&F variant in [`docs/MPC_PLAN.md`](docs/MPC_PLAN.md) is
  superseded.

Built with a modular architecture, Pydantic settings, and modern tooling (`uv`, `typer`).

## Prerequisites

- **Python 3.11+**
- **[Eclipse SUMO](https://eclipse.dev/sumo/)** (>= 1.21.0)
- **[uv](https://github.com/astral-sh/uv)** (High-performance Python package installer)

## Installation

1.  **Install dependencies using `uv`**:
    ```bash
    uv pip install -e .
    ```
    *This installs the project in editable mode along with runtime dependencies.*

2.  **Install development dependencies (optional)**:
    ```bash
    uv pip install -e .[dev]
    # OR explicitly
    uv pip install pytest ruff mypy types-requests
    ```

## Usage

### 1. Set SUMO_HOME
You must have the `SUMO_HOME` environment variable set to your SUMO installation directory.

```bash
export SUMO_HOME=/path/to/your/sumo
# Example:
# export SUMO_HOME=/usr/share/sumo
# export SUMO_HOME=$(pwd)/.venv/lib/python3.11/site-packages/sumo
```

### 2. Run the Simulation
Run the simulation using the new CLI entry point:

```bash
uv run python -m sumotraci.main --nogui --simulation-end-time 1000
```

**Common Options:**
-   `--nogui`: Run without the SUMO GUI (headless mode).
-   `--simulation-end-time FLOAT`: Stop the simulation after X seconds.
-   `--time-block-accident FLOAT`: Time interval to block accident creation.
-   `--vehicle-number INT`: Total number of vehicles to simulate.
-   `--algorithm STR`: Traffic-control strategy. Accepted: `default`, `proposto`,
    `edf_greenwave` (alias for `proposto`), `shield` (planned — see
    [`docs/SPILLBACK_PLAN.md`](docs/SPILLBACK_PLAN.md) Phase A), `mpc_capacity`
    (planned — see [`docs/SPILLBACK_PLAN.md`](docs/SPILLBACK_PLAN.md) Phase B).
-   `--help`: Show all available options.

**Example with GUI:**
```bash
uv run python -m sumotraci.main --vehicle-number 100 --simulation-end-time 500
```

## Project Structure

The source code is located in `src/sumotraci/` and is organized as follows:

-   **`main.py`**: CLI entry point and application bootstrap.
-   **`core/`**: Core system logic.
    -   `simulation.py`: Main `SimulationEngine` class.
    -   `config.py`: `Settings` management using Pydantic.
    -   `sumo_interface.py`: Typed wrapper around TraCI calls.
-   **`managers/`**: Business logic modules.
    -   `accident_manager.py`: Accident lifecycle.
    -   `emergency_manager.py`: EV dispatch and monitoring.
    -   `traffic/`: Traffic-control package.
        -   `manager.py`: `TrafficManager` — public facade; delegates to a strategy.
        -   `green_wave.py`: `GreenWaveManager` — 3-phase preemption FSM with pending queue.
        -   `edf.py`: `EDFArbitration` policy + `ArbitrationPolicy` Protocol.
        -   `strategies/`: One module per strategy.
            -   `base.py` — `TrafficControlStrategy` ABC.
            -   `default.py` — `NoOpStrategy` (no preemption).
            -   `edf_greenwave.py` — `EDFGreenWaveStrategy` (current `proposto`).
            -   `__init__.py` — `make_strategy()` factory.
-   **`domain/`**: Pydantic schemas (`GreenWaveAllocationView`, `EmergencyVehicle`, …)
    and enums (`SeverityEnum`, `StatusEnum`).
-   **`utils/`**: SUMO scenario generation and XML→CSV post-processing.

## Traffic Control Strategies

Strategy is selected at startup via `--algorithm` and dispatched by `make_strategy()`
in `managers/traffic/strategies/__init__.py`. To add a new strategy, implement
`TrafficControlStrategy` and register it in the factory.

### `default` — `NoOpStrategy`

No traffic-light intervention. SUMO's programmed cycles run untouched. EVs get no
priority. Used as the comparison baseline.

### `proposto` / `edf_greenwave` — `EDFGreenWaveStrategy`

Reactive preemption. Each simulation step the strategy iterates EVs in
Earliest-Deadline-First order; for every TLS within `VEHICLE_DISTANCE_TO_TLS` of an
EV, it calls `GreenWaveManager.request(...)`.

The manager runs a **3-phase FSM** per allocation (one allocation = one EV holding
priority at one TLS):

| Phase | Action on entry | Exit condition |
|-------|------------------|----------------|
| `CLEARING` | Yellow on opposing greens; preserve EV's lane | Wait `TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT` (8 s) |
| `EV_GREEN` | Green for EV's lane, red elsewhere | EV no longer in `getNextTLS` within range |
| `EXIT_YELLOW` | Yellow on EV's greens | Wait `TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT` (8 s), then restore or hand off |

Conflicts are resolved by **EDF arbitration** (`ArbitrationPolicy.can_preempt`). When
a request loses arbitration to the current holder, it joins the holder's **pending
queue** (sorted by deadline). When the holder finishes, the manager either:

- promotes the next still-relevant pending EV directly into `CLEARING` — without
  cycling the TLS back through its original program (the *direct hand-off*), or
- restores the original program if the queue is empty or all queued EVs have
  drifted out of range.

The pending queue is wiped at the end of every `tick()` and refilled by the
strategy's `request()` calls within the same simulation step. This is the
freshness guard: an EV that moved out of range simply does not re-request, and
its queue entry does not reappear next tick.

### `shield` — `SpillbackAwareEDFGreenWaveStrategy` *(planned — Phase A)*

Wraps `proposto` with a spillback shield. Each tick, for every EV, the strategy
checks lane occupancy on the EV's first downstream edge after the next TLS. If
saturated above `SPILLBACK_OCCUPANCY_THRESHOLD`, it skips the EV preempt at the
current TLS (so cross-traffic can flow) and instead requests a *drain* at the
TLS controlling the saturated edge's exit — using the same FSM as the EV
preempt, but with the saturated edge as the priority lane. Drain priority is
lower than EV preempt (later deadline), so an arriving EV preempts an active
drain via EDF.

Full design in [`docs/SPILLBACK_PLAN.md`](docs/SPILLBACK_PLAN.md) §3.

### `mpc_capacity` — *(planned — Phase B)*

Linear program over a rolling horizon, same Store-and-Forward base as the
original MPC plan but with a **downstream-capacity constraint** that bounds
discharge from each lane by the residual capacity of the lane it feeds into.
This makes spillback an explicit element of the model rather than a missing
one. Solver: PuLP + CBC.

Full design (sketch) in [`docs/SPILLBACK_PLAN.md`](docs/SPILLBACK_PLAN.md) §4.
The original pure-S&F MPC formulation in
[`docs/MPC_PLAN.md`](docs/MPC_PLAN.md) is superseded — read it for shared
infrastructure (PuLP setup, glossary), not for direction.

## Development

### Linting
To check code quality and static typing:

```bash
uv run ruff check src/sumotraci
uv run mypy src/sumotraci
```

### Configuration
Configuration is managed via `src/sumotraci/core/config.py` (Pydantic `Settings`).
Override defaults via environment variables, an `.env` file, or CLI arguments.

Settings used by `EDFGreenWaveStrategy`:

| Setting | Default | Meaning |
|---------|---------|---------|
| `VEHICLE_DISTANCE_TO_TLS` | 300 | Max distance (m) from EV to TLS that triggers a `request()`; also used to detect when the EV has left a TLS. |
| `TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT` | 8.0 | Duration (s) of `CLEARING` and `EXIT_YELLOW` waits. |

### Project status

- Strategy abstraction (`TrafficControlStrategy` ABC + factory) — **done**.
- `EDFGreenWaveStrategy` refactor (3-phase FSM, slim public API,
  pending-queue hand-off) — **done**.
- `SpillbackAwareEDFGreenWaveStrategy` (Phase A of
  [`docs/SPILLBACK_PLAN.md`](docs/SPILLBACK_PLAN.md)) — **planned, next**.
- `mpc_capacity` (Phase B) — **planned, after Phase A informs the LP design**.
- Original pure-S&F MPC plan ([`docs/MPC_PLAN.md`](docs/MPC_PLAN.md)) —
  **superseded**.
