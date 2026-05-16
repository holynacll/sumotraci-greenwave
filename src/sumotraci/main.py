import os
from typing import Optional

import typer

# Add the current directory to sys.path to ensure modules can be imported if running directly
# sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from .core.config import Settings
from .core.simulation import SimulationEngine

app = typer.Typer(help="SumoTraCI Greenwave Simulation")

@app.command()
def run(
    nogui: bool = typer.Option(False, "--nogui", help="Run SUMO in command-line mode (no GUI)."),
    seed: Optional[int] = typer.Option(None, "--seed", help="Seed for random number generator."),
    road_filepath: str = typer.Option("road.net.xml", "--road-filepath", help="Road network output file path."),
    sumocfg_filepath: str = typer.Option("data/config.sumocfg", "--sumocfg-filepath", help="SUMO config file path."),
    route_filepath: str = typer.Option("route.rou.xml", "--route-filepath", help="Route output file path."),
    trips_filepath: str = typer.Option("data/trips.trips.xml", "--trips-filepath", help="Trips output file path."),
    tripinfo_filepath: str = typer.Option("tripinfo.xml", "--tripinfo-filepath", help="Tripinfo output file path."),
    lanedata_filepath: str = typer.Option("lanedata.xml", "--lanedata-filepath", help="Lanedata output file path."),
    summary_filepath: str = typer.Option("summary.xml", "--summary-filepath", help="Summary output file path."),
    time_block_accident: Optional[float] = typer.Option(
        None, "--time-block-accident", help="Time to block create accidents."
    ),
    delay_dispatch: Optional[float] = typer.Option(
        None, "--delay-dispatch", help="Delay to dispatch emergency vehicle."
    ),
    vehicle_number: Optional[int] = typer.Option(None, "--vehicle-number", help="Number of vehicles to insert."),
    simulation_end_time: Optional[float] = typer.Option(
        None, "--simulation-end-time", help="Simulation end time."
    ),
    algorithm: Optional[str] = typer.Option(None, "--algorithm", help="Algorithm to be used (proposto/default)."),
    car_follow_model: Optional[str] = typer.Option(
        None, "--car-follow-model", help="Car follow model (EIDM/IDM/Krauss)."
    ),
):
    """
    Run the traffic simulation.
    """
    # 1. Load Settings (Environment variables + Defaults)
    settings = Settings()

    # 2. Override with CLI arguments if provided
    if seed is not None:
        settings.SEED = seed
    if time_block_accident is not None:
        settings.TIME_TO_BLOCK_CREATE_ACCIDENTS = time_block_accident
    if delay_dispatch is not None:
        settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE = delay_dispatch
    if vehicle_number is not None:
        settings.VEHICLE_NUMBER = vehicle_number
    if simulation_end_time is not None:
        settings.SIMULATION_END_TIME = simulation_end_time
    if algorithm is not None:
        settings.ALGORITHM = algorithm
    if car_follow_model is not None:
        settings.CAR_FOLLOW_MODEL = car_follow_model

    # 3. Validation / Environment Check
    if not os.environ.get('SUMO_HOME'):
         # Fallback check
         # In original config: os.environ['SUMO_HOME'] = "/.../site-packages/sumo"
         # We try to keep it cleaner here but print warning
         typer.echo("WARNING: SUMO_HOME environment variable is not set. Simulation might fail.", err=True)

    # 4. Initialize Simulation Engine
    engine = SimulationEngine(
        settings=settings,
        nogui=nogui,
        sumocfg_path=sumocfg_filepath,
        road_filepath=road_filepath,
        route_filepath=route_filepath,
        trips_filepath=trips_filepath,
        tripinfo_filepath=tripinfo_filepath,
        lanedata_filepath=lanedata_filepath,
        summary_filepath=summary_filepath
    )

    # 5. Run
    engine.run()


if __name__ == "__main__":
    app()
