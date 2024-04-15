import os
import subprocess
import xml.etree.ElementTree as ET
from config import settings


def generate_routefile(route_filepath: str, trips_filepath: str, TRIPS_REPETITION_RATE):
    road_filepath = "data/road.net.xml"
    route_filepath = f"data/{route_filepath}"
    cmd = f"python {os.environ['SUMO_HOME']}/tools/randomTrips.py -n {road_filepath} -r {route_filepath} -o {trips_filepath} --seed 42 --validate --fringe-factor 1000 -p {TRIPS_REPETITION_RATE}"
    cmd_list = cmd.split(" ")
    subprocess.run(cmd_list, check=True)

    # Parse the existing XML route file
    tree = ET.parse(route_filepath)
    root = tree.getroot()

    # Create emergency vehicle type and add it to the XML route file
    new_element = ET.fromstring("""
    <vType id="emergency_emergency" vClass="emergency" color="red" speedFactor="1.5">
        <param key="has.bluelight.device" value="true"/>
    </vType>
    """)

    # Insert the new element as the first child of the root
    root.insert(0, new_element)

    # Write the updated XML route file
    tree.write(route_filepath, encoding="UTF-8", xml_declaration=True)


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
