# -*- coding: utf-8 -*-
#
# ===== PYTHON 3 ======
#
# ======================================================================================================================
# SAPI - Sistema de Apoio a Procedimentos de Informática
#
# Componente: sapi_tableau
# Objetivo: Servidor para tratamento de imagem gerada pelo TD3/Tableau
# Funcionalidades:
#  - Conexão com o servidor SAPI para obter lista de tarefas de imagem
#  - Criação de pasta para armazenamento da imagem
#  - Verificação de situação de pasta de destino
#  - Atualização no servidor (SETEC3) da situação da tarefa
# Histórico:
#  - v1.0 : Inicial
# ======================================================================================================================

# ======================================================================
# Módulos necessários
# ======================================================================
from __future__ import print_function

import platform
import sys

try:
    import time
    import random
    import re
    import hashlib
    import shutil
    import multiprocessing
except ImportError:
    print("Falha na importação de módulos")
    # Não precisa nenhum tratamento adicional,
    # pois irá parar na verificação de versão abaixo

# ======================================================================
# Verifica se está utilizando versão correta do Python (3.0)
# ======================================================================
# Testa se está rodando a versão correta do python
if sys.version_info <= (3, 0):
    erro = "Versao do intepretador python (" + str(platform.python_version()) + ") incorreta.\n"
    sys.stdout.write(erro)
    sys.stdout.write("Este programa requer Python 3 (preferencialmente Python 3.5.2).\n")
    sys.exit(1)

# =======================================================================
# GLOBAIS
# =======================================================================
Gprograma = "sapi_tableau"
Gversao = "1.8.11"

#  Configuração e dados gerais
Gconfiguracao = dict()
Gcaminho_pid = "sapi_tableau_pid.txt"


# Cache de tarefas, para evitar releitura
Gcache_tarefa = dict()

# Pasta raiz do tableau (será definida durante a inicialização)
Gpasta_raiz_tableau = None

# Radical base a partir do qual se formam
# os nomes dos arquivos (.E01, .E02, .log, etc)
Gtableau_imagem = "image"


# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi.py, para evitar dependência
from sapilib_0_8_2 import *


# **********************************************************************
# PRODUCAO 
# **********************************************************************

# ===================================================================================
# Rotina Principal
# ===================================================================================
def main():
    # Processa parâmetros logo na entrada, para garantir que configurações
    # relativas a saída sejam respeitadas
    sapi_processar_parametros_usuario()

    #Teste da lixeira
    #pasta="Memorando_1880-17_CF_PR-26/item01Arrecadacao01a/item01Arrecadacao01a_imagem"
    #mover_lixeira(pasta)

    # Se não estiver em modo background (opção do usuário),
    # liga modo dual, para exibir saída na tela e no log
    if not modo_background():
        ligar_log_dual()

    # Cabeçalho inicial do programa
    # -----------------------------
    # Verifica se programa já está rodando (outra instância)
    if existe_outra_instancia_rodando(Gcaminho_pid):
        print("Já existe uma instância deste programa rodando.")
        print("Abortando execução, pois só pode haver uma única instância deste programa")
        sys.exit(0)

    # Inicialização do programa
    # -------------------------
    print_log(" ===== INÍCIO ", Gprograma, " - (Versao", Gversao, ")")

    # Inicializa programa
    if not inicializar():
        # Falhou na inicialização, talvez falha de comunicação, talvez mudança de versão...
        finalizar_programa()


    while True:
        (sucesso, msg_erro) = executar_tableau()
        if not sucesso:
            print_log("Execução do Tableau falhou: ", msg_erro)
            print_log("Abandonando programa para buscar estabilização")
            finalizar_programa()

        dormir(60, "Pausa entre ciclo de execução de tarefas do tableau")
        if not inicializar():
            # Falhou na inicialização, talvez falha de comunicação, talvez mudança de versão...
            # Irá finalizar, e o scheduler vai reiniciar o programa no próximo ciclo
            finalizar_programa()


# ===================================================================================
# Inicialização do agente
# Procedimento de inicialização
# Durante estes procedimento será determinado se comunicação a com servidor está ok,
# se este programa está habilitado para operar com o servidor, etc
# Existe um mecanismo para determinar automaticamente se será atualizado o servidor de desenvolvimento ou produção
# (ver documentação da função). Caso prefira definir manualmente, adicione ambiente='desenv' (ou 'prod')
# O nome do agente também é determinado por default através do hostname.
# ===================================================================================
def inicializar():
    global Gconfiguracao
    global Gpasta_raiz_tableau

    try:
        # Efetua inicialização
        # Neste ponto, se a versão do sapi_tableau estiver
        # desatualizada será gerado uma exceção
        print_log("Efetuando inicialização")
        # nome_arquivo_log = "log_sapi_tableau.txt"
        sapisrv_inicializar(Gprograma, Gversao,
                            auto_atualizar=True)
        print_log('Inicializado com sucesso', Gprograma, ' - ', Gversao)

        # Obtendo arquivo de configuração
        print_log("Obtendo configuração")
        Gconfiguracao = sapisrv_obter_configuracao_cliente(Gprograma)
        print_log(Gconfiguracao)

    except SapiExceptionProgramaFoiAtualizado as e:
        print_log("Programa foi atualizado para nova versão em: ", e)
        print_log("Encerrando para ser reinicializado em versão correta")
        # Encerra sem sucesso
        return False

    except SapiExceptionVersaoDesatualizada:
        print_log("sapi_tableau desatualizado. Não foi possível efetuar atualização automática. ")
        # Encerra sem sucesso
        return False

    except SapiExceptionProgramaDesautorizado:
        # Servidor sapi pode não estar respondendo (banco de dados inativo)
        # Logo, encerra e aguarda uma nova oportunidade
        print_log("AVISO: Não foi possível obter acesso (ver mensagens anteriores). Encerrando programa")
        # Encerra sem sucesso
        return False

    except SapiExceptionFalhaComunicacao:
        # Se versão do sapi_tableau está desatualizada, irá tentar se auto atualizar
        print_log("Comunição com servidor falhou.",
                  "Vamos encerrar e aguardar atualização, ",
                  "pois pode ser algum defeito no cliente")
        # Encerra sem sucesso
        return False

    except BaseException as e:
        # Para outras exceções exibe e encerra
        trc_string = traceback.format_exc()
        print_log("[168]: Exceção abaixo sem tratamento específico. ",
                  "Avaliar se deve ser tratada")
        print_log(trc_string)
        # Encerra sem sucesso
        return False


    # Determinação de pastas default
    Gpasta_raiz_tableau = montar_caminho(get_parini('raiz_storage'), "tableau")

    # Tudo certo
    return True


