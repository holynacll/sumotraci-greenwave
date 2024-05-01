import os
import subprocess
import xml.etree.ElementTree as ET
from config import settings


def generate_routefile(route_filepath: str, trips_filepath: str, trips_repetition_rate: float, seed: int):
    road_filepath = "data/road.net.xml"
    route_filepath = f"data/{route_filepath}"
    # trip_attributes = r"--trip-attributes='color=\"0,0,1\" accel=\"0.8\" decel=\"4.5\" sigma=\"0.5\" length=\"5\" minGap=\"2.5\" maxSpeed=\"16.67\" guiShape=\"passenger\" lcStrategic=\"0.5\"'"
    trip_attributes_1 = 'departLane="best"'
    trip_attributes_2 = 'lcStrategic="0.5"'
    cmd = (
        f"python {os.environ['SUMO_HOME']}/tools/randomTrips.py -n {road_filepath} -r {route_filepath}"
        f" -o {trips_filepath} --seed {seed} --validate --fringe-factor 1000 -p {trips_repetition_rate}"
        f" --vehicle-class passenger"
        f" --trip-attributes '{trip_attributes_1}'"
        f" --trip-attributes '{trip_attributes_2}'"
        # r"--trip-attributes=\'color=\"0,0,1\" accel=\"0.8\" decel=\"4.5\" sigma=\"0.5\" length=\"5\" ' "
        # r'minGap=\"2.5\" maxSpeed=\"16.67\" guiShape=\"passenger\" lcStrategic=\"0.5\" '
    )
    cmd_list = cmd.split(" ")
    os.system(cmd)
    # subprocess.run(cmd_list, check=True)

    # Parse the existing XML route file
    tree = ET.parse(route_filepath)
    root = tree.getroot()

    # Create emergency vehicle type and add it to the XML route file
    new_element = ET.fromstring("""
    <vType id="emergency_emergency" vClass="emergency" color="red" speedFactor="1.2">
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
