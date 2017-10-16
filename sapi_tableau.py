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
Gversao = "1.8.1"

#  Configuração e dados gerais
Gconfiguracao = dict()
Gcaminho_pid = "sapi_tableau_pid.txt"


# Configuração de limites para avisos
# Irá gerar mensagem de aviso,
# caso este percencutal de erros de leitura seja ultrapassado
GlimitePercentualErroLeitura = 1

# Cache de tarefas, para evitar releitura
Gcache_tarefa = dict()

# Pasta raiz do tableau (será definida durante a inicialização)
Gpasta_raiz_tableau = None

# Radical base a partir do qual se formam
# os nomes dos arquivos (.E01, .E02, .log, etc)
Gtableau_imagem = "image"

# Tipo de componente, para que laudo possa montar descrição adequada
Gsapi_tipo_componente = 'armazenamento'

# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi.py, para evitar dependência
from sapilib_0_8_1 import *


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
        executar()
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
def executar():
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
        return (False, erro)

    if not sucesso:
        return (False, msg_erro)

    # var_dump(sucesso)
    # var_dump(tarefas_imagem)
    # die('ponto1581')

    if len(tarefas_imagem)==0:
        print_log("Não existe nenhuma tarefa de imagem para ser processada")
        return

    print_log("Foram recuperadas", len(tarefas_imagem), "tarefas de imagem")

    for t in tarefas_imagem:

        codigo_tarefa = t['codigo_tarefa']
        codigo_situacao_tarefa = int(t['codigo_situacao_tarefa'])

        if codigo_situacao_tarefa == GFilaCriacaoPasta:
            # Se está na fila para criação de pasta,
            # Cria pasta para tarefa
            criar_pasta_tableau(codigo_tarefa)
        elif codigo_situacao_tarefa == GAguardandoPCF:
            # Se está aguardando PCF,
            # Verifica se upload já iniciou
            monitorar_tarefa(codigo_tarefa)
        elif codigo_situacao_tarefa == GTableauExecutando:
            # Se já está executando, monitora tarefa
            monitorar_tarefa(codigo_tarefa)
        else:
            # Nada a fazer para as demais situações
            print_log("Nenhuma ação tomada para tarefa", codigo_tarefa, "que está com situação", codigo_situacao_tarefa)



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
    protocolo = protocolo.zfill(5)
    # Tirei o ano, para ficar mais curto
    #protocolo = "p_" + protocolo + "_" + tarefa["dados_solicitacao_exame"]["ano_protocolo"]
    protocolo = "p_" + protocolo + "_" + tarefa["dados_solicitacao_exame"]["ano_protocolo"]
    protocolo = sanitiza_parte_caminho(protocolo)

    # Material
    material = "mt_" + tarefa["dados_item"]["material_simples"]
    material = sanitiza_parte_caminho(material)

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
    (pasta_destino, pasta_item, nome_base) = decompor_caminho_destino(caminho_destino)

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



# Desmonta o caminho de destino em vários elementos
# -----------------------------------------------------------------------------------
def decompor_caminho_destino(caminho_destino):
    # O caminho de destino para o arquivo E01 vem completo,
    # e tem que ser desmontado nos componentes:
    # caminho_destino     =
    #   "Memorando_1880-17_CF_PR-26/item01Arrecadacao01a/item01Arrecadacao01a_imagem/item01Arrecadacao01a.E01"
    # pasta_destino       =
    #   "Memorando_1880-17_CF_PR-26/item01Arrecadacao01a/item01Arrecadacao01a_imagem"
    # nome_arquivo_imagem = "item01Arrecadacao01a"
    partes = caminho_destino.split('/')
    # var_dump(partes)

    # Nome base do arquivo de imagem
    # Exemplo: item01Arrecadacao01a
    # Na pasta do tableau, existirão vários aquivos .E01 .E02 .Exx .log
    # Todos estes serão renomeado para este nome base
    nome_base = partes.pop()
    nome_base = nome_base.replace(".E01", "")

    # A pasta de destino é a pasta onde serão armazenados os arquivos .E01 .E02 etc
    pasta_destino = "/".join(partes)
    pasta_item = "/".join(partes[:-1])
    # Adiciona caminho relativo (uma vez que está sendo executado na pasta /sistema)
    pasta_destino = montar_caminho(get_parini('raiz_storage'), pasta_destino)
    pasta_item = montar_caminho(get_parini('raiz_storage'), pasta_item)

    return (pasta_destino, pasta_item, nome_base)


# Retorna verdadeiro se a tarefa já está sendo acompanhada
def tarefa_sendo_acompanhada(codigo_tarefa):
    return False