# ===================================================================================
# Executa tarefas do tableau
# ===================================================================================
def executar_tableau():
    try:
        return _executar_tableau()

    except BaseException as e:
        trc_string = traceback.format_exc()
        print_log("[207]: executar_tableau falhou, com exceção abaixo.")
        print_log(trc_string)
        return (False, "Exceção inesperada")

def _executar_tableau():

    # Recupera a lista de pasta das tarefas de imagem
    # -----------------------------------------------
    try:
        storage = Gconfiguracao["storage_unico"]
        print_log("Buscando tarefas de imagem para storage:", storage)
        (sucesso, msg_erro, tarefas_imagem) = sapisrv_chamar_programa(
            "sapisrv_obter_tarefas_imagem.php",
            {'storage': storage }
        )
    except BaseException as e:
        erro = "Não foi possível recuperar a situação atualizada das tarefas do servidor"
        # Provavelmente é um erro transiente (rede)
        # Mas para garantir, vamos encerrar o programa e tentar novamente mais tarde
        return (False, erro)

    if not sucesso:
        # Servidor não conseguiu executar...
        return (False, msg_erro)

    if len(tarefas_imagem)==0:
        print_log("Não existe nenhuma tarefa de imagem para ser processada")
        # Tudo certo, isto é normal
        return (True, "")

    print_log("Foram recuperadas", len(tarefas_imagem), "tarefas de imagem")

    for t in tarefas_imagem:

        codigo_tarefa = t['codigo_tarefa']
        codigo_situacao_tarefa = int(t['codigo_situacao_tarefa'])

        if codigo_situacao_tarefa == GFilaCriacaoPasta:
            # Se está na fila para criação de pasta,
            # Cria pasta para tarefa
            criar_pasta_tableau(codigo_tarefa)
        elif codigo_situacao_tarefa == GAguardandoPCF :
            # Se está aguardando PCF,
            # Verifica se upload já iniciou
            monitorar_tarefa(codigo_tarefa)
        elif codigo_situacao_tarefa == GAbortou :
            # Se tarefa abortou,
            # verifica se foi reiniciada
            monitorar_tarefa(codigo_tarefa)
        elif codigo_situacao_tarefa == GTableauExecutando:
            # Se já está executando, monitora tarefa
            monitorar_tarefa(codigo_tarefa)
        # Isto aqui será efetuado pelo sapi_aquisicao
        #elif codigo_situacao_tarefa == GFilaExclusao:
        #    # Se já está executando, monitora tarefa
        #    excluir_tarefa(codigo_tarefa)
        else:
            # Nada a fazer para as demais situações
            print_log("Nenhuma ação tomada para tarefa", codigo_tarefa, "que está com situação", codigo_situacao_tarefa)

        # Fazemos uma pausa aqui, para evitar que os processos fiquem muito sincronizado
        # pois isto dificulta a análise do arquivo de log
        time.sleep(10)

    # Tudo certo
    return (True, "")

# Obtem dados de uma tarefa
# Armazena em cache, para evitar sobrecarregar o servidor
def obter_tarefa_cache(codigo_tarefa):

    global Gcache_tarefa

    # Se já está em cache, retorna valor armazenado
    if codigo_tarefa in Gcache_tarefa:
        # Está em cache. Retorna valor do cache
        return Gcache_tarefa[codigo_tarefa]

    # Recupera tarefa do servidor
    print_log("Buscando dados da tarefa", codigo_tarefa)
    tarefa = recupera_tarefa_do_setec3(codigo_tarefa)
    print_log("Dados recuperados")

    # Armazena em cache
    Gcache_tarefa[codigo_tarefa] = tarefa

    # Retorna valor recuperado e armazenado
    return Gcache_tarefa[codigo_tarefa]


