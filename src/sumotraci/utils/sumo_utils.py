import os
import xml.etree.ElementTree as ET

from ..core.config import Settings


def generate_roadfile(road_filepath: str, settings: Settings):
    # Ensure data directory exists
    os.makedirs(os.path.dirname(f"data/{road_filepath}"), exist_ok=True)

    full_road_filepath = f"data/{road_filepath}"

    # Check if we should really generate it every time or strictly follow original logic
    # Original logic: os.system(...)

    cmd = (
        f"netgenerate --grid --grid.number={settings.GRID_NUMBER} --grid.length={settings.LANE_LENGTH} "
        f"--default.lanenumber {str(settings.LANE_NUMBER)} --default-junction-type traffic_light "
        f"--output-file={full_road_filepath} --no-turnarounds=true"
    )
    os.system(cmd)
    print(f"Generate road network file on {full_road_filepath}")
    return full_road_filepath


def generate_routefile(
    route_filepath: str,
    trips_filepath: str,
    road_filepath: str,
    seed: int,
    settings: Settings,
):
    full_route_filepath = f"data/{route_filepath}"

    # Ensure SUMO_HOME is set
    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
        # Fallback or error? defaulting to original text's path if available could be useful but risky.
        # Better to warn.
        print("WARNING: SUMO_HOME not set. Random trips generation might fail.")

    trip_attributes = 'type="krauss_or_eidm"'
    # Using python to call randomTrips.py
    cmd = (
        f"python {sumo_home}/tools/randomTrips.py -n {road_filepath} -r {full_route_filepath}"
        f" -b 0 -e {settings.SIMULATION_END_TIME} -p {((settings.SIMULATION_END_TIME - 0) / settings.VEHICLE_NUMBER)}"
        f" -o {trips_filepath} --fringe-factor 10"
        f" --seed {seed}"
        f" --trip-attributes '{trip_attributes}'"
    )
    os.system(cmd)

    # Parse the existing XML route file
    try:
        tree = ET.parse(full_route_filepath)
        root = tree.getroot()

        _add_emergency_vehicle_type_to_route_file(root, settings)
        _add_passenger_idm_vehicle_type_to_route_file(root, settings)

        # Write the updated XML route file
        tree.write(full_route_filepath, encoding="UTF-8", xml_declaration=True)
        print(f"Generate route file on {full_route_filepath}")
    except Exception as e:
        print(f"Error processing route file: {e}")


def _add_emergency_vehicle_type_to_route_file(root, settings: Settings):
    # Create emergency vehicle type and add it to the XML route file
    new_element = ET.fromstring(f"""
    <vType
    id="emergency_emergency"
    vClass="emergency"
    guiShape="emergency"
    emissionClass="HBEFA3/PC_G_EU4"
    color="red"
    minGap="{settings.MIN_GAP_EV}"
    speedFactor="1.2"
    collisionMinGapFactor="0.0"
    >
        <param key="has.bluelight.device" value="true"/>
        <param key="has.emissions.device" value="true"/>
        <param key="device.emissions.deterministic"/>
    </vType>
    """)

    # Insert the new element as the first child of the root
    root.insert(0, new_element)


def _add_passenger_idm_vehicle_type_to_route_file(root, settings: Settings):
    new_element = ET.fromstring(f"""
    <vType
        id="krauss_or_eidm"
        carFollowModel="{settings.CAR_FOLLOW_MODEL}"
        color="yellow"
    >
    </vType>
    """)

    # Insert the new element as the first child of the root
    root.insert(0, new_element)


def update_sumo_config(
    summary_filename: str,
    route_filename: str,
    new_sumoconfig_filepath: str = "data/config.sumocfg",
):
    # Carregar o arquivo config.sumocfg
    # Assuming config.sumocfg exists in data/ or use a template
    sumoconfig_filepath = "data/config.sumocfg"  # Base template
    if not os.path.exists(sumoconfig_filepath):
        print(f"Warning: Template {sumoconfig_filepath} not found.")
        return

    tree = ET.parse(sumoconfig_filepath)
    root = tree.getroot()

    # Encontrar o elemento summary e atualizar o atributo value
    for summary in root.iter("summary"):
        summary.set("value", summary_filename)

    # Encontrar o elemento summary e atualizar o atributo value
    for route in root.iter("route-files"):
        route.set("value", route_filename)

    # Salvar o arquivo modificado
    tree.write(new_sumoconfig_filepath)
