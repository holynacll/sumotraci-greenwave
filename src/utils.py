import os
import subprocess
import xml.etree.ElementTree as ET
from config import settings


# def generate_roadfile(road_filepath: str):
#     # road_filepath = "data/road.net.xml"
#     cmd = (
#         f"python {os.environ['SUMO_HOME']}/tools/osmWebWizard.py -l {settings.LANE_LENGTH} -n {road_filepath}"
#     )
#     cmd_list = cmd.split(" ")
#     os.system(cmd)
#     # subprocess.run(cmd_list, check=True


def generate_routefile(route_filepath: str, trips_filepath: str, trips_repetition_rate: float, seed: int):
    road_filepath = "data/road.net.xml"
    route_filepath = f"data/{route_filepath}"
    # trip_attributes = r"--trip-attributes='color=\"0,0,1\" accel=\"0.8\" decel=\"4.5\" sigma=\"0.5\" length=\"5\" minGap=\"2.5\" maxSpeed=\"16.67\" guiShape=\"passenger\" lcStrategic=\"0.5\"'"
    trip_attributes_1 = 'type="passenger_idm"'
    trip_attributes_2 = 'lcStrategic="10.0"'
    cmd = (
        f"python {os.environ['SUMO_HOME']}/tools/randomTrips.py -n {road_filepath} -r {route_filepath}"
        f" -b 0 -e {settings.SIMULATION_END_TIME} -p {((settings.SIMULATION_END_TIME - 0) / settings.VEHICLE_NUMBER)}"
        f" -o {trips_filepath} --validate --fringe-factor 1000"
        f" --seed {seed}"
        # "  --random -l"
        f" --vehicle-class passenger "
        # f" --trip-attributes '{trip_attributes_1}'"
        f" --trip-attributes '{trip_attributes_2}'"
    )
    os.system(cmd)
    # cmd_list = cmd.split(" ")
    # subprocess.run(cmd_list, check=True)

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
    <vType id="emergency_emergency" vClass="emergency" color="red" speedFactor="1.2">
        <param key="has.bluelight.device" value="true"/>
    </vType>
    """)

    # Insert the new element as the first child of the root
    root.insert(0, new_element)


def add_passenger_idm_vehicle_type_to_route_file(root):
    pass
    # new_element = ET.fromstring("""
    # <vType id="passenger_idm" vClass="passenger" color="yellow" speedFactor="1.2" lcStrategic="10.0">
    #     <param key="length" value="5.0"/>
    #     <param key="minGap" value="2.5"/>
    #     <param key="maxSpeed" value="16.67"/>
    #     <param key="accel" value="3.0"/>
    #     <param key="decel" value="3.25"/>
    #     <param key="sigma" value="0.5"/>
    #     <param key="tau" value="0.8"/>
    #     <param key="delta" value="4"/>
    #     <param key="stepping" value="0.25"/>
    #     <param key="adaptFactor" value="1.8"/>
    #     <param key="adaptTime" value="600"/>
    #     <param key="idm.perceptionDistance" value="50.0"/>
    #     <param key="idm.desiredSpeed" value="10.0"/>
    #     <param key="idm.acceleration" value="0.2"/>
    #     <param key="idm.deceleration" value="0.4"/>
    #     <param key="idm.timeHeadway" value="1.5"/>
    #     <param key="idm.minGapFactor" value="0.8"/>
    #     <param key="idm.maxDecel" value="7.0"/>
    #     <param key="idm.avoidanceLaneChangeProb" value="0.5"/>
    # </vType>
    # """)
    
    # # Insert the new element as the first child of the root
    # root.insert(0, new_element)


def update_sumo_config(summary_filename: str, route_filename: str, new_sumoconfig_filepath: str = 'data/config.sumocfg'):
    # Carregar o arquivo config.sumocfg
    sumoconfig_filepath = 'data/config.sumocfg'
    tree = ET.parse(sumoconfig_filepath)
    root = tree.getroot()

    # Encontrar o elemento summary e atualizar o atributo value
    for summary in root.iter('summary'):
        summary.set('value', summary_filename)
    
    # Encontrar o elemento summary e atualizar o atributo value
    for route in root.iter('route-files'):
        route.set('value', route_filename)
    
    # Salvar o arquivo modificado
    tree.write(new_sumoconfig_filepath)
