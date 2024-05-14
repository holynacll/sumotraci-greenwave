from config import (
    traci,
    checkBinary,
    tc,
    settings,
)
import optparse
import traceback

from accident import create_accident
from emergency_call import call_emergency_vehicle
from emergency_monitor import monitor_emergency_vehicles
from optimization_green_wave import improve_traffic_for_emergency_vehicle
from optimization_reroute import improve_traffic_on_accidented_road
from utils import generate_routefile, update_sumo_config
from transform.xml_to_csv import emission_xml_to_csv, summary_xml_to_csv, tripinfo_xml_to_csv


def shouldContinueSim():
    """Checks that the simulation should continue running.
    Returns:
        bool: `True` if vehicles exist on network. `False` otherwise.
    """
    numVehicles = traci.simulation.getMinExpectedNumber()
    return True if numVehicles > 0 else False


def run():
    step = 0
    print('Running simulation...')
    print(f'Seed: {settings.SEED}')
    print(f'Simulation end time: {settings.SIMULATION_END_TIME}')
    print(f'Trips repetition rate: {settings.TRIPS_REPETITION_RATE}')
    print(f'Time to block create accidents: {settings.TIME_TO_BLOCK_CREATE_ACCIDENTS}')
    print(f'Algorithm: {settings.ALGORITHM}')
    try:
        while shouldContinueSim():
            traci.simulationStep()
            monitor_emergency_vehicles() # monitor emergency vehicles and handle them when they arrive at the accident
            if traci.simulation.getTime() < settings.SIMULATION_END_TIME:
                if traci.simulation.getTime()%10 == 0:
                    create_accident()
                if traci.simulation.getTime()%10 == 0:
                    call_emergency_vehicle()
            if settings.ALGORITHM == 'proposto':
                improve_traffic_for_emergency_vehicle() # green wave solution
            step += 1
            # print(f'Step: {step} - Time: {traci.simulation.getTime()}', end='\r')
        traci.close()
        print('Simulation finished!')
        print(f'Saveds: {settings.count_saveds}')
        print(f'Unsaveds: {settings.count_accidents - settings.count_saveds}')
    except Exception as e:
        print(traceback.format_exc())


def get_options():
    optParser = optparse.OptionParser()
    optParser.add_option("--nogui", action="store_true",
                         default=False, help="run the commandline version of sumo")
    optParser.add_option("--seed", type="str",
                         default=settings.SEED, help="define the seed for random number generator")
    optParser.add_option("--sumocfg_filepath", type="string",
                         default="data/config.sumocfg", help="define the sumoconfig file path")
    optParser.add_option("--route_filepath", type="string",
                         default="route.rou.xml", help="define the route output file path")
    optParser.add_option("--trips_filepath", type="string",
                         default="data/trips.trips.xml", help="define the route output file path")
    optParser.add_option("--tripinfo_filepath", type="string",
                         default="tripinfo.xml", help="define the tripinfo file path")
    optParser.add_option("--summary_filepath", type="string",
                         default="summary.xml", help="define the summary output file path")
    optParser.add_option("--emissions_filepath", type="string",
                         default="emissions.xml", help="define the emissions output file path")
    optParser.add_option("--TIME_TO_BLOCK_CREATE_ACCIDENTS", type="string",
                        default=settings.TIME_TO_BLOCK_CREATE_ACCIDENTS, help="define the time to block create new accidents")
    optParser.add_option("--SIMULATION_END_TIME", type="string",
                        default=settings.SIMULATION_END_TIME, help="define the simulation end time")
    optParser.add_option("--TRIPS_REPETITION_RATE", type="string",
                        default=settings.TRIPS_REPETITION_RATE, help="define the trips repetition rate")
    optParser.add_option("--ALGORITHM", type="string",
                        default=settings.ALGORITHM, help="define the algorithm to be used")
    options, args = optParser.parse_args()
    return options


# this is the main entry point of this script
if __name__ == "__main__":
    options = get_options()

    # this script has been called from the command line. It will start sumo as a
    # server, then connect and run
    if options.nogui:
        sumoBinary = checkBinary('sumo')
    else:
        sumoBinary = checkBinary('sumo-gui')

    settings.SEED = int(options.seed)
    settings.TIME_TO_BLOCK_CREATE_ACCIDENTS = float(options.TIME_TO_BLOCK_CREATE_ACCIDENTS)
    settings.SIMULATION_END_TIME = float(options.SIMULATION_END_TIME)
    settings.TRIPS_REPETITION_RATE = float(options.TRIPS_REPETITION_RATE)
    settings.ALGORITHM = options.ALGORITHM

    generate_routefile(
        route_filepath=options.route_filepath,
        trips_filepath=options.trips_filepath,
        trips_repetition_rate=settings.TRIPS_REPETITION_RATE,
        seed=settings.SEED,
    )
    update_sumo_config(
        summary_filename=options.summary_filepath,
        route_filename=options.route_filepath,
        new_sumoconfig_filepath=options.sumocfg_filepath,
    )

    # this is the normal way of using traci. sumo is started as a
    # subprocess and then the python script connects and runs
    traci.start([
        sumoBinary,
        "-c", options.sumocfg_filepath,
        # "--lanechange.duration", "5.0",
        "--lateral-resolution", "1.8",
        "--device.bluelight.reactiondist", "1.0",
        # "--device.bluelight.deterministic", "true",
        "--emission-output", f'data/{options.emissions_filepath}',
        #  "--tripinfo-output", f'data/{options.tripinfo_filepath}',
        "-S",
        "-Q",
    ])
        
    run()

    print('Generating CSV files...')
    # results_dir = f'data/results-{settings.SEED}'
    # os.makedirs(results_dir, exist_ok=True)
    emission_xml_to_csv(
        f'data/{options.emissions_filepath}',
        f'data/{options.emissions_filepath[:-4]}.csv',
        # algorithm,
        # # proportion_delay_call_emergency_vehicle_to_accident,
        # trips_repetition_rate,
        # simulation_end_time,
    )
    # tripinfo_xml_to_csv(
    #     f'data/{options.tripinfo_filepath}',
    #     f'{results_dir}/{options.tripinfo_filepath[:-4]}.csv',
    #     # algorithm,
    #     # # proportion_delay_call_emergency_vehicle_to_accident,
    #     # trips_repetition_rate,
    #     # simulation_end_time,
    # )
    # summary_xml_to_csv(
    #     f'data/{options.summary_filepath}',
    #     f'{results_dir}/{options.summary_filepath[:-4]}.csv',
    #     # algorithm,
    #     # # proportion_delay_call_emergency_vehicle_to_accident,
    #     # trips_repetition_rate,
    #     # simulation_end_time,
    # )
    print('CSV files generated!')