import shutil

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi.py, para evitar dependência
from sapilib_0_5_4 import *

arg_tipo = sys.argv[1]
arg_storage = sys.argv[2]


def valida_caminho(pasta, explicar=False):
    # Verifica se pasta informada existe
    if not os.path.exists(pasta):
        if_print_ok(explicar)
        if_print_ok(explicar, "* ERRO: Pasta informada %s não localizada", pasta)
        return False


while (True):
    # Requisita uma tarefa
    print_log_dual("Solicitando tarefa ao servidor")
    (disponivel, tarefa) = sapisrv_obter_iniciar_tarefa(arg_tipo, storage=arg_storage)
    caminho_origem = tarefa["caminho_origem"]
    caminho_destino = tarefa["caminho_destino"]

    valida_caminho(caminho_destino)
    valida_caminho(caminho_origem)
    shutil.copytree(caminho_origem, caminho_destino)
