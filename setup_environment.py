# setup_environment.py
import os
import sys

# Define o diretório raiz baseado na localização deste arquivo e adiciona 'src'
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(root_dir, 'src')
sys.path.append(src_dir)