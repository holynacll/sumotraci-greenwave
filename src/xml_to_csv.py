import csv
import xml.etree.ElementTree as ET

from config import settings

def emission_xml_to_csv(xml_file, csv_file):
    print(f'emission_xml_to_csv - seed: {settings.SEED}')
    print(f'emission_xml_to_csv - simulation_end_time: {settings.SIMULATION_END_TIME}')
    # Parse the XML file
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Prepare to write to CSV
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        csv_writer = None

        # Iterate over each timestep and then each vehicle
        for timestep in root.findall('timestep'):
            time = timestep.attrib['time']

            for vehicle in timestep.findall('vehicle'):
                # Combine the time attribute with vehicle attributes
                vehicle_data = vehicle.attrib
                vehicle_data['seed'] = settings.SEED
                vehicle_data['time'] = time
                vehicle_data['ALGORITHM'] = settings.ALGORITHM
                vehicle_data['TIME_TO_BLOCK_CREATE_ACCIDENTS'] = settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
                vehicle_data['SIMULATION_END_TIME'] = settings.SIMULATION_END_TIME

                # If the CSV writer hasn't been set up yet, do it with the headers
                if csv_writer is None:
                    headers = list(vehicle_data.keys())
                    csv_writer = csv.DictWriter(file, fieldnames=headers)
                    csv_writer.writeheader()

                # Write the vehicle data as a row in the CSV
                csv_writer.writerow(vehicle_data)


# def summary_xml_to_csv(xml_file, csv_file):
#     # Parse the XML file
#     tree = ET.parse(xml_file)
#     root = tree.getroot()

#     # Prepare to write to CSV
#     with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
#         csv_writer = None

#         # Iterate over each timestep and then each vehicle
#         for step in root.findall('step'):
#             # Combine the time attribute with vehicle attributes
#             step_data = step.attrib
#             step_data['seed'] = settings.SEED
#             step_data['ALGORITHM'] = algorithm
#             step_data['PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT'] = proportion_delay_call_emergency_vehicle_to_accident
#             step_data['SIMULATION_END_TIME'] = simulation_end_time


#             # If the CSV writer hasn't been set up yet, do it with the headers
#             if csv_writer is None:
#                 headers = list(step_data.keys())
#                 csv_writer = csv.DictWriter(file, fieldnames=headers)
#                 csv_writer.writeheader()

#             # Write the vehicle data as a row in the CSV
#             csv_writer.writerow(step_data)


def edgedata_xml_to_csv(xml_file, csv_file):
    # Parse the XML file
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Prepare to write to CSV
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        csv_writer = None

        # Iterate over each timestep and then each vehicle
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
                interval_data['TIME_TO_BLOCK_CREATE_ACCIDENTS'] = (
                    settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
                )
                interval_data['SAVEDS'] = settings.count_saveds
                interval_data['UNSAVEDS'] = settings.count_accidents - settings.count_saveds

                # If the CSV writer hasn't been set up yet, do it with the headers
                if csv_writer is None:
                    headers = list(interval_data.keys())
                    csv_writer = csv.DictWriter(file, fieldnames=headers)
                    csv_writer.writeheader()

                # Write the vehicle data as a row in the CSV
                csv_writer.writerow(interval_data)


def tripinfo_xml_to_csv(xml_file, csv_file):
    # Parse the XML file
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Prepare to write to CSV
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        csv_writer = None

        # Iterate over each timestep and then each vehicle
        for tripinfo in root.findall('tripinfo'):
            # Combine the time attribute with vehicle attributes
            tripinfo_data = tripinfo.attrib
            tripinfo_data['CO_abs'] = ''
            tripinfo_data['CO2_abs'] = ''
            tripinfo_data['HC_abs'] = ''
            tripinfo_data['PMx_abs'] = ''
            tripinfo_data['NOx_abs'] = ''
            tripinfo_data['fuel_abs'] = ''
            if tripinfo_data['vType'] == 'emergency_emergency':
                for tripinfo_emission in tripinfo.findall('emissions'):
                    tripinfo_emission_data = tripinfo_emission.attrib
                    tripinfo_data['CO_abs'] = tripinfo_emission_data['CO_abs']
                    tripinfo_data['CO2_abs'] = tripinfo_emission_data['CO2_abs']
                    tripinfo_data['HC_abs'] = tripinfo_emission_data['HC_abs']
                    tripinfo_data['PMx_abs'] = tripinfo_emission_data['PMx_abs']
                    tripinfo_data['NOx_abs'] = tripinfo_emission_data['NOx_abs']
                    tripinfo_data['fuel_abs'] = tripinfo_emission_data['fuel_abs']

            tripinfo_data['seed'] = settings.SEED
            tripinfo_data['ALGORITHM'] = settings.ALGORITHM
            tripinfo_data['DELAY_TO_DISPATCH_EMERGENCY_VEHICLE'] = settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE
            tripinfo_data['CAR_FOLLOW_MODEL'] = settings.CAR_FOLLOW_MODEL
            tripinfo_data['TIME_TO_BLOCK_CREATE_ACCIDENTS'] = (
                settings.TIME_TO_BLOCK_CREATE_ACCIDENTS
            )
            tripinfo_data['SAVEDS'] = settings.count_saveds
            tripinfo_data['UNSAVEDS'] = settings.count_accidents - settings.count_saveds


            # If the CSV writer hasn't been set up yet, do it with the headers
            if csv_writer is None:
                headers = list(tripinfo_data.keys())
                csv_writer = csv.DictWriter(file, fieldnames=headers)
                csv_writer.writeheader()

            # Write the vehicle data as a row in the CSV
            csv_writer.writerow(tripinfo_data)
# Example usage
# summary_xml_to_csv('data/summary_0.xml', 'data/summary_0.csv')
