import os
import xml.etree.ElementTree as ET

def calculate_average_density(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    total_density = 0
    count = 0

    for interval in root.findall('interval'):
        for edge in interval.findall('edge'):
            edge_data = edge.attrib
            if edge_data is not None:
                total_density += float(edge_data['density'])
                count += 1

    if count == 0:
        return 0

    average_density = total_density / count
    return average_density

if __name__ == "__main__":
    xml_files = [
        'data/edgedata_com_gw.xml',
        'data/edgedata.xml'
    ]

    for xml_file in xml_files:
        average_density = calculate_average_density(xml_file)
        print(f"The average density for {xml_file} is: {average_density:.6f}")