# Retorna o caminho para a pasta temporária do tableau da tarefa
def obter_caminho_pasta_tableau(tarefa):

    #var_dump(tarefa)
    #die('ponto282')

    # identificador do sujeito responsável pelo exame
    dados_exame = tarefa["dados_solicitacao_exame"]["dados_exame"]
    nome = dados_exame["nome_guerra_sujeito_posse"]
    matricula = dados_exame["matricula_sujeito_posse"]
    sujeito = nome + "_" + matricula

    # Protocolo
    protocolo = tarefa["dados_solicitacao_exame"]["numero_protocolo"]
    protocolo = protocolo.zfill(4)
    #protocolo = "p_" + protocolo + "_" + tarefa["dados_solicitacao_exame"]["ano_protocolo"]
    ano = tarefa["dados_solicitacao_exame"]["ano_protocolo"]
    ano = ano[-2:]
    # Tirei o ano, para ficar mais curto
    protocolo = "p" + protocolo + "_" + ano
    protocolo = sanitiza_parte_caminho(protocolo)

    # Material
    material = "m" + tarefa["dados_item"]["material_simples"]
    material = sanitiza_parte_caminho(material)
    # Vamos tirar a palavra parte, para deixar mais enxuto
    material = material.replace("_parte", "")

    # Agrupa
    pasta_material = montar_caminho(sujeito, protocolo, material)
    pasta_tableau  = montar_caminho(Gpasta_raiz_tableau, pasta_material)

    #var_dump(pasta_tableau)
    #var_dump(pasta_material)
    #die('ponto302')

    return (pasta_tableau, pasta_material)


# Cria pasta temporária para o tableau, caso ainda não exista
def criar_pasta_tableau(codigo_tarefa):

    label_log = "[Tarefa " + str(codigo_tarefa) + "]"

    print_log(label_log, "Criação de pasta para tarefa")

    # Recupera tarefa
    # ------------------------------------------------------------------
    tarefa = obter_tarefa_cache(codigo_tarefa)
    if tarefa is None:
        print_log(label_log, "Criação de pasta falhou, pois não foi possível recuperar tarefa")
        return False

    #var_dump(tarefa)
    #die('ponto308')

    # Nome do storage
    nome_storage = tarefa["dados_storage"]["maquina_netbios"]

    # Verifica se pasta temporária para tableau existe
    # ------------------------------------------------------------------
    if not os.path.exists(Gpasta_raiz_tableau):
        print_log("Não foi encontrada pasta raiz do tableau: ", Gpasta_raiz_tableau)
        print_log("Criando pasta: ", Gpasta_raiz_tableau)
        os.makedirs(Gpasta_raiz_tableau)

    if not os.path.exists(Gpasta_raiz_tableau):
        print_log(label_log, "ERRO: Pasta raiz do tableau não foi encontrada: ", Gpasta_raiz_tableau)
        print_log(label_log, "Não é possível criar pasta para a tarefa.")
        print_log(label_log, "Siga o roteiro de instalação do storage conforme definido na Wiki do SAPI")

    # Pasta para a tarefa
    # Ficou meio longo com a pasta do memorando
    # tarefa["dados_solicitacao_exame"]["pasta_memorando"]
    # Vamos mostrar apenas o número do protocolo
    (pasta_tableau, pasta_material) = obter_caminho_pasta_tableau(tarefa)
    print_log(label_log, "Pasta temporária do tableau associada a tarefa: ", pasta_tableau)

    # Se pasta não existe, cria
    if os.path.exists(pasta_tableau):
        print_log(label_log, "Pasta tableau já existe")
    else:
        # Cria pasta de destino
        try:
            print_log(label_log, "Criando pasta", pasta_tableau)
            os.makedirs(pasta_tableau)
            print_log(label_log, "Pasta criada")
        except Exception as e:
            erro = "Não foi possível criar pasta: " + str(e)
            # Pode ter alguma condição temporária impedindo. Continuar tentando.
            return False

    # Se a pasta final (que fica sob o memorando tiver conteúdo),
    # transfere o conteúdo para a pasta temporária do tableau
    # para ser reprocessada
    # Esta é uma atividade executada apenas em ambiente de desenvolvimento
    if ambiente_desenvolvimento():
        recupera_dados_pasta_destino(tarefa)

    # Simula um erro irrecuperável, trocando o código de tarefa para uma inexistente
    #codigo_tarefa=12345095

    # Se pasta de destino existe, atualiza a situação de tarefa para GAguardandoPCF
    if os.path.exists(pasta_tableau):
        sapisrv_troca_situacao_tarefa_loop(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=GAguardandoPCF,
            texto_status=texto("Pasta para recepção de tableau criada em",
                               pasta_tableau,
                               "no storage",
                               nome_storage)
        )

    # Tudo certo
    return True

