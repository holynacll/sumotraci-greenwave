import os
import pathlib
import pandas as pd
import subprocess
import concurrent.futures

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from config import settings
# from src.transform.xml_to_csv import emission_xml_to_csv, summary_xml_to_csv
from scripts.merge_csvs import merge_csvs

def run_simulation(
    seed: int,
    summary_filename: str,
    emissions_filename: str,
    route_filename: str,
    trips_filename: str,
    tripinfo_filename: str,

    delay_dispatch: str,
    time_block_accident: str,
    car_following_model: str,
    algorithm: str,
):
    # execute main.py com as configurações atualizadas
    subprocess.run([
        'python', 'main.py', '--nogui',
        '--seed', str(seed),
        '--summary_filepath', summary_filename,
        '--emissions_filepath', emissions_filename,
        '--route_filepath', route_filename,
        '--trips_filepath', trips_filename,
        '--tripinfo_filepath', tripinfo_filename, 
        
        '--delay_dispatch_emergency_vehicle', delay_dispatch,
        '--time_block_accident', time_block_accident,
        '--car_follow_model', car_following_model,
        '--algorithm', algorithm,
    ])
    return pathlib.Path(f'{os.getcwd()}/data/{tripinfo_filename[:-4]}.csv').resolve()


def main():
    seeds = [42, 123, 2023, 1001, 2024, 7, 555, 888, 999, 314]
    # Carregar os casos de teste do arquivo CSV
    filepath = f'{os.getcwd()}/scripts/cases.csv'
    df = pd.read_csv(filepath)
    for seed in seeds:
        # Cria um ThreadPoolExecutor para gerenciar a execução simultânea
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Lista para armazenar os futuros
            futures = []
            for index, row in df.iterrows():
                # Gerar um nome de arquivo dinâmico para cada caso
                summary_filename = f'summary_{index}.xml'
                emissions_filename = f'emissions_{index}.xml'
                route_filename = f'route_{index}.rou.xml'
                trips_filename = f'data/trips_{index}.trips.xml'
                tripinfo_filename = f'tripinfo_{index}.xml'

                delay_dispatch: str = str(row['Tempo de Atraso no Despacho do Veículo de Emergência (seg)'])
                time_block_accident: str = str(row['Tempo de Bloqueio de Criação de Acidente (seg)'])
                car_following_model: str = str(row['Modelo Seguidor de Carro'])
                algorithm: str = str(row['Algoritmo'])

                future = executor.submit(
                    run_simulation,
                    seed=seed,
                    summary_filename=summary_filename,
                    emissions_filename=emissions_filename,
                    route_filename=route_filename,
                    trips_filename=trips_filename,
                    tripinfo_filename=tripinfo_filename,
                    delay_dispatch=delay_dispatch,
                    time_block_accident=time_block_accident,
                    car_following_model=car_following_model,
                    algorithm=algorithm,
                )
                futures.append(future)

            file_list = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    print("Result:", result)
                    file_list.append(result)
                except Exception as exc:
                    raise(f'On index {index} generated an exception: {exc}')
            # Merge CSVs
            merge_csvs(file_list, f'{os.getcwd()}/output', f'seed_{seed}.csv')
        print(f'Seed {seed} executed successfully')
    return 'All seeds executed successfully'


if __name__ == '__main__':
    main()