def monitorar_tarefa(codigo_tarefa):
    # Se tarefa já iniciou e está sendo acompanhada,
    # não há mais nada a fazer
    if tarefa_sendo_acompanhada(codigo_tarefa):
        # Não tem mais nada a fazer
        print_log("Tarefa", codigo_tarefa, "já está sendo monitorada")
        return True


    print_log("Inicio de monitaramento da tarefa", codigo_tarefa)

    # Recupera dados da tarefa do cache,
    # para evitar sobrecarregar o servidor com requisições
    tarefa = obter_tarefa_cache(codigo_tarefa)

    # Pasta para a tarefa
    (pasta_tableau, pasta_material) = obter_caminho_pasta_tableau(tarefa)
    print_log("Pasta de tableau da tarefa: ", pasta_tableau)

    # Se pasta não existe, tem algo erro aqui
    if not os.path.exists(pasta_tableau):
        # Isto aqui não deveria acontecer nunca...foi feita exclusão manual?
        erro = texto("Pasta do tableau não existe")
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

        if int(tarefa["codigo_situacao_tarefa"]) != GTableauExecutando:
            # Registra comando de execução do IPED
            sapisrv_troca_situacao_tarefa_loop(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=GTableauExecutando,
                texto_status="Pasta do tableau contém dados"
            )

        # Inicia processo para acompanhamento em background
        print_log("Tarefa: ", codigo_tarefa, "Pasta do tableau tem conteúdo. Iniciando acompanhamento")

        # Inicia subprocesso para acompanhamento do Tableau
        # ------------------------------------------------
        nome_arquivo_log = obter_nome_arquivo_log()
        dados_pai_para_filho = obter_dados_para_processo_filho()
        label_processo = "acompanhar:" + str(codigo_tarefa)
        item = tarefa["item"]
        caminho_destino = tarefa["caminho_destino"]

        (pasta_destino, pasta_item, nome_base)=decompor_caminho_destino(caminho_destino)

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
                  dados_pai_para_filho
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
        dados_pai_para_filho):

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

    # Fica em loop infinito.
    # Será encerrado quando não tiver mais nada a fazer,
    # ou então pelo pai (com terminate)
    tam_pasta_tableau = 0
    registrado_subpasta = False
    while True:

        # Se pasta do Tableau não existe, não tem o que acompanhar
        # Isto não deveria acontecer
        if not os.path.exists(pasta_tableau):
            print_log("Pasta para tableau não existe:", pasta_tableau)
            print_log("Abandonando acompanhamento desta tarefa")
            return

        # Verifica quantas subpastas existem no tableau
        # Não pode ter mais do que uma pasta, pois isto pode indicar
        # que o usuário está duplicando mais do que uma material para a
        # mesma pasta raiz do tableau...pode ter se enganado de material.
        # -------------------------------------------------------------------------------
        qtd_pastas = 0
        for dirpath, dirnames, filenames in os.walk(pasta_tableau):
            for sub in dirnames:
                # Despreza pasta que foi classificada com erro
                if "ERRO" in sub:
                    print_log("Desprezada subpasta com indicativo de erro", sub)
                    continue

                qtd_pastas += 1

                # Subpasta a ser processada
                print_log("Verificada presença de subpasta", sub)
                subpasta = montar_caminho(dirpath, sub)

        # Se não tem nenhuma subpasta,
        # encerra o acompanhamento
        if qtd_pastas==0:
            # Pode ser que só tivesse uma pasta de erro
            print_log("Nenhuma subpasta disponível para processamento. Finalizando subprocesso")
            return

        # Se tiver mais do que uma pasta, tem algo errado
        # Será necessária a intervenção manual do perito
        if qtd_pastas > 1:
            texto_status = \
                texto("Existe mais de uma subpasta.",
                      "É possível que tenha ocorrido algum equivoco, ",
                      "e existam dois processos de duplicação em andamento",
                      "de materiais distintos para a mesma pasta")
            sapisrv_abortar_tarefa(codigo_tarefa, texto_status)
            return

        # Registra no log a subpasta que será processada
        if not registrado_subpasta:
            print_log("Processando subpasta:", subpasta)
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status=texto("Processando subpasta", subpasta)
            )
            registrado_subpasta = True

        # Verifica se já tem o primeiro arquivo
        # Por convenção (fixado no tableau), grava será
        # image.E01.partial (se ainda não terminou o primeiro arquivo)
        # image.E01 (se já terminou o primeiro arquivo)
        # Se pasta já foi renomeada, então será algo como
        # item01Arrecadacao01.E01
        nome_possiveis=list()
        for prefixo in (Gtableau_imagem, nome_base):
            for sufixo in (".E01", ".E01.partial"):
                nome_arquivo=prefixo + sufixo
                nome_possiveis.append(nome_arquivo)

        encontrado_primeiro = False
        for nome_arquivo in nome_possiveis:
            caminho_primeiro_arquivo = montar_caminho(subpasta, nome_arquivo)
            if os.path.isfile(caminho_primeiro_arquivo):
                print_log("Encontrado arquivo", caminho_primeiro_arquivo)
                encontrado_primeiro = True
                # Ok, achou o arquivo
                break
            else:
                print_log("Não foi encontrado arquivo", caminho_primeiro_arquivo)

        if not encontrado_primeiro:
            texto_status = texto("Não foi encontrado arquivo indicativo ",
                                 "de início de cópia")
            sapisrv_abortar_tarefa(codigo_tarefa, texto_status)
            return

        # Verifica se já existe arquivo de log
        print_log("Verificando se já existe arquivo de log")
        encontrado_log = False
        for prefixo in (Gtableau_imagem, nome_base):
            arquivo_log = prefixo + ".log"
            caminho_arquivo_log = montar_caminho(subpasta, arquivo_log)
            if os.path.isfile(caminho_arquivo_log):
                encontrado_log = True
                break
            else:
                print_log("Não encontrado arquivo", arquivo_log)

        if encontrado_log:
            print_log("Encontrado arquivo de log:", caminho_arquivo_log)
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status=texto("Detectado existência de arquivo de log, "
                                   "indicando que tableau finalizou")
            )
            print_log("Interrompe loop de acompanhamento. Será analisado resultado")
            break
        else:
            print_log("Ainda não existe arquivo de log")

        # Calcula o tamanho da pasta do tableau e atualiza
        carac = obter_caracteristicas_pasta_ok(subpasta)
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
        # ----------------------------------------------------


    # Faz upload do arquivo de log do tableau
    # -------------------------------------------------------------------------------
    conteudo_log = ""
    # Upload do resultado do IPED
    with open(caminho_arquivo_log, "r") as fentrada:
        for linha in fentrada:
            conteudo_log += linha

    sapisrv_armazenar_texto_tarefa(codigo_tarefa, 'Log do tableau', conteudo_log)

    # Processa log do tableau, extraindo dados da tarefa para utilização no laudo
    # -------------------------------------------------------------------------------
    (sucesso, erro, dados_relevantes) = parse_arquivo_log_tableau(caminho_arquivo_log, item)

    if sucesso:
        print_log("Tudo certo no log")
    else:
        print_log("Detectado erro no parse do log: ", erro)

    # var_dump(sucesso)
    # var_dump(erro)
    # var_dump(dados_relevantes)
    # die('ponto310')

    # Se tableau não finalizou com sucesso, renomeia a pasta com erro e aborta a tarefa
    # -------------------------------------------------------------------------------
    if not sucesso:

        # Renomeia a pasta que está com problema,
        # para não ser mais reprocessada
        # Adicionar o sufixo "_ERRO"
        try:
            subpasta_renomeada = subpasta + "_ERRO"
            os.rename(subpasta, subpasta_renomeada)
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status=texto("Pasta de com erro foi renomeada para ", subpasta_renomeada)
            )
        except Exception as e:
            # Adiciona erro
            erro_adicional = texto("E também não foi possível renomear pasta com erro", subpasta, ":", e)
            erro = texto(erro, erro_adicional)
            return

        # Aborta tarefa
        sapisrv_abortar_tarefa(codigo_tarefa, erro)
        return

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
        for nome_arquivo in os.listdir(subpasta):

            nome_arquivo=montar_caminho(subpasta, nome_arquivo)

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
    # De:   tableau\Ronaldo_14940\proto_00943_2017\mat_1023_17_parte_2\2071005050_09_01_05
    # para:
    #
    # -------------------------------------------------------------------------------
    try:

        # Se pasta de destino já existe, move para lixeira
        # Isto pode acontecer se a tarefa foi reiniciada
        if os.path.exists(pasta_destino):
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status="Pasta de destino já existe. Movendo para lixeira"
            )
            # Move pasta de destino para lixeira
            mover_lixeira(pasta_destino)

        # Se não existe pasta pai, cria
        if not os.path.exists(pasta_item):
            os.makedirs(pasta_item)

        # Move pasta temporária para definitiva
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="Movendo pasta temporária para definitiva"
        )
        mover_pasta_storage(subpasta, pasta_destino)

        # Adiciona no arquivo sapi.info a pasta de origem
        sapi_tableau=dict()
        sapi_tableau['pasta_origem']=subpasta
        sapi_tableau['base_nome_original']=Gtableau_imagem
        sapi_tableau['base_nome_novo']=nome_base
        sapi_info_set(pasta_destino, 'sapi_tableau', sapi_tableau)
        print_log("Registrado situação em sapi.info")

        # Movimentação concluída
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="Pasta temporária movida para pasta definitiva"
        )

    except Exception as e:
        # Isto não deveria acontecer nunca
        erro = "Não foi possível mover para pasta definitiva: " + str(e)
        sapisrv_abortar_tarefa(codigo_tarefa, erro)
        return


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