# Se pasta de destino contém dados que foram originários do sapi_tableau
# move dados novamente para pasta do tableau, para novo processamento
def recupera_dados_pasta_destino(tarefa):

    caminho_destino = tarefa["caminho_destino"]
    (pasta_destino, pasta_item, nome_base) = decompor_caminho_destino_imagem(caminho_destino)

    # Se pasta de destino não contém dados, nada a fazer
    if obter_tamanho_pasta_ok(pasta_destino) == 0:
        return

    print_log("Pasta de destino", pasta_destino, "contém dados")

    # Recupera sapi_tableau armazenados no sapi.info
    sapi_info = sapi_info_carregar(pasta_destino)
    if sapi_info is None:
        return
    sapi_tableau = sapi_info.get('sapi_tableau', None)
    if sapi_tableau is None:
        print_log("Dados da pasta destino NÃO são provenientes do tableau")
        return

    #var_dump(sapi_tableau)
    #die('ponto410')

    #
    pasta_origem = sapi_tableau["pasta_origem"]
    base_nome_original = sapi_tableau["base_nome_original"]
    base_nome_novo = sapi_tableau["base_nome_novo"]
    print_log("Dados da pasta de destino são provenientes do tableau")

    try:
        print_log("Movendo dados da pasta", pasta_destino, "para", pasta_origem)
        #die('ponto422')
        mover_pasta_storage(pasta_destino, pasta_origem)
        print_log("Movimentado com sucesso")
    except Exception as e:
        erro = "Não foi possível mover: " + str(e)
        print_log(erro)
        return

    print_log("Renomeando arquivos recuperados")
    try:
        # Ajusta nomes dos arquivos na pasta de destino
        for nome_arquivo in os.listdir(pasta_origem):
            nome_arquivo=montar_caminho(pasta_origem, nome_arquivo)
            if not os.path.isfile(nome_arquivo):
                continue
            # Volta ao nome original
            if base_nome_novo in nome_arquivo:
                nome_novo = nome_arquivo.replace(base_nome_novo, base_nome_original)
                print_log("Renomeando",nome_arquivo, "para", nome_novo)
                os.rename(nome_arquivo, nome_novo)

    except Exception as e:
        # Isto não deveria acontecer nunca
        erro = "Não foi possível ajustar nomes dos arquivos: " + str(e)
        print_log(erro)
        return

    print_log("Recuperação de dados da pasta de destino efetuada com sucesso")
    return





# Monta label do processo de acompanhamento
def get_label_processo_acompanhamento(codigo_tarefa):
    label_processo = "acompanhar:" + str(codigo_tarefa)
    return label_processo


# Retorna verdadeiro se a tarefa já está sendo acompanhada
def tarefa_sendo_acompanhada(codigo_tarefa):

    # Monta label do processo de acompanhamento
    label_processo = get_label_processo_acompanhamento(codigo_tarefa)

    # Verifica se existe processo
    if Gpfilhos.get(label_processo, None) is None:
        # Não existe processo de acompanhamento para esta tarefa
        return False

    # Verifica se processo está ativo
    if Gpfilhos[label_processo].is_alive():
        return True

    # Processo não está mais ativo
    return False

def monitorar_tarefa(codigo_tarefa):
    # Se tarefa já iniciou e está sendo acompanhada,
    # não há mais nada a fazer
    if tarefa_sendo_acompanhada(codigo_tarefa):
        # Não tem mais nada a fazer
        print_log("Tarefa", codigo_tarefa, "já está sendo monitorada")
        return True


    print_log("Inicio de monitoramento da tarefa", codigo_tarefa)

    # Recupera dados da tarefa do cache,
    # para evitar sobrecarregar o servidor com requisições
    tarefa = obter_tarefa_cache(codigo_tarefa)

    # Pasta para a tarefa
    (pasta_tableau, pasta_material) = obter_caminho_pasta_tableau(tarefa)
    print_log("Pasta de tableau da tarefa: ", pasta_tableau)

    # Se pasta não existe, tem algo erro aqui
    if not os.path.exists(pasta_tableau):
        # Isto aqui não deveria acontecer nunca...foi feita exclusão manual?
        erro = texto("Pasta do tableau não existe", pasta_tableau)
        sapisrv_reportar_erro_tarefa(codigo_tarefa, erro)
        return False

    # Se pasta da tarefa está vazia,
    # ou seja, ainda não foi iniciado o upload,
    # então não tem nada a fazer
    # Recupera tamanho da pasta
    carac = obter_caracteristicas_pasta_ok(pasta_tableau)
    if carac is None:
        return False

    if carac["tamanho_total"] == 0:
        # Pasta está zerada (tamanho zero)
        # Logo, ainda não tem nada a fazer
        print_log("Tarefa ainda sem dados na pasta de temporária. Aguardar início do tableau")
        return False

    # Acompanha execução da tarefa de cópia
    deu_erro = False
    erro_exception = None
    try:

        # Transferi para posição após constatar que existe uma subpasta a ser processada
        # O tamanho só não é indicativo, pois a pasta existente pode ser uma pasta com ERRO
        # if int(tarefa["codigo_situacao_tarefa"]) != GTableauExecutando:
        #     # Registra comando de execução do IPED
        #     sapisrv_troca_situacao_tarefa_loop(
        #         codigo_tarefa=codigo_tarefa,
        #         codigo_situacao_tarefa=GTableauExecutando,
        #         texto_status="Pasta do tableau contém dados"
        #     )
        codigo_situacao_tarefa=int(tarefa["codigo_situacao_tarefa"])

        # Inicia processo para acompanhamento em background
        print_log("Tarefa: ", codigo_tarefa, "Pasta do tableau tem conteúdo. Iniciando acompanhamento")

        # Inicia subprocesso para acompanhamento do Tableau
        # ------------------------------------------------
        nome_arquivo_log = obter_nome_arquivo_log()
        dados_pai_para_filho = obter_dados_para_processo_filho()
        label_processo = get_label_processo_acompanhamento(codigo_tarefa)
        item = tarefa["item"]
        caminho_destino = tarefa["caminho_destino"]

        (pasta_destino, pasta_item, nome_base)=decompor_caminho_destino_imagem(caminho_destino)

        # Adiciona raiz do storage nas pastas
        # Desta forma, não importa em qual pasta o sapi_tableau é iniciado
        # O caminho será sempre relativo à raiz do storage
        pasta_destino = montar_caminho(get_parini('raiz_storage'), pasta_destino)
        pasta_item = montar_caminho(get_parini('raiz_storage'), pasta_item)

        # Inicia tarefa em background
        # ----------------------------
        p_acompanhar = multiprocessing.Process(
            target=background_acompanhar_tableau,
            args=(codigo_tarefa,
                  item,
                  pasta_tableau,
                  pasta_item,
                  pasta_destino,
                  nome_base,
                  nome_arquivo_log,
                  label_processo,
                  dados_pai_para_filho,
                  codigo_situacao_tarefa
                  )
        )
        p_acompanhar.start()
        registra_processo_filho(label_processo, p_acompanhar)

    except subprocess.CalledProcessError as e:
        # Se der algum erro, não volta nada acima, mas tem como capturar pegando o output da exception
        erro_exception = str(e.output)
        deu_erro = True
    except Exception as e:
        # Alguma outra coisa aconteceu...
        erro_exception = str(e)
        deu_erro = True

    if deu_erro:
        print_log("Erro na chamada do acompanhamento de tarefa: ", erro_exception)
        return False

    #time.sleep(100)
    #print("Interrompendo principal para iniciar apenas uma tarefa")
    #die('ponto1784')

    # Ok, tudo certo. O resto é com o processo em background
    return True


