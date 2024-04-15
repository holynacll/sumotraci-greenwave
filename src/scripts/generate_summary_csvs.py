import os
from simple_grid.src.transform.xml_to_csv import summary_xml_to_csv

pwd = os.path.dirname(os.path.abspath(__file__))
data_dir = f'{pwd}/../data'
# Generate CSVs from XMLs
for filename in os.listdir(data_dir):
    if 'summary' in filename and filename.endswith('.xml'):
        summary_xml_to_csv(f'{data_dir}/{filename}', f'{data_dir}/{filename[:-4]}.csv')