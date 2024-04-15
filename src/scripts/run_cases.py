import os
import sys
import pandas as pd
import subprocess
import concurrent.futures

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from src.transform.xml_to_csv import emission_xml_to_csv, summary_xml_to_csv

def run_simulation(
    sumocfg_filename: str,
    summary_filename: str,
    emissions_filename: str,
    route_filename: str,
    trips_filename: str,
    tripinfo_filename: str,
    
    PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT: str,
    SIMULATION_END_TIME: str,
    TRIPS_REPETITION_RATE: str,
    ALGORITHM: str,
):
    # execute main.py com as configurações atualizadas
    subprocess.run([
        'python', 'main.py', '--nogui',
        # '--sumocfg_filepath', sumocfg_filename,
        '--summary_filepath', summary_filename,
        '--emissions_filepath', emissions_filename,
        '--route_filepath', route_filename,
        '--trips_filepath', trips_filename,
        '--tripinfo_filepath', tripinfo_filename, 
        
        '--PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT', PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT,
        '--SIMULATION_END_TIME', SIMULATION_END_TIME,
        '--TRIPS_REPETITION_RATE', TRIPS_REPETITION_RATE,
        '--ALGORITHM', ALGORITHM,
    ])

def main():
    # Carregar os casos de teste do arquivo CSV
    filepath = f'{os.getcwd()}/scripts/cases.csv'
    df = pd.read_csv(filepath)
    # Cria um ThreadPoolExecutor para gerenciar a execução simultânea
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Lista para armazenar os futuros
        futures = []
        for index, row in df.iterrows():
            # Gerar um nome de arquivo dinâmico para cada caso
            sumocfg_filename = f'data/config_{index}.sumocfg'
            summary_filename = f'summary_{index}.xml'
            emissions_filename = f'data/emissions_{index}.xml'
            route_filename = f'route_{index}.rou.xml'
            trips_filename = f'data/trips_{index}.trips.xml'
            tripinfo_filename = f'data/tripinfo_{index}.xml'

            PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT=str(row['Incidência de Acidentes por ambulância (#acidentes/#ambulâncias)'])
            SIMULATION_END_TIME=str(row['Tempo de Simulação (steps)'])
            TRIPS_REPETITION_RATE=str(row['Incidência de Viagens Por Unidade de Tempo (trip/second)'])
            ALGORITHM=str(row['Algoritmo'])

            future = executor.submit(
                run_simulation,
                sumocfg_filename=sumocfg_filename,
                summary_filename=summary_filename,
                emissions_filename=emissions_filename,
                route_filename=route_filename,
                trips_filename=trips_filename,
                tripinfo_filename=tripinfo_filename,
                PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT=PROPORTION_DELAY_CALL_EMERGENCY_VEHICLE_TO_ACCIDENT,
                SIMULATION_END_TIME=SIMULATION_END_TIME,
                TRIPS_REPETITION_RATE=TRIPS_REPETITION_RATE,
                ALGORITHM=ALGORITHM,
            )
            futures.append(future)
            
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                print("Result:", result)
            except Exception as exc:
                raise(f'On index {index} generated an exception: {exc}')

if __name__ == '__main__':
    main()