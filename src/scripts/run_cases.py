import pandas as pd
import subprocess
import concurrent.futures
from config import settings
from xml_to_csv import emission_xml_to_csv, summary_xml_to_csv

def run_simulation(
    sumocfg_filename: str,
    summary_filename: str,
    emissions_filename: str,
    route_filename: str,
    trips_filename: str,
):
    # execute main.py com as configurações atualizadas
    subprocess.run([
        'python', 'main.py', '--nogui',
        # '--sumocfg_filepath', sumocfg_filename,
        '--summary_filepath', summary_filename,
        '--emissions_filepath', emissions_filename,
        '--route_filepath', route_filename,
        '--trips_filepath', trips_filename,
    ])
    emission_xml_to_csv(emissions_filename, f'{emissions_filename[:-4]}.csv')
    summary_xml_to_csv(summary_filename, f'{summary_filename[:-4]}.csv')

def main():
    # Carregar os casos de teste do arquivo CSV
    df = pd.read_csv('cases.csv')
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

            # Atualiza a configuração global
            settings.update(
                INCIDENCE_CALL_EMERGENCY_VEHICLE_PER_ACCIDENT=row['Incidência de Acidentes por ambulância (#acidentes/#ambulâncias)'],
                SIMULATION_END_TIME=row['Tempo de Simulação (steps)'],
                TRIPS_REPETITION_RATE=row['Incidência de Viagens Por Unidade de Tempo (trip/second)'],
                ALGORITHM=row['Algoritmo'],
                # Adicione outras atualizações conforme necessário
            )
            future = executor.submit(run_simulation, sumocfg_filename, summary_filename, emissions_filename, route_filename, trips_filename)
            futures.append(future)
            
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                print("Result:", result)
            except Exception as exc:
                raise(f'On index {index} generated an exception: {exc}')

if __name__ == '__main__':
    main()