# Acompanha a execução do Tableau e atualiza o status da tarefa
def background_acompanhar_tableau(
        codigo_tarefa,
        item,
        pasta_tableau,
        pasta_item,
        pasta_destino,
        nome_base,
        nome_arquivo_log,
        label_processo,
        dados_pai_para_filho,
        codigo_situacao_tarefa):

    # Restaura dados herdados do processo pai
    restaura_dados_no_processo_filho(dados_pai_para_filho)

    # Se não estiver em modo background (opção do usuário),
    # liga modo dual, para exibir saída na tela e no log
    if not modo_background():
        ligar_log_dual()

    # Inicializa sapilib
    # Será utilizado o mesmo arquivo de log do processo pai
    sapisrv_inicializar(nome_programa=Gprograma,
                        versao=Gversao,
                        nome_arquivo_log=nome_arquivo_log,
                        label_processo=label_processo
                        )

    print_log("Processo de acompanhamento de tarefa de imagem Tableau iniciado")

    try:
        erro=None
        # Executa acompanhamento de tableau, capturando e registrando qualquer erro ocorrido
        _background_acompanhar_tableau(
            codigo_tarefa,
            item,
            pasta_tableau,
            pasta_item,
            pasta_destino,
            nome_base,
            codigo_situacao_tarefa)
    except BaseException as e:
        # Qualquer outra coisa
        trc_string = traceback.format_exc()
        erro="[671]: ERRO: Exceção sem tratamento: " + trc_string

    if erro is not None:
        print_log(erro)
        # Atualiza erro na situação da tarefa
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status=erro
        )
        os._exit(1)

    # Fim normal
    print_log("Processo de acompanhamento de tarefa de imagem Tableau finalizado normalmente")
    # Na realidade não retornar para lugar nenhum, pois é um processo em background.
    # Irá simplesmente finalizar
    return


