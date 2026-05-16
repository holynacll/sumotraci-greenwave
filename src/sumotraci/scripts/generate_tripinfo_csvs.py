import os
import sys

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# import config
from src.xml_to_csv import tripinfo_xml_to_csv


pwd = os.path.dirname(os.path.abspath(__file__))
data_dir = f'{pwd}/../data'
# Generate CSVs from XMLs
for filename in os.listdir(data_dir):
    if 'emissions' in filename and filename.endswith('.xml'):
        tripinfo_xml_to_csv(f'{data_dir}/{filename}', f'{data_dir}/{filename[:-4]}.csv')
