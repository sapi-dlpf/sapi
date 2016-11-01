import shutil
import time
import socket

from sapilib_0_5_4 import *

GmodoInstantaneo = False
tempo_sleep = 5
tempo_atualizacao_progresso = 60
tempo_ultimo_update = 0

cd_tarefa_atual = None
arg_tipo = sys.argv[1]
arg_origem = sys.argv[2]
arg_destino = sys.argv[3]


# Faz uma pausa por alguns segundos
# Dependendo de parâmetro, ignora a pausa
def dormir(tempo):
    if not GmodoInstantaneo:
        time.sleep(tempo)
    else:
        print_log_dual("Sem pausa...modo instantâneo em demonstração")


nome_agente = socket.gethostbyaddr(socket.gethostname())[0]


def funcao_copia_com_status(src, dst):
    global tempo_ultimo_update
    if time.time() > tempo_ultimo_update:
        tempo_ultimo_update += tempo_atualizacao_progresso
        print_log_dual("Copiando arquivo " + src)
        atualizar_status_tarefa(cd_tarefa_atual, GEmAndamento, "Copiando arquivo " + src)
    shutil.copy2(src, dst)


def atualizar_tarefa_com_espera(cd_tarefa, cd_situacao_tarefa, texto_status):
    print_log_dual("Atualizando tarefa " + texto_status)  # alterar para incluir cd_tarefa
    while not atualizar_status_tarefa(cd_tarefa,
                                      cd_situacao_tarefa,
                                      status=texto_status
                                      ):
        print_log_dual("Falha na atualização da tarefa %s", cd_tarefa_atual)
        dormir(tempo_sleep)


while True:
    # Requisita uma tarefa
    print_log_dual("Solicitando tarefa ao servidor")
    (disponivel, tarefa) = sapisrv_obter_iniciar_tarefa(arg_tipo, storage=None)  # storage=nome_agente
    # Se não tem nenhuma tarefa disponível, espera um pouco
    if not disponivel:
        print_log_dual("Servidor informou que não existe tarefa para processamento. Esperando (", tempo_sleep,
                       " segundos)")
        dormir(tempo_sleep)
        continue
    var_dump(tarefa)
    #die("1")
    cd_tarefa_atual = tarefa["codigo_tarefa"]  # Identificador único da tarefa
    caminho_origem = tarefa["caminho_origem"]
    caminho_destino = tarefa["caminho_destino"]
    sucesso, ponto_de_montagem_origem, erro_montagem = acesso_storage_windows(tarefa["dados_storage"], True)
    if sucesso:
        print_log_dual("montado ponto de origem: " + ponto_de_montagem_origem)

    sucesso, ponto_de_montagem_destino, erro_montagem = acesso_storage_windows(tarefa["dados_storage_entrega"], True)
    if sucesso:
        print_log_dual("montado ponto de entrega: " + ponto_de_montagem_destino)
    caminho_origem = ponto_de_montagem_origem + caminho_origem
    caminho_destino = ponto_de_montagem_destino + caminho_destino
    if not os.path.exists(caminho_origem):
        atualizar_tarefa_com_espera(cd_tarefa_atual, GAbortou,
                                    "Falha - caminho de origem informado não existe: " + caminho_origem)
        continue
    # origem DIRETORIO
    if os.path.isdir(caminho_origem):
        # acordado que o destino não pode existir (pelo menos até que exista a restauração de uma tarefa interrompida)
        if os.path.exists(caminho_destino):
            atualizar_tarefa_com_espera(cd_tarefa_atual, GAbortou, "Falha - caminho de destino informado já existe")
            continue
        try:
            shutil.copytree(caminho_origem, caminho_destino, copy_function=funcao_copia_com_status)
        except OSError as erro:
            atualizar_tarefa_com_espera(cd_tarefa_atual, GAbortou, "Falha - " + str(erro))
            print_log_dual(str(erro))
            continue
    # origem ARQUIVO - quando for utilizar VHD
    elif os.path.isfile(caminho_origem):
        # se o path destino é apenas um diretorio, complementa com o nome do arquivo
        if os.path.isdir(caminho_destino):
            caminho_destino = os.path.join(caminho_destino, os.path.basename(caminho_origem))
        # checa se o arquivo já existe
        if os.path.exists(caminho_destino) and os.path.isfile(caminho_destino):
            atualizar_tarefa_com_espera(cd_tarefa_atual, GAbortou, "Falha - arquivo de destino informado já existe")
        diretorio_destino = os.path.dirname(caminho_destino)
        os.makedirs(diretorio_destino, exist_ok=True)
        shutil.copy2(caminho_origem, caminho_destino)
    else:  # não é nem arquivo nem pasta, deve falhar. link simbólico?
        atualizar_tarefa_com_espera(cd_tarefa_atual, GAbortou, "Falha - caminho de origem "
                                    + caminho_origem + " não é arquivo ou diretório")
        continue

    dormir(tempo_sleep)