def _background_acompanhar_tableau(
        codigo_tarefa,
        item,
        pasta_tableau,
        pasta_item,
        pasta_destino,
        nome_base,
        codigo_situacao_tarefa):

    # Fica em loop infinito.
    # Será encerrado quando não tiver mais nada a fazer,
    # ou então pelo pai (kill)
    tam_pasta_tableau = 0
    while True:

        # Se pasta do Tableau não existe, não tem o que acompanhar
        # Isto não deveria acontecer
        if not os.path.exists(pasta_tableau):
            print_log("Pasta para tableau não existe:", pasta_tableau)
            print_log("Abandonando acompanhamento desta tarefa")
            return

        # Verifica quantas subpastas ok para processamento existem no pasta do tableau
        # Não pode ter mais do que uma pasta, pois isto indica
        # que o usuário está duplicando mais do que um material para a
        # mesma pasta temporária o tableau...pode ter se enganado de material.
        # -------------------------------------------------------------------------------
        qtd_pastas_ok = 0
        for dirpath, dirnames, filenames in os.walk(pasta_tableau):
            for sub in dirnames:
                print_log("Verificada presença de subpasta", sub)

                # Despreza pasta que foi anteriormente classificada como duplicação com erro
                if "ERRO" in sub:
                    print_log("Desprezada subpasta pois contém indicativo de erro")
                    continue

                # caminho completo para a subpasta
                subpasta_caminho_completo=montar_caminho(dirpath, sub)

                # Vamos ver se esta pasta está pronta para ser processada
                if not subpasta_contem_primeiro_arquivo(subpasta_caminho_completo, nome_base):
                    print_log("Desprezada subpasta pois ainda não contém arquivo indicando início de imagem do tableau")
                    continue

                # Vamos ver se a subpasta contém duplicação abortada
                # Para isto, é necessário que tenha arquivo de log,
                # e o arquivo de log indique que ocorreu erro
                (encontrado_log, caminho_arquivo_log) = existe_arquivo_log_tableau(subpasta_caminho_completo, nome_base)
                if encontrado_log:
                    print_log("Pasta já possui arquivo de log")
                    # Verifica se log indica que duplicação falhou
                    (sucesso, erro_log, dados_relevantes) = tableau_parse_arquivo_log(caminho_arquivo_log, item)
                    if sucesso:
                        print_log("Arquivo de log indica sucesso")
                    else:
                        # Renomeia pasta com erro, e interrompe este ciclo
                        print_log("Arquivo de log indica falha: ", erro_log)
                        print_log("Renomeando pasta para _ERRO e interrompendo ciclo")
                        renomear_pasta_com_erro_e_abortar(subpasta_caminho_completo, codigo_tarefa, erro_log)
                        return

                # Ok, pasta está pronta para ser processada
                qtd_pastas_ok += 1
                subpasta_processar = subpasta_caminho_completo
                print_log("Pasta ok para ser processada:", subpasta_processar)


        # ---------------------------------------------------------------------------------------
        # Agora que varreu todas as subpastas, vamos ver como ficou
        # Se tiver zero subpastas, fica aguardando
        # Se tiver mais do que uma, tem algo erro, e neste caso aborta a tarefa
        # Se tiver exatamente uma subpasta, está tudo certo, e continua monitorando esta subpasta
        # ---------------------------------------------------------------------------------------
        # Se não tem nenhuma subpasta,
        # encerra o acompanhamento
        if qtd_pastas_ok==0:
            # Pode ser que só tivesse uma pasta de erro
            print_log("Nenhuma subpasta disponível para processamento. Finalizando subprocesso")
            return

        # Se tiver mais do que uma pasta, tem algo errado
        # Será necessária a intervenção manual do perito
        if qtd_pastas_ok > 1:
            print_log("Existe mais de uma subpasta para processamento:", qtd_pastas_ok)
            # Se ainda não está abortado, aborta
            if int(codigo_situacao_tarefa) != int(GAbortou):
                print_log("Abortando tarefa")
                texto_status = \
                texto("Existe mais de uma subpasta na pasta",
                      pasta_tableau,
                      "É possível que você tenha se equivocado na seleção da pasta do tableau, ",
                      "e existam dois processos de duplicação em andamento de materiais distintos para esta mesma pasta.",
                      "Se for este o caso, cancele a duplicação incorreta no Tableau (botão CANCELAR),",
                      "aguarde alguns minutos, e tudo voltará ao normal.")
                sapisrv_abortar_tarefa(codigo_tarefa, texto_status)
            else:
                print_log("Tarefa já está abortada. Nada a ser feito")
            return

        # Ok, temos apenas uma pasta, Tudo certo até aqui
        # ------------------------------------------------

        # Se ainda não está no estado de execução, ajusta
        if int(codigo_situacao_tarefa) != int(GTableauExecutando):
            # Registra comando de execução do IPED
            codigo_situacao_tarefa=GTableauExecutando
            sapisrv_troca_situacao_tarefa_loop(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=GTableauExecutando,
                texto_status=texto("Pasta do tableau contém subpasta com dados:", subpasta_processar)
            )

        # Se já tem arquivo de log, interrompe loop para finalizar processamento da pasta
        if encontrado_log:
            print_log("Encontrado arquivo de log:", caminho_arquivo_log)
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status=texto("Detectado existência de arquivo de log, "
                                   "indicando que tableau finalizou")
            )
            print_log("Interrompe loop de acompanhamento. Será analisado resultado")
            break

        # Ainda não tem arquivo de log
        # Como ainda não tem arquivo de log, apenas atualiza a situação atual
        print_log("Ainda não existe arquivo de log. Apenas atualiza situação atual (tamanho)")

        # Calcula o tamanho da pasta do tableau e atualiza
        carac = obter_caracteristicas_pasta_ok(subpasta_processar)
        if carac is not None:
            tam_pasta_tableau = carac.get("tamanho_total", None)
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status="Tamanho atual da pasta temporária do tableau: " + converte_bytes_humano(tam_pasta_tableau),
                tamanho_destino_bytes = tam_pasta_tableau
            )
        else:
            print_log("Falhou na determinação do tamanho da pasta do tableau")

        # Pausa para evitar sobrecarga no servidor
        dormir(60, "pausa entre atualizações de status")

        # Fim do While - Fica em loop até achar arquivo de log
        # ou surgir alguma outra situação inesperada
        # ----------------------------------------------------


    # =========================================================================================
    # Saiu do loop
    # Se chegou até aqui, indica que o processamento terminou com sucesso
    # Ou seja, tem log, e o log indica conclusão com sucesso
    # =========================================================================================

    # Faz upload do arquivo de log do tableau
    # -------------------------------------------------------------------------------
    conteudo_log = ""
    # Upload do resultado do IPED
    with open(caminho_arquivo_log, "r") as fentrada:
        for linha in fentrada:
            conteudo_log += linha

    sapisrv_armazenar_texto_tarefa(codigo_tarefa, 'Log do tableau', conteudo_log)

    # Ajusta nomes dos arquivos de imagem e log, para ficarem com nomes padronizados
    # Exemplo: item01Arrecadacao01.E01
    # Ajusta nomes dos arquivos na pasta de destino
    # Exemplo: tableau-imagem.E01 => item01Arrecadacao01.E01
    # -------------------------------------------------------------------------------
    try:
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="Ajustando nomes de arquivos da pasta definitiva"
        )

        # Ajusta nomes dos arquivos na pasta de destino
        for nome_arquivo in os.listdir(subpasta_processar):

            nome_arquivo=montar_caminho(subpasta_processar, nome_arquivo)

            if not os.path.isfile(nome_arquivo):
                continue

            if (Gtableau_imagem not in nome_arquivo and
                nome_base not in nome_arquivo):
                print_log("Arquivo inesperado na pasta de destino: ", nome_arquivo)
                continue

            nome_novo = nome_arquivo.replace(Gtableau_imagem, nome_base)
            print_log("Renomeando",nome_arquivo, "para", nome_novo)
            os.rename(nome_arquivo, nome_novo)

        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="Nomes de arquivos ajustados"
        )

    except Exception as e:
        # Isto não deveria acontecer nunca
        erro = "Não foi possível ajustar nomes dos arquivos: " + str(e)
        sapisrv_abortar_tarefa(codigo_tarefa, erro)
        return



    # Move pasta temporária para pasta definitiva. Exemplo:
    # De:   tableau\Ronaldo_14940\p_00943_17\m_1023_17_2\2017-10-05_09-01-05
    # para: Memorando_1880-16\item01Arrecadacao02\item01Arrecadacao02_imagem
    # -------------------------------------------------------------------------------
    try:
        moveu_sucesso=False
        # Se pasta de destino já existe, move para lixeira
        # Isto pode acontecer se a tarefa foi reiniciada
        if os.path.exists(pasta_destino):
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status="Pasta de destino já existe. Movendo para lixeira"
            )
            # Move pasta de destino para lixeira
            mover_lixeira(pasta_destino)

        # Se pasta pai (do item) não existe, cria
        if not os.path.exists(pasta_item):
            os.makedirs(pasta_item)

        # Move pasta temporária para definitiva
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="Movendo pasta temporária para definitiva"
        )
        mover_pasta_storage(subpasta_processar, pasta_destino)

        # Adiciona no arquivo sapi.info a pasta de origem
        # Este arquivo posteriormente permite identificar qual a foi a origem da pasta
        sapi_tableau=dict()
        sapi_tableau['pasta_origem']=subpasta_processar
        sapi_tableau['base_nome_original']=Gtableau_imagem
        sapi_tableau['base_nome_novo']=nome_base
        sapi_info_set(pasta_destino, 'sapi_tableau', sapi_tableau)
        print_log("Registrado situação em sapi.info")

        # Movimentação concluída
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status=texto("Pasta temporária movida para pasta definitiva", pasta_destino)
        )
        moveu_sucesso=True
    except Exception as e:
        # Isto não deveria acontecer nunca
        moveu_sucesso = False
        trc_string = traceback.format_exc()
        erro = texto("[891] ** ERRO na movimentação da pasta",
                     subpasta_processar,
                     trc_string)
        print_log(erro)

    # Se movimentação falhou, aborta tarefa
    if not moveu_sucesso:
        sapisrv_abortar_tarefa(codigo_tarefa, erro)
        return

    # Exclusão da pasta temporária do Tableau
    # ---------------------------------------
    try:
        erro = None
        excluir_pasta_temporaria_tableau(codigo_tarefa, pasta_tableau)
    except Exception as e:
        # Se ocorrer algo inesperado, guarda no log
        trc_string = traceback.format_exc()
        erro = texto("[947] ERRO na exclusão da pasta temporária do tableau",
                     e,
                     trc_string)

    # Se falhar a exclusão da pasta temporária, prosseguimos, pois isto não é essencial
    if erro is not None:
        # Apenas registra em log
        print_log(erro)
        # Prossegue

    # Atualiza situação da tarefa para sucesso
    # ----------------------------------------
    sapisrv_troca_situacao_tarefa_loop(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=GFinalizadoComSucesso,
        texto_status="Imagem do Tableau finalizada com sucesso",
        dados_relevantes=dados_relevantes,
        tamanho_destino_bytes=tam_pasta_tableau
    )
    print_log("Tarefa de imagem do tableau finalizada com sucesso")


