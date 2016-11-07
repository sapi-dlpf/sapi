import shutil
import time
import socket

from sapilib_0_5_4 import *

GmodoInstantaneo = False
tempo_sleep = 5
tempo_atualizacao_progresso = 5
tempo_ultimo_status_update = time.time()

cd_tarefa_atual = None
arg_tipo = sys.argv[1]
nome_agente = socket.gethostbyaddr(socket.gethostname())[0]
debug = True


# Faz uma pausa por alguns segundos
# Dependendo de parâmetro, ignora a pausa
def dormir(tempo):
    if not GmodoInstantaneo:
        time.sleep(tempo)
    else:
        print_log_dual("Sem pausa...modo instantâneo em demonstração")


# função para ser utilizada no copytree (que utiliza copy2 por padrão)
# Também é baseada no copy2, mas antes de fazer a cópia, atualiza a tarefa
# (atualização apenas após determinado período para evitar sobrecarregar o servidor)
def funcao_copia_com_status(src, dst):
    global tempo_ultimo_status_update
    if time.time() > tempo_ultimo_status_update:
        tempo_ultimo_status_update += tempo_atualizacao_progresso
        print_log_dual("Copiando arquivo " + src)
        atualizar_status_tarefa(cd_tarefa_atual, GEmAndamento, "Copiando arquivo " + src)
    shutil.copy2(src, dst)


def atualizar_tarefa_com_espera(cd_tarefa, cd_situacao_tarefa, texto_status):
    print_log_dual("Atualizando tarefa " + texto_status)  # alterar para incluir cd_tarefa
    if not debug:
        while not atualizar_status_tarefa(cd_tarefa,
                                          cd_situacao_tarefa,
                                          status=texto_status
                                          ):
            print_log_dual("Falha na atualização da tarefa %s", cd_tarefa_atual)
            dormir(tempo_sleep)


def formata_tamanho(num, sufixo='B'):
    for unidade in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unidade, sufixo)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', sufixo)


def copia_com_status(file_size, fsrc, fdst, length=16 * 1024):
    global tempo_ultimo_status_update
    bytes_lidos = 0
    while 1:
        buf = fsrc.read(length)
        bytes_lidos += len(buf)
        if time.time() > tempo_ultimo_status_update:
            tempo_ultimo_status_update += tempo_atualizacao_progresso
            if not debug:
                atualizar_status_tarefa(cd_tarefa_atual, GEmAndamento, "Cópia em andamento: ")
            print_log_dual("Copiados %s - %.1f%%" % (formata_tamanho(bytes_lidos), bytes_lidos * 100 / file_size))
        if not buf:
            break
        fdst.write(buf)


# função de cópia de arquivos isolados com atualização de status da tarefa
def copiar_arquivo_com_status(src, dst):
    file_info = os.stat(src)
    file_size = file_info.st_size
    mensagem_tamanho = "Copiando arquivo " + src + " com tamanho de " + formata_tamanho(file_size)
    print_log_dual(mensagem_tamanho)
    if not debug:
        atualizar_status_tarefa(cd_tarefa_atual, GEmAndamento, mensagem_tamanho)
    with open(src, 'rb') as fsrc:
        with open(dst, 'wb') as fdst:
            copia_com_status(file_size, fsrc, fdst)


while True:
    # Requisita uma tarefa
    print_log_dual("Solicitando tarefa ao servidor")
    (disponivel, tarefa) = sapisrv_obter_iniciar_tarefa(arg_tipo, storage=None)  # storage=nome_agente
    # Se não tem nenhuma tarefa disponível, espera um pouco
    if not disponivel:
        print_log_dual("Servidor informou que não existe tarefa para processamento. Esperando (", tempo_sleep,
                       " segundos)")

        dormir(tempo_sleep)
        if not debug:
            continue
    # var_dump(tarefa)
    # die("1")
    if debug:
        cd_tarefa_atual = 1
        caminho_origem = sys.argv[2]
        caminho_destino = sys.argv[3]
    else:
        cd_tarefa_atual = tarefa["codigo_tarefa"]  # Identificador único da tarefa
        caminho_origem = tarefa["caminho_origem"]
        caminho_destino = tarefa["caminho_destino"]
        sucesso, ponto_de_montagem_origem, erro_montagem = acesso_storage_windows(tarefa["dados_storage"], True)
        if sucesso:
            print_log_dual("montado ponto de origem: " + ponto_de_montagem_origem)

        sucesso, ponto_de_montagem_destino, erro_montagem = acesso_storage_windows(tarefa["dados_storage_entrega"],
                                                                                   True)
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
            atualizar_tarefa_com_espera(cd_tarefa_atual, GAbortou,
                                        "Falha copiando estrutura de diretórios - " + str(erro))
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
            continue
        diretorio_destino = os.path.dirname(caminho_destino)
        os.makedirs(diretorio_destino, exist_ok=True)
        try:
            copiar_arquivo_com_status(caminho_origem, caminho_destino)
        except OSError as erro:
            atualizar_tarefa_com_espera(cd_tarefa_atual, GAbortou, "Falha copiando arquivo - " + str(erro))
            print_log_dual(str(erro))
            continue
    else:  # não é nem arquivo nem diretório, deve falhar.
        atualizar_tarefa_com_espera(cd_tarefa_atual, GAbortou, "Falha - caminho de origem "
                                    + caminho_origem + " não é arquivo ou diretório")
        continue
    atualizar_tarefa_com_espera(cd_tarefa_atual, GFinalizadoComSucesso, "Cópia com sucesso")
    dormir(tempo_sleep)
