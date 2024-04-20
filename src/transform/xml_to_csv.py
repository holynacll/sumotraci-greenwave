import os
import sys
import csv
import xml.etree.ElementTree as ET

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

def emission_xml_to_csv(xml_file, csv_file, algorithm, proportion_delay_call_emergency_vehicle_to_accident, trips_repetition_rate, simulation_end_time):
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
                vehicle_data['time'] = time
                vehicle_data['ALGORITHM'] = algorithm
                vehicle_data['PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT'] = proportion_delay_call_emergency_vehicle_to_accident
                vehicle_data['TRIPS_REPETITION_RATE'] = trips_repetition_rate
                vehicle_data['SIMULATION_END_TIME'] = simulation_end_time

                # If the CSV writer hasn't been set up yet, do it with the headers
                if csv_writer is None:
                    headers = list(vehicle_data.keys())
                    csv_writer = csv.DictWriter(file, fieldnames=headers)
                    csv_writer.writeheader()

                # Write the vehicle data as a row in the CSV
                csv_writer.writerow(vehicle_data)


def summary_xml_to_csv(xml_file, csv_file, algorithm, proportion_delay_call_emergency_vehicle_to_accident, trips_repetition_rate, simulation_end_time):
    # Parse the XML file
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Prepare to write to CSV
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        csv_writer = None

        # Iterate over each timestep and then each vehicle
        for step in root.findall('step'):
            # Combine the time attribute with vehicle attributes
            step_data = step.attrib
            step_data['ALGORITHM'] = algorithm
            step_data['PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT'] = proportion_delay_call_emergency_vehicle_to_accident
            step_data['TRIPS_REPETITION_RATE'] = trips_repetition_rate
            step_data['SIMULATION_END_TIME'] = simulation_end_time


            # If the CSV writer hasn't been set up yet, do it with the headers
            if csv_writer is None:
                headers = list(step_data.keys())
                csv_writer = csv.DictWriter(file, fieldnames=headers)
                csv_writer.writeheader()

            # Write the vehicle data as a row in the CSV
            csv_writer.writerow(step_data)


def tripinfo_xml_to_csv(xml_file, csv_file, algorithm, proportion_delay_call_emergency_vehicle_to_accident, trips_repetition_rate, simulation_end_time):
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
            tripinfo_data['ALGORITHM'] = algorithm
            tripinfo_data['PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT'] = proportion_delay_call_emergency_vehicle_to_accident
            tripinfo_data['TRIPS_REPETITION_RATE'] = trips_repetition_rate
            tripinfo_data['SIMULATION_END_TIME'] = simulation_end_time
            # tripinfo_data['EXP_ID'] = f'{algorithm}-{proportion_delay_call_emergency_vehicle_to_accident}-{trips_repetition_rate}-{simulation_end_time}'


            # If the CSV writer hasn't been set up yet, do it with the headers
            if csv_writer is None:
                headers = list(tripinfo_data.keys())
                csv_writer = csv.DictWriter(file, fieldnames=headers)
                csv_writer.writeheader()

            # Write the vehicle data as a row in the CSV
            csv_writer.writerow(tripinfo_data)
# Example usage
# summary_xml_to_csv('data/summary_0.xml', 'data/summary_0.csv')