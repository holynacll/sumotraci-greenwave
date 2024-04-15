import xml.etree.ElementTree as ET
import csv

def emission_xml_to_csv(xml_file, csv_file):
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

                # If the CSV writer hasn't been set up yet, do it with the headers
                if csv_writer is None:
                    headers = list(vehicle_data.keys())
                    csv_writer = csv.DictWriter(file, fieldnames=headers)
                    csv_writer.writeheader()

                # Write the vehicle data as a row in the CSV
                csv_writer.writerow(vehicle_data)


def summary_xml_to_csv(xml_file, csv_file):
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

            # If the CSV writer hasn't been set up yet, do it with the headers
            if csv_writer is None:
                headers = list(step_data.keys())
                csv_writer = csv.DictWriter(file, fieldnames=headers)
                csv_writer.writeheader()

            # Write the vehicle data as a row in the CSV
            csv_writer.writerow(step_data)


# Example usage
# summary_xml_to_csv('data/summary_0.xml', 'data/summary_0.csv')