# Faz parse no arquivo de log do Tableau e extrai informações relevantes para laudo
# Recebe o arquivo de log, e o item correspondente
def parse_arquivo_log_tableau(caminho_arquivo_log, item):
    try:
        return _parse_arquivo_log_tableau(caminho_arquivo_log, item)

    except Exception as e:
        erro = "Parse de log do Tableau falhou: " + str(e)
        return (False, erro, {})


def _parse_arquivo_log_tableau(caminho_arquivo_log, item):
    # Lista de avisos
    avisos = list()

    # Exemplo de log do tableau
    '''
    -----------------------------Start of TD3 Log Entry-----------------------------

    Task: Disk Image
    Status: Ok
    Created: Thu Sep 21 14:31:53 2017
    Started: Thu Sep 21 14:31:53 2017
    Closed: Thu Sep 21 14:42:49 2017
    Elapsed: 11 min
    User: <<not entered>>
    Case ID: <<not entered>>
    Case Notes: <<not entered>>

    Imager App: TD3
    Imager Ver: 2.0.0
    TD3 S/N: 000ecc11d370f2

    ------------------------------Source Disk-------------------------------

    Interface: USB
    Model: Kingston DataTraveler 108
    Firmware revision: PMAP
    USB Serial number: 0060E049DF71EBB100005893
    Capacity in bytes: 3,926,949,888 (3.9 GB)
    Block Size: 512 bytes
    Block Count: 7,669,824

    ----------------------------Destination CIFS----------------------------

    Share Name: //10.41.87.235/tableau

    --------------------------Disk Imaging Results--------------------------

    Output file format: E01 - EnCase format
    Chunk size in bytes: 2,147,483,648 (2.1 GB)
    Chunks written: 2
    Filename of first chunk: 1023_17_parte_1/2017-09-21_14-31-52/temporario.E01
    Total errors: 3
    Acquisition MD5:   cfdd6b92b8599309bbc8901d05ec2927
    Acquisition SHA-1: bb6bc7a155d22e748148b7f6100d50edabdb324c

    -----------------------------List of Errors-----------------------------

    Error # 1: Read error (source), byte offset=2123809280, byte length=512
    Error # 2: Read error (source), byte offset=2123810304, byte length=512
    Error # 3: Read error (source), byte offset=2123811328, byte length=512

    ---------------------Readback Verification Results----------------------

    Verification MD5:   cfdd6b92b8599309bbc8901d05ec2927
    Verification SHA-1: bb6bc7a155d22e748148b7f6100d50edabdb324c
    Status: Verified

    ------------------------------End of TD3 Log Entry------------------------------
    '''

    # Definição de identificadores de blocos
    blocos = dict()
    blocos["start"] = "-----Start of TD3"
    blocos["source"] = "----Source"
    blocos["destination"] = "---Destination"
    blocos["result"] = "---Disk Imaging Results"
    blocos["erros"] = "----List of Errors"
    blocos["verification"] = "---Readback Verification Results"
    blocos["fim"] = "----End of TD3"

    # Definição de tags de campos
    tags = dict()
    tags["erro_geral"] = "<<< CAUTION: "
    tags["task"] = "Task: "
    tags["status"] = "Status: "
    tags["created"] = "Created: "
    tags["started"] = "Started: "
    tags["closed"] = "Closed: "
    tags["elapsed"] = "Elapsed: "
    tags["user"] = "User: "
    tags["case"] = "Case ID:"
    tags["notes"] = "Case Notes:"
    tags["imager_app"] = "Imager App:"
    tags["imager_ver"] = "Imager Ver:"
    tags["td3_sn"] = "TD3 S/N:"
    tags["interface"] = "Interface: "
    tags["modelo"] = "Model: "
    tags["firmware_revision"] = "Firmware revision:"
    tags["0_usb_serial_number"] = "USB Serial number:"
    tags["1_serial_number"] = "Serial number:"
    tags["capacity"] = "Capacity in bytes:"
    tags["block_size"] = "Block Size:"
    tags["block_count"] = "Block Count:"
    tags["share_name"] = "Share Name:"
    tags["output_file_format"] = "Output file format:"
    tags["chunk_bytes"] = "Chunk size in bytes:"
    tags["chunks_written"] = "Chunks written:"
    tags["first_chunk"] = "Filename of first chunk:"
    tags["total_erros"] = "Total errors:"
    tags["aquisition_md5"] = "Acquisition MD5:"
    tags["aquisition_sha1"] = "Acquisition SHA-1:"
    #tags["verification_md5"] = "Verification MD5: "
    #tags["verification_sha1"] = "Verification SHA-1:"

    # Processa o arquivo de log
    with open(caminho_arquivo_log, "r") as fentrada:

        id_bloco = None
        valores = dict()
        for linha in fentrada:

            # Sanitiza
            # Troca tabulação por espaço
            # linha=linha.replace('\t',' ')

            processado = True

            # Verifica se é uma linha de início de bloco
            for b in blocos:
                if blocos[b] in linha:
                    id_bloco = b
                    break

            # Verifica se é linha de tag conhecido
            for t in sorted(tags):
                if tags[t] in linha:
                    id_tag = t
                    # Separa valor
                    # Task: Disk Image
                    partes = linha.split(':')
                    v = partes[1].strip()
                    # Armazena valor
                    chave = id_bloco + ":" + id_tag
                    valores[chave] = v
                    #
                    break

            # Ok, prossegue para a proxima linha
            continue

    # var_dump(valores)
    # die('ponto756')

    # -----------------------------------------------------------------------------
    # O código acima irá produzir um dicionário sendo:
    # Chave: concatenação do bloco com o tag identificador do campo (ex: start:elapsed)
    # Valor: O que vem depois do tag
    # -----------------------------------------------------------------------------
    # Exemplo:
    '''
     valores={
     'start:erro_geral': 'THE OPERATION RECORDED IN THIS LOG DID NOT COMPLETE NORMALLY >>>'
     'start:case': '<<not entered>>',
     'start:closed': 'Thu Sep 21 14',
     'start:created': 'Thu Sep 21 14',
     'start:elapsed': '11 min',
     'start:imager_app': 'TD3',
     'start:imager_ver': '2.0.0',
     'start:notes': '<<not entered>>',
     'start:started': 'Thu Sep 21 14',
     'start:status': 'Ok',
     'start:task': 'Disk Image',
     'start:td3_sn': '000ecc11d370f2',
     'start:user': '<<not entered>>',
     'source:block_count': '7,669,824',
     'source:block_size': '512 bytes',
     'source:capacity': '3,926,949,888 (3.9 GB)',
     'source:firmware_revision': 'PMAP',
     'source:interface': 'USB',
     'source:modelo': 'Kingston DataTraveler 108',
     'source:0_usb_serial_number': '0060E049DF71EBB100005893',
     'source:1_serial_number': 'NA8NMGTN',
     'destination:share_name': '//10.41.87.235/tableau',
     'result:aquisition_md5': 'cfdd6b92b8599309bbc8901d05ec2927',
     'result:aquisition_sha1': 'bb6bc7a155d22e748148b7f6100d50edabdb324c',
     'result:chunk_bytes': '2,147,483,648 (2.1 GB)',
     'result:chunks_written': '2',
     'result:first_chunk': '1023_17_parte_1/2017-09-21_14-31-52/temporario.E01',
     'result:output_file_format': 'E01 - EnCase format',
     'result:total_erros': '0'
     }
    '''

    # Não exigem mais verificação
    # Isto será feito no servidor
    #'verification:status': 'Verified',
    #'verification:verification_md5': 'cfdd6b92b8599309bbc8901d05ec2927',
    #'verification:verification_sha1': 'bb6bc7a155d22e748148b7f6100d50edabdb324c'

    # Duplicação não foi finalizada
    erro_geral = valores.get('start:erro_geral', None)
    if erro_geral is not None:
        erro = texto("Erro:", erro_geral,
                     " Consulte o log do tableau que foi carregado para o SAPI",
                     " para mais detalhes")
        return (False, erro, {})

    # Verificação não deveria estar ligada
    # Se estiver ligada, acusa um erro, para evitar que a lentidão afete outros
    # procedimentos
    # Verifica se o resultado é sucesso
    # Se não for sucesso, não tem por que prosseguir,
    # pois operação terá que ser refeita
    resultado = valores.get('verification:status', None)
    # No início, exigia verificação. Agora, não pode ter verificação
    # if resultado is None:
    #     erro = texto("Não foi possível identificar resultado final da imagem",
    #                  "(não encontrado Bloco Readback Verification Results ",
    #                  "com campo Status: Verified). ",
    #                  "Confirme se opção de verificação está ativa.")
    #     return (False, erro, {})
    if resultado is not None:
        erro = texto("A verificação do Tableau está ligada.",
                     " Isto dobra o tempo de imagem.",
                     " Desligue a verificação"
                     );
        return (False, erro, {})


    # -----------------------------------------------------------------------------
    # Duplicação efetuada com SUCESSO
    # -----------------------------------------------------------------------------

    # Dicionário para armazenamento de dados do componente que foi duplicado
    dlaudo = dict()
    dcomp = dict()

    # -----------------------------------------------------------------------------
    # Versão do tableau
    # -----------------------------------------------------------------------------
    # start:imager_ver': '2.0.0'
    versao = valores.get('start:imager_ver', None)
    if versao is None:
        erro = texto("Não foi possível identificar a versão do Tableau.")
        return (False, erro, {})

    if versao != '2.0.0':
        erro = texto("Versão do Tableau utilizado: ",
                     versao,
                     " é diferente da versão esperada (2.0.0)")
        return (False, erro, {})

    tableau_versao = valores.get('start:imager_app', "?") + " " + versao
    dlaudo["sapiSoftwareVersao"] = "Tableau " + tableau_versao

    # Separa outros elementos relevantes para utilização em laudo
    # A chave é o nome no tableau
    # O texto é o nome no SAPI
    relevantes = {
        # Elapsed: 11 min
        'start:elapsed': 'sapiTempoExecucaoSegundos',

        # TD3 S/N: 000ecc11d370f2
        'start:td3_sn': 'sapiTableauSN',

        # Share Name: //10.41.87.235/tableau
        'destination:share_name': 'sapiStorageDestino',

        # Model: Seagate Expansion
        'source:modelo': 'sapiModelo',

        # Tem duas informações serial: da USB e do dispositivo
        # Aparentemente, todos os dispositivos tem uma identificação serial USB
        # Contudo, nem todos também disponibilizam a sua identificação serial
        # do dispositivo interno
        # Por exemplo: Um hd externo terial o serial da USB e também o serial do próprio HD
        # que está dentro do case USB.

        # USB Serial number: 0060E049DF71EBB100005893
        'source:0_usb_serial_number': 'sapiSerialUSB',

        # Serial number: NA8NMGTN
        'source:1_serial_number': 'sapiSerialDispositivo',

        # Capacity in bytes: 3,926,949,888 (3.9 GB)
        'source:capacity': 'sapiTamanhoBytes',

        # Output file format: E01 - EnCase format
        'result:output_file_format': 'sapiFormatoArquivo',

        # Filename of first chunk: 1023_17_parte_1/2017-09-21_14-31-52/temporario.E01
        'result:first_chunk': 'sapiCaminhoImagemTemporario',

        # Total errors: 0
        'result:total_erros': 'sapiErrosLeituraQuantidade'
    }

    for r in relevantes:
        if (r in valores):
            chave_sapi = relevantes[r]
            dcomp[chave_sapi] = valores[r]

    #
    # var_dump(dcomp)


    # ------------------------------------------------------------------------------
    # Ajuste no tamanho da mídia
    # ------------------------------------------------------------------------------
    tamanho = dcomp.get('sapiTamanhoBytes', None)
    if tamanho is None:
        erro = texto("Não foi possível identificar o tamanho da mídia de origem (source:capacity)")
        return (False, erro, {})

    # 3,926,949,888(3.9 GB)
    partes = tamanho.split("(")
    t = partes[0].strip()
    t = t.replace(",", "")
    try:
        tamanho = int(t)
    except:
        erro = "Não foi possível converter tamanho da mídia para inteiro:" + t
        return (False, erro, {})

    dcomp['sapiTipoComponente'] = Gsapi_tipo_componente
    dcomp['sapiTamanhoBytes'] = tamanho
    dcomp['sapiTamanhoBytesHumano'] = converte_bytes_humano(tamanho)
    dcomp['sapiTamanhoBytesHumanoMil'] = converte_bytes_humano(tamanho,
                                                            utilizar_base_mil=True)

    # ------------------------------------------------------------------------------
    # Ajuste no tempo
    # ------------------------------------------------------------------------------
    tempo = dcomp.get('sapiTempoExecucaoSegundos', None)
    if tempo is None:
        erro = "Não foi possível identificar o tempo de execução da duplicação (start:elapsed)"
        return (False, erro, {})

    # Elapsed: 1 hour 28 min 15 sec
    tempo_orginal = tempo
    tempo = tempo.replace(' ', '')
    tempo = tempo.replace('day', ':d ')
    tempo = tempo.replace('hour', ':h ')
    tempo = tempo.replace('min', ':m ')
    tempo = tempo.replace('sec', ':s ')
    tempo = tempo.strip()
    partes_tempo = tempo.split(' ')

    tempo_segundos = 0
    erro = None
    for p in partes_tempo:
        # var_dump(p)
        # die('ponto983')

        x = p.split(':')
        if len(x) < 2:
            erro = "Formato de unidade de medida inesperado (" + p + ")"
            break
        valor = int(x[0])
        unidade = x[1]
        if unidade == 'd':
            valor *= 24 * 3600
        elif unidade == 'h':
            valor = 3600 * valor
        elif unidade == 'm':
            valor = 60 * valor
        elif unidade == 's':
            valor = valor
        else:
            erro = "Unidade de medida (" + unidade + ") inesperada"

        tempo_segundos = tempo_segundos + valor
        # var_dump(tempo_segundos)

    if erro is not None:
        erro = "Fomato de elapsed (" + tempo_orginal + ") inesperado : " + erro
        return (False, erro, {})

    # Tudo certo
    dcomp['sapiTempoExecucaoSegundos'] = tempo_segundos
    dcomp['sapiTempoExecucaoHumano'] = converte_segundos_humano(tempo_segundos)
    # die('ponto1029')


    # Todo: Detectar o tipo de dispositivo de origem (HD normal, HD externo: USB com tamanho grande, pendrive...Indeterminado)

    # ------------------------------------------------------------------------------
    # Calculo do percentual de erro
    # ------------------------------------------------------------------------------
    qtd_erros_reportados = int(dcomp['sapiErrosLeituraQuantidade'])
    if qtd_erros_reportados == 0:
        # Nenhum erro reportado pelo Tableau
        dcomp['sapiErrosLeituraPercentualHumano'] = "Nenhum erro de leitura"
    else:
        # Le arquivo integralmente, procurando por linhas que indicam setores defeituosos
        # Exemplo de formato de linha de erro
        # Error  # 1: Read error (source), byte offset=2123809280, byte length=512
        # Processa o arquivo de log
        qtd_linhas_erro = 0
        total_bytes_erro = 0
        with open(caminho_arquivo_log, "r") as fentrada:

            for linha in fentrada:

                linha = linha.strip()

                # Trata apenas linhas de erro de origem
                if "Read error (source)" not in linha \
                        or "byte length=" not in linha:
                    continue

                # Separa tamanho do erro
                # byte length=512
                partes = linha.split("byte length=")
                if len(partes) != 2:
                    erro = "Linha de erro em formato desconhecido: " + linha
                    return (False, erro, {})

                # Soma quantidade de bytes com erro
                bytes_erro = int(partes[1])
                total_bytes_erro += bytes_erro

                # var_dump(bytes_erro)
                # var_dump(total_bytes_erro)

                # Contador de linhas de erro
                qtd_linhas_erro += 1

                # Ok, prossegue para a proxima linha
                continue

        # Verifica se a quantidade de erros reportados
        # bate com o total de linhas encontradas no log
        if qtd_linhas_erro != qtd_erros_reportados:
            erro = "Quantidade de linhas de erro (" + \
                   str(qtd_linhas_erro) \
                   + ") diferente do esperado (" \
                   + str(qtd_erros_reportados) \
                   + ")"
            return (False, erro, {})

        # Valida e armazena quantidade total de bytes com erro de leitura
        if total_bytes_erro == 0:
            erro = "Situação inconsistente: total de bytes com erro=0, mas foi reportando " \
                   + str(qtd_erros_reportados) \
                   + " erros"
            return (False, erro, {})
        dcomp['sapiErrosLeituraTotalBytes'] = total_bytes_erro

        # Calcula o percentual de erro de leitura
        tamanho_bytes = int(dcomp['sapiTamanhoBytes'])
        # Para simular % de erro
        # total_bytes_erro = tamanho_bytes/5
        percentual_erro = (total_bytes_erro / tamanho_bytes) * 100
        dcomp['sapiErrosLeituraPercentual'] = percentual_erro
        if percentual_erro < 0.01:
            dcomp['sapiErrosLeituraPercentualHumano'] = "<0.01%"
        else:
            formatado = '{0:.2f}%'.format(percentual_erro)
            formatado = formatado.replace('.', ',')
            dcomp['sapiErrosLeituraPercentualHumano'] = formatado

        # Se o limite de erro ultrapassar um certo limite gera um aviso
        if percentual_erro > GlimitePercentualErroLeitura:
            avisos.append("Total de erros (" + dcomp['sapiErrosLeituraPercentualHumano']
                          + ") excede limite (" + str(GlimitePercentualErroLeitura) + "%)")
            texto_resultado_duplicao = ''

        # Resultado resumido da duplicação
        texto_resultado_duplicacao = ''
        if total_bytes_erro==0:
            texto_resultado_duplicacao = 'Dispositivo duplicado com sucesso'
        else:
            texto_resultado_duplicacao = 'Dispositivo duplicado, porém ocorreram erros de leitura.'
        dcomp['sapiResultadoDuplicacao'] = texto_resultado_duplicacao

    # ------------------------------------------------------------------------------
    # Tratamento para hashes
    # ------------------------------------------------------------------------------
    #Acquisition MD5:   cfdd6b92b8599309bbc8901d05ec2927
    #'result:aquisition_md5': 'cfdd6b92b8599309bbc8901d05ec2927',

    #Acquisition SHA-1: bb6bc7a155d22e748148b7f6100d50edabdb324c
    #'result:aquisition_sha1': 'bb6bc7a155d22e748148b7f6100d50edabdb324c',

    '''
    sapiHashes =>
        0 =>
        sapiHashAlgoritmo => sha256
        sapiHashDescricao => Hash do arquivo item03Arrecadacao03_extracao_iped/listaArquivos.csv
        sapiHashValor => 17a074d5608f35cdfc1f7cb5701f292da2597a1bc34533a7dc975fb8c01f878d
    '''

    # Armazena dados de hash
    hashes = list()

    # Processa os hashes
    ix_hash = 0
    for tipo_hash in ('md5', 'sha1'):
        h = dict()
        valor_hash = valores.get('result:aquisition_' + tipo_hash, None)
        if valor_hash is not None:
            h["sapiHashDescricao"] = "Hash " + tipo_hash.upper() + " de leitura do item " + item
            h["sapiHashValor"] = valor_hash
            h["sapiHashAlgoritmo"] = tipo_hash
        else:
            erro = "Não foi localizado o hash " + tipo_hash
            return (False, erro, {})

        # Armazena na lista de hashes
        hashes.append(h)
        ix_hash += 1

    # Finalizado com sucesso
    finalizado_sucesso = True

    # conclui dados para laudo
    dlaudo["comp1"] = dcomp
    dlaudo["sapiQuantidadeComponentes"] = 1  # Só tem um componente
    dlaudo["sapiHashes"] = hashes
    dlaudo["sapiTipoAquisicao"] = "imagem"

    # Monta dados relevantes para tarefa
    dados_relevantes = dict()
    dados_relevantes['laudo'] = dlaudo
    dados_relevantes['avisos'] = avisos

    return (True, None, dados_relevantes)