# Verifica se já tem o primeiro arquivo
# Por convenção (fixado no tableau), grava será
# image.E01.partial (se ainda não terminou o primeiro arquivo)
# image.E01 (se já terminou o primeiro arquivo)
# Se pasta já foi renomeada, então será algo como
# item01Arrecadacao01.E01
# Retorna: True/False
def subpasta_contem_primeiro_arquivo(subpasta, nome_base):
    nome_possiveis = list()
    for prefixo in (Gtableau_imagem, nome_base):
        for sufixo in (".E01", ".E01.partial"):
            nome_arquivo = prefixo + sufixo
            nome_possiveis.append(nome_arquivo)

    for nome_arquivo in nome_possiveis:
        caminho_primeiro_arquivo = montar_caminho(subpasta, nome_arquivo)
        if os.path.isfile(caminho_primeiro_arquivo):
            print_log("Encontrado arquivo", caminho_primeiro_arquivo)
            # Ok, achou o arquivo
            return True
        else:
            print_log("Não foi encontrado arquivo", caminho_primeiro_arquivo)

    # Não econtrado arquivo
    print_log("Não foi encontrado nenhum arquivo que indique início de imagem")
    return False


# Verifica se já existe arquivo de log do tableau
def existe_arquivo_log_tableau(subpasta_processar, nome_base):
    print_log("Verificando se já existe arquivo de log")
    encontrado_log = False
    for prefixo in (Gtableau_imagem, nome_base):
        arquivo_log = prefixo + ".log"
        caminho_arquivo_log = montar_caminho(subpasta_processar, arquivo_log)
        if os.path.isfile(caminho_arquivo_log):
            encontrado_log = True
            return (True, caminho_arquivo_log)
        else:
            print_log("Não encontrado arquivo", arquivo_log)

    # Não foi encontrado arquivo de log
    return (False, None)


