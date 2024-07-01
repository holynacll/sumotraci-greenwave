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



def add_passenger_idm_vehicle_type_to_route_file(root):
    new_element = ET.fromstring(f"""
    <vType 
        id="passenger_idm"
        carFollowModel="{settings.CAR_FOLLOW_MODEL}"
        color="yellow"
    >
    </vType>
    """)
    
    # Insert the new element as the first child of the root
    root.insert(0, new_element)


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