# Abortar execução do programa
# Esta rotina é invocada quando alguma situação exige que para a restauração da ordem
# o ambiente seja reiniciado
def finalizar_programa():
    print_log("Iniciando procedimento de encerramento do programa")
    print_log("Verificando se existem processos filhos a serem encerrados")
    for ix in sorted(Gpfilhos):
        if Gpfilhos[ix].is_alive():
            # Finaliza processo
            print_log("Finalizando processo ", ix, " [", Gpfilhos[ix].pid, "]")
            Gpfilhos[ix].terminate()

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
    pasta_sapi_info= "H:\\sapi_simulacao_storage\\Memorando_1880-17_CF_PR-26"

    #variavel="sub_pasta"
    #valor="c:\\tempr\\testexxx"
    #sapi_info_set(pasta_sapi_info, variavel, valor)

    #complexo=dict()
    #complexo["xxx"]="teste"
    #complexo["yyy"]="abc"
    #sapi_info_set(pasta_sapi_info, "complexo1", complexo)
    #die('ponto1403')

    #sapi_info=sapi_info_carregar(pasta_sapi_info)
    #var_dump(sapi_info)
    #die('ponto1407')

    #xxx=sapi_info_get(pasta_sapi_info, "sub_pasta")
    #var_dump(xxx)
    #die('ponto1397')


    # # Parse de um arquivo
    # ret=parse_arquivo_log("tableau_imagem.log", "item01Arrecadacao01")
    # var_dump(ret)
    # die('ponto2211')
    #
    #
    # # Para testar o processamento do log,
    # # processa um conjunto de arquivos de log do tableau usados para teste
    # pasta = "I:\\desenvolvimento\\sapi\\dados_para_testes\\tableau_log_total"
    # for f in os.listdir(pasta):
    #     print()
    #     print("======== Arquivo ", f," ======================")
    #     ret = parse_arquivo_log(os.path.join(pasta,f), "item01Arrecadacao01")
    #     var_dump(ret)
    #     print()

    # Executa rotina principal
    main()
