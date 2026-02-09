import os
import sys

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ.get('SUMO_HOME'), 'tools')
    sys.path.append(tools)
    print(f"Pasta tools adicionada ao sys.path: {tools}")
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

try:
    import traci
    import traci.constants as tc
    from sumolib import checkBinary  # noqa
    print("traci importado com sucesso.")
except ModuleNotFoundError as e:
    print(f"Erro ao importar módulo: {e}")
    sys.exit("Certifique-se de que o SUMO e o Traci estão instalados corretamente e o caminho do SUMO_HOME está correto.")
