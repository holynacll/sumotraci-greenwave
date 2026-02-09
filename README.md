# SumoTraCI Greenwave

Refactored Python codebase for SumoTraCI Greenwave project, implementing a modular architecture and modern tooling with `uv` and `typer`.

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
-   `--algorithm STR`: Traffic logic to use (`proposto` or `default`).
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
-   **`managers/`**: Business logic modules.
    -   `accident_manager.py`: Manages accident lifecycle.
    -   `emergency_manager.py`: Handles emergency vehicle dispatch and monitoring.
    -   `traffic_manager.py`: Implements Green Wave and rerouting strategies.
-   **`domain/`**: Data models (Schemas) and Enumerations (`SeverityEnum`, `StatusEnum`).
-   **`utils/`**: Helper utilities for SUMO interaction and XML/CSV processing.

## Development

### Linting
To check code quality and static typing:

```bash
uv run ruff check src/sumotraci
uv run mypy src/sumotraci
```

### Configuration
Configuration is managed via `src/sumotraci/core/config.py`. You can override defaults using environment variables or CLI arguments.