# Renomeia a pasta que está com problema,
# para não ser mais reprocessada
# Adicionar o sufixo "_ERRO"
def renomear_pasta_com_erro_e_abortar(subpasta_processar, codigo_tarefa, erro_log):

    try:
        erro = texto("Duplicação na pasta", subpasta_processar, "foi abortada com erro:", erro_log)
        subpasta_renomeada = subpasta_processar + "_ERRO"
        os.rename(subpasta_processar, subpasta_renomeada)
        erro = texto(erro, "Pasta com erro foi renomeada para ", subpasta_renomeada)
    except Exception as e:
        # Não conseguiu renomear
        erro = texto(erro," [1043] Além disso, tentativa de renomear pasta com erro", subpasta_processar, "também falhou :", e)

    # Aborta tarefa
    sapisrv_abortar_tarefa(codigo_tarefa, erro)
    return


# Exclusão da pasta temporária do Tableau
# Se este procedimento falhar, não tem problema,
# pois poderá ser feita exclusão manual posteriormente
# -----------------------------------------------------------------------------------------
def excluir_pasta_temporaria_tableau(codigo_tarefa, pasta_tableau):

    print_log("Tratamento/exclusão da pasta temporária do tableau:", pasta_tableau)

    # 1) Move as pastas de duplicação marcadas com _ERRO para a lixeira,
    #    para ser mais rápido
    # -------------------------------------------------------------------------
    # Primeiro, move para a lixeira todas as subpastas que abortaram
    for dirpath, dirnames, filenames in os.walk(pasta_tableau):
        for subpasta_erro in dirnames:
            # Despreza pasta que foi classificada com erro
            if "ERRO" in subpasta_erro:
                subpasta_erro = montar_caminho(dirpath, subpasta_erro)
                print_log("Movendo para lixeira a subpasta", subpasta_erro)
                (sucesso, pasta_lixeira) = mover_lixeira(subpasta_erro)
                if sucesso:
                    sapisrv_atualizar_status_tarefa_informativo(
                        codigo_tarefa=codigo_tarefa,
                        texto_status=texto("Movido subpasta com falha de execução do tableau",
                                           subpasta_erro,
                                           "para lixeira",
                                           pasta_lixeira)
                    )
                else:
                    print_log("Movimentação para lixeira da pasta", subpasta_erro, "falhou")
            else:
                print_log("Pasta do tableau contém subpasta inesperada:", subpasta_erro)



    # 2) Exclui a pasta tableau referente ao material
    # -------------------------------------------------------------------------
    # Se não sobrou nenhum conteúdo na pasta temporária, pode excluir
    print_log("Verificando se é possível excluir pasta tableau:", pasta_tableau)
    if excluir_pasta_se_vazia(pasta_tableau):
        # Exclusão ok
        print_log("Pasta tableau excluída com sucesso:", pasta_tableau)
    else:
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status=texto("AVISO: Não foi possível excluir pasta temporária do tableau",
                               pasta_tableau,
                               "Normalmente isto indica que a pasta ainda contém arquivos.",
                               "Verifique se não foi feita algum upload por engano para esta pasta")
        )
        return False

    # 3) Se pasta do protocolo estiver vazia, será excluída
    #    O mesmo se aplica para a pasta do perito
    #    A ideia é manter a pasta do tableau o mais limpo possível, para evitar confusão
    # ---------------------------------------------------------------------------------------
    pasta_protocolo=obter_pasta_pai(pasta_tableau)
    print_log("Verificando se deve excluir pasta do protocolo:", pasta_protocolo)
    if excluir_pasta_se_vazia(pasta_protocolo):
        # Se pasta do perito estiver vazia, será excluída
        pasta_perito = obter_pasta_pai(pasta_protocolo)
        print_log("Verificando se deve excluir pasta do perito:", pasta_perito)
        excluir_pasta_se_vazia(pasta_perito)

    # Tudo certo
    return True


# Abortar execução do programa
# Esta rotina é invocada quando alguma situação exige que para a restauração da ordem
# o ambiente seja reiniciado
def finalizar_programa():
    print_log("Iniciando procedimento de encerramento do programa")
    print_log("Verificando se existem processos filhos a serem encerrados")
    for ix in sorted(Gpfilhos):
        if Gpfilhos[ix].is_alive():
            # Finaliza processo
            pid =  Gpfilhos[ix].pid
            print_log("Finalizando processo ", ix, " [", pid, "]")
            kill_pai_e_filhos(pid, including_parent=True)

    # Para garantir, aguarda caso ainda tenha algum processo não finalizado...NÃO DEVERIA ACONTECER NUNCA
    # --------------------------------------------------------------------------------------------------------------
    repeticoes = 0
    while True:
        # Uma pequena pausa para dar tempo dos processos finalizarem
        lista = multiprocessing.active_children()
        qtd = len(lista)
        if qtd == 0:
            # Tudo certo
            print_log("Não resta nenhum processo filho")
            break
        repeticoes = repeticoes + 1
        if repeticoes > 5:
            print_tela_log("Aguardando encerramento de", len(lista), "processo(s). Situação incomum!")
        # Aguarda e repete, até finalizar tudo...isto não deveria acontecer....
        time.sleep(2)

    # Ok, tudo encerrado
    # -----------------------------------------------------------------------------------------------------------------
    print_log(" ===== FINAL ", Gprograma, " - (Versao", Gversao, ")")
    os._exit(1)


# ----------------------------------------------------------------------------------
# Chamada para rotina principal
# ----------------------------------------------------------------------------------
if __name__ == '__main__':


    # Executa rotina principal
    main()
