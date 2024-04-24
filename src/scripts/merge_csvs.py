import pandas as pd
import os

def merge_csvs(file_list: list, output_dir: str, filename: str):
    # Gerar o caminho do arquivo de saída
    output_file = f'{output_dir}/{filename}'
    # Ler os arquivos CSV
    dataframes = [pd.read_csv(file) for file in file_list]
    # Concatenar os dataframes
    merged_df = pd.concat(dataframes)
    # Salvar o dataframe concatenado em um arquivo CSV
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    merged_df.to_csv(output_file, index=False)
    print(f'Arquivo {output_file} salvo com sucesso!')