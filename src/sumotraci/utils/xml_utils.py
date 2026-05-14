import csv
import xml.etree.ElementTree as ET

from ..core.config import Settings


def emission_xml_to_csv(xml_file: str, csv_file: str, settings: Settings):
    print(f'emission_xml_to_csv - seed: {settings.SEED}')
    print(f'emission_xml_to_csv - simulation_end_time: {settings.SIMULATION_END_TIME}')

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML {xml_file}: {e}")
        return

    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        csv_writer = None

        for timestep in root.findall('timestep'):
            time = timestep.attrib['time']

            for vehicle in timestep.findall('vehicle'):
                vehicle_data = vehicle.attrib
                vehicle_data['seed'] = settings.SEED
                vehicle_data['time'] = time
                vehicle_data['ALGORITHM'] = settings.ALGORITHM
                vehicle_data['TIME_TO_BLOCK_CREATE_ACCIDENTS'] = settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
                vehicle_data['SIMULATION_END_TIME'] = settings.SIMULATION_END_TIME

                if csv_writer is None:
                    headers = list(vehicle_data.keys())
                    csv_writer = csv.DictWriter(file, fieldnames=headers)
                    csv_writer.writeheader()

                csv_writer.writerow(vehicle_data)


def edgedata_xml_to_csv(xml_file: str, csv_file: str, settings: Settings, saveds: int, un_saveds: int):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML {xml_file}: {e}")
        return

    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        csv_writer = None

        for meandata in root.findall('interval'):
            for interval in meandata.findall('edge'):
                interval_data = interval.attrib
                if 'teleported' not in interval_data:
                    interval_data['teleported'] = '0'
                if 'vaporized' not in interval_data:
                    interval_data['vaporized'] = '0'
                interval_data['seed'] = settings.SEED
                interval_data['ALGORITHM'] = settings.ALGORITHM
                interval_data['DELAY_TO_DISPATCH_EMERGENCY_VEHICLE'] = settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE
                interval_data['CAR_FOLLOW_MODEL'] = settings.CAR_FOLLOW_MODEL
                interval_data['TIME_TO_BLOCK_CREATE_ACCIDENTS'] = settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
                interval_data['SAVEDS'] = saveds
                interval_data['UNSAVEDS'] = un_saveds

                if csv_writer is None:
                    headers = list(interval_data.keys())
                    csv_writer = csv.DictWriter(file, fieldnames=headers)
                    csv_writer.writeheader()

                csv_writer.writerow(interval_data)


def tripinfo_xml_to_csv(
    xml_file: str,
    csv_file: str,
    settings: Settings,
    saveds: int,
    un_saveds: int,
    collisions_involved: int = 0,
    collision_steps: int = 0,
    ev_collisions: int = 0,
):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML {xml_file}: {e}")
        return

    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        csv_writer = None

        for tripinfo in root.findall('tripinfo'):
            tripinfo_data = tripinfo.attrib
            tripinfo_data['CO_abs'] = ''
            tripinfo_data['CO2_abs'] = ''
            tripinfo_data['HC_abs'] = ''
            tripinfo_data['PMx_abs'] = ''
            tripinfo_data['NOx_abs'] = ''
            tripinfo_data['fuel_abs'] = ''

            if tripinfo_data.get('vType') == 'emergency_emergency':
                for tripinfo_emission in tripinfo.findall('emissions'):
                    tripinfo_emission_data = tripinfo_emission.attrib
                    tripinfo_data['CO_abs'] = tripinfo_emission_data.get('CO_abs', '')
                    tripinfo_data['CO2_abs'] = tripinfo_emission_data.get('CO2_abs', '')
                    tripinfo_data['HC_abs'] = tripinfo_emission_data.get('HC_abs', '')
                    tripinfo_data['PMx_abs'] = tripinfo_emission_data.get('PMx_abs', '')
                    tripinfo_data['NOx_abs'] = tripinfo_emission_data.get('NOx_abs', '')
                    tripinfo_data['fuel_abs'] = tripinfo_emission_data.get('fuel_abs', '')

            tripinfo_data['seed'] = settings.SEED
            tripinfo_data['ALGORITHM'] = settings.ALGORITHM
            tripinfo_data['DELAY_TO_DISPATCH_EMERGENCY_VEHICLE'] = settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE
            tripinfo_data['CAR_FOLLOW_MODEL'] = settings.CAR_FOLLOW_MODEL
            tripinfo_data['TIME_TO_BLOCK_CREATE_ACCIDENTS'] = settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
            tripinfo_data['SAVEDS'] = saveds
            tripinfo_data['UNSAVEDS'] = un_saveds
            tripinfo_data['COLLISIONS_INVOLVED'] = collisions_involved
            tripinfo_data['COLLISION_STEPS'] = collision_steps
            tripinfo_data['EV_COLLISIONS'] = ev_collisions

            if csv_writer is None:
                headers = list(tripinfo_data.keys())
                csv_writer = csv.DictWriter(file, fieldnames=headers)
                csv_writer.writeheader()

            csv_writer.writerow(tripinfo_data)


def lanedata_xml_to_csv(
    xml_file: str,
    csv_file: str,
    settings: Settings,
    saveds: int,
    un_saveds: int,
    collisions_involved: int = 0,
    collision_steps: int = 0,
    ev_collisions: int = 0,
):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML {xml_file}: {e}")
        return

    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        csv_writer = None

        for interval in root.findall('interval'):
            for edge in interval.findall('edge'):
                for lane in edge.findall('lane'):
                    interval_data = interval.attrib
                    lane_data = lane.attrib
                    if 'teleported' not in lane_data:
                        lane_data['teleported'] = '0'
                    if 'vaporized' not in lane_data:
                        lane_data['vaporized'] = '0'
                    lane_data['end'] = interval_data['end']
                    lane_data['seed'] = settings.SEED
                    lane_data['ALGORITHM'] = settings.ALGORITHM
                    lane_data['DELAY_TO_DISPATCH_EMERGENCY_VEHICLE'] = settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE
                    lane_data['CAR_FOLLOW_MODEL'] = settings.CAR_FOLLOW_MODEL
                    lane_data['TIME_TO_BLOCK_CREATE_ACCIDENTS'] = settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
                    lane_data['SAVEDS'] = saveds
                    lane_data['UNSAVEDS'] = un_saveds
                    lane_data['COLLISIONS_INVOLVED'] = collisions_involved
                    lane_data['COLLISION_STEPS'] = collision_steps
                    lane_data['EV_COLLISIONS'] = ev_collisions

                    if csv_writer is None:
                        headers = list(lane_data.keys())
                        csv_writer = csv.DictWriter(file, fieldnames=headers)
                        csv_writer.writeheader()

                    csv_writer.writerow(lane_data)
