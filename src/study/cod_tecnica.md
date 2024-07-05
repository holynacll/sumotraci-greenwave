- a configuração da via é feita pelo script:  netgenerate --grid --grid.number=4 --grid.length=300 --default.lanenumber 3 --default-junction-type traffic_light --output-file=data/road.net.xml --no-turnarounds true
    - a configuração e geração dos veículo é feita pelo script dinâmicamente executado, antes de todo início de simulação:
    ```
    def generate_routefile(route_filepath: str, trips_filepath: str, seed: int):
    road_filepath = "data/road.net.xml"
    route_filepath = f"data/{route_filepath}"
    trip_attributes_1 = 'type="passenger_idm"'
    cmd = (
        f"python {os.environ['SUMO_HOME']}/tools/randomTrips.py -n {road_filepath} -r {route_filepath}"
        f" -b 0 -e {settings.SIMULATION_END_TIME} -p {((settings.SIMULATION_END_TIME - 0) / settings.VEHICLE_NUMBER)}"
        f" -o {trips_filepath} --validate --fringe-factor 1000"
        f" --seed {seed}"
        f" --trip-attributes '{trip_attributes_1}'"
    )
    os.system(cmd)

    # Parse the existing XML route file
    tree = ET.parse(route_filepath)
    root = tree.getroot()

    add_emergency_vehicle_type_to_route_file(root)
    
    add_passenger_idm_vehicle_type_to_route_file(root)

    # Write the updated XML route file
    tree.write(route_filepath, encoding="UTF-8", xml_declaration=True)


    def add_emergency_vehicle_type_to_route_file(root):
        # Create emergency vehicle type and add it to the XML route file
        new_element = ET.fromstring("""
        <vType
        id="emergency_emergency"
        vClass="emergency"
        color="red"
        minGap="0.5"
        >
            <param key="has.bluelight.device" value="true"/>
        </vType>
        """)

        # Insert the new element as the first child of the root
        root.insert(0, new_element)


    def add_passenger_vehicle_type_to_route_file(root):
        new_element = ET.fromstring("""
        <vType 
            id="passenger"
            vClass="passenger"
            color="yellow"
            lcCooperative="1.0"
            lcPushy="0.2"
            lcKeepRight="100"
            jmIgnoreKeepClearTime="1.0"
            jmIgnoreJunctionFoeProb="1.0"
            lcTurnAlignmentDistance="1.0"
        >
        </vType>    
        """)

        # Insert the new element as the first child of the root
        root.insert(0, new_element)
    ```
    - a configuração completa da simulação é feita antes de todo início de simulação. Durante a simulação são capturados as métricas especificadas e ao final da simulação serão gerados os relatórios:
    ```
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
    settings.TIME_TO_BLOCK_CREATE_ACCIDENTS = float(options.time_block_accident)
    settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE = float(options.delay_dispatch_emergency_vehicle)
    settings.CAR_FOLLOW_MODEL = options.car_follow_model
    settings.ALGORITHM = options.algorithm

    generate_routefile(
        route_filepath=options.route_filepath,
        trips_filepath=options.trips_filepath,
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
        "--lateral-resolution", "1.8",
        "--device.bluelight.reactiondist", "1.0",
        # "--emission-output", f'data/{options.emissions_filepath}',
         "--tripinfo-output", f'data/{options.tripinfo_filepath}',
        "-S",
        "-Q",
    ])  

    # Simulation starting
    run()
    
    print('Simulation finished')
    print(settings.ALGORITHM)
    print(settings.CAR_FOLLOW_MODEL)
    print(settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE)
    print(settings.TIME_TO_BLOCK_CREATE_ACCIDENTS)
    print('Generating CSV files...')
    tripinfo_xml_to_csv(
        f'data/{options.tripinfo_filepath}',
        f'data/{options.tripinfo_filepath[:-4]}.csv',
    )
    print('CSV files generated!')
    ```