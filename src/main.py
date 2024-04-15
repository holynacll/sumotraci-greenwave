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
# from stats import get_statistics_from_timeloss_and_halting

proportion_delay_call_emergency_vehicle_to_accident = 1.2
simulation_end_time = 1200
trips_repetition_rate = 1.0
algorithm = 'proposto'
interval_call_emergency_vehicle_time = settings.INTERVAL_ACCIDENT_TIME * proportion_delay_call_emergency_vehicle_to_accident

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
    print(f'Simulation end time: {simulation_end_time}')
    print(f'Trips repetition rate: {trips_repetition_rate}')
    print(f'Algorithm: {algorithm}')
    print(f'Proportion delay call emergency vehicle to accident: {proportion_delay_call_emergency_vehicle_to_accident}')
    # junctionID = traci.junction.getIDList()[0]
    # traci.junction.subscribeContext(
    #     junctionID, tc.CMD_GET_VEHICLE_VARIABLE, 1000000,
    #     [tc.VAR_SPEED, tc.VAR_ALLOWED_SPEED]
    # )

    try:
        while shouldContinueSim():
            traci.simulationStep()
            monitor_emergency_vehicles() # monitor emergency vehicles and handle them when they arrive at the accident
            if traci.simulation.getTime()%settings.INTERVAL_ACCIDENT_TIME == 0:
                create_accident() # create accident
            if traci.simulation.getTime()%interval_call_emergency_vehicle_time == 0:
                call_emergency_vehicle()
            if algorithm == 'proposto':
                improve_traffic_on_accidented_road() # reroute vehicles to avoid of the aciddented road
                improve_traffic_for_emergency_vehicle() # green wave solution
            # get_statistics_from_timeloss_and_halting(junctionID)
            step += 1
            if traci.simulation.getTime() > simulation_end_time:
                break
        # get_network_parameters()
        traci.close()
    except Exception as e:
        print(traceback.format_exc())


def get_options():
    optParser = optparse.OptionParser()
    optParser.add_option("--nogui", action="store_true",
                         default=False, help="run the commandline version of sumo")
    optParser.add_option("--sumocfg_filepath", type="string",
                         default="data/config.sumocfg", help="define the sumoconfig file path")
    optParser.add_option("--route_filepath", type="string",
                         default="route.rou.xml", help="define the route output file path")
    optParser.add_option("--trips_filepath", type="string",
                         default="data/trips.trips.xml", help="define the route output file path")
    optParser.add_option("--tripinfo_filepath", type="string",
                         default="data/tripinfo.xml", help="define the tripinfo file path")
    optParser.add_option("--summary_filepath", type="string",
                         default="summary.xml", help="define the summary output file path")
    optParser.add_option("--emissions_filepath", type="string",
                         default="data/emissions.xml", help="define the emissions output file path")
    
    optParser.add_option("--PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT", type="string",
                         default=proportion_delay_call_emergency_vehicle_to_accident, help="define the proportion delay call emergency vehicle to accident")
    optParser.add_option("--SIMULATION_END_TIME", type="string",
                        default=simulation_end_time, help="define the simulation end time")
    optParser.add_option("--TRIPS_REPETITION_RATE", type="string",
                        default=trips_repetition_rate, help="define the trips repetition rate")
    optParser.add_option("--ALGORITHM", type="string",
                        default=algorithm, help="define the algorithm to be used")
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
    

    # Atualiza a configuração global
    # settings.update(
    #     PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT=float(options.PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT),
    #     SIMULATION_END_TIME=int(options.SIMULATION_END_TIME),
    #     TRIPS_REPETITION_RATE=float(options.TRIPS_REPETITION_RATE),
    #     ALGORITHM=options.ALGORITHM,
    #     # Adicione outras atualizações conforme necessário
    # )
    simulation_end_time = float(options.SIMULATION_END_TIME)
    trips_repetition_rate = float(options.TRIPS_REPETITION_RATE)
    algorithm = options.ALGORITHM
    proportion_delay_call_emergency_vehicle_to_accident = float(options.PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT)
    interval_call_emergency_vehicle_time = settings.INTERVAL_ACCIDENT_TIME * proportion_delay_call_emergency_vehicle_to_accident

    generate_routefile(
        options.route_filepath,
        options.trips_filepath,
        trips_repetition_rate
    )
    update_sumo_config(
        summary_filename=options.summary_filepath,
        route_filename=options.route_filepath,
        new_sumoconfig_filepath=options.sumocfg_filepath
    )

    # this is the normal way of using traci. sumo is started as a
    # subprocess and then the python script connects and runs
    traci.start([
        sumoBinary,
        "-c", options.sumocfg_filepath,
        "--emission-output", options.emissions_filepath,
         "--tripinfo-output", options.tripinfo_filepath,
        "-S", "-Q",
    ])
        
    run()
    
    print('Generating CSV files...')
    emission_xml_to_csv(
        options.emissions_filepath,
        f'{options.emissions_filepath[:-4]}.csv',
        algorithm,
        proportion_delay_call_emergency_vehicle_to_accident,
        trips_repetition_rate,
        simulation_end_time,
    )
    tripinfo_xml_to_csv(
        options.tripinfo_filepath,
        f'{options.tripinfo_filepath[:-4]}.csv',
        algorithm,
        proportion_delay_call_emergency_vehicle_to_accident,
        trips_repetition_rate,
        simulation_end_time,
    )
    summary_xml_to_csv(
        f'data/{options.summary_filepath}',
        f'data/{options.summary_filepath[:-4]}.csv',
        algorithm,
        proportion_delay_call_emergency_vehicle_to_accident,
        trips_repetition_rate,
        simulation_end_time,
    )
    print('CSV files generated!')