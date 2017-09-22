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

# Controle de tempos/pausas
GtempoEntreAtualizacoesStatus = 180
GdormirSemServico = 60
GmodoInstantaneo = False
# GmodoInstantaneo = True

#
Gconfiguracao = dict()
Gcaminho_pid="sapi_tableau_pid.txt"

# Pasta raiz da área temporária do tableau
# Todos os storages tem que ter a mesma estrutura, no caso /storage/tableau
Gpasta_raiz_tableau = "tableau"

# Cache de tarefas
Gcache_tarefa = dict()

# radical a partir do qual se formam os nomes dos arquivos (.E01, .E02, .log, etc)
Gtableau_imagem = "tableau-imagem"
Gponto_montagem = None

# Execução de tarefa
Gcodigo_tarefa_executando = None
Glabel_processo_executando = None

# Exclusão de tarefa
Gcodigo_tarefa_excluindo = None
Glabel_processo_excluindo = None

# Dados resultantes, para atualização da tarefa
Gdados_laudo = None
Gtamanho_destino_bytes = None


# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi.py, para evitar dependência
from sapilib_0_8_1 import *


# **********************************************************************
# PRODUCAO 
# **********************************************************************


# ======================================================================
# Funções auxiliares
# ======================================================================


# Faz um pausa por alguns segundos
# Dependendo de parâmetro, ignora a pausa
def dormir(tempo, rotulo=None):
    texto="Dormindo por " + str(tempo) + " segundos"
    if rotulo is not None:
        texto = rotulo + ": " + texto
    print_log(texto)
    if (not GmodoInstantaneo):
        time.sleep(tempo)
    else:
        print_log("Sem pausa...deve ser usado apenas para debug...modo instantâneo (ver GmodoInstantaneo)")


# Inicialização do agente
# Procedimento de inicialização
# Durante estes procedimento será determinado se comunicação a com servidor está ok,
# se este programa está habilitado para operar com o servidor, etc
# Existe um mecanismo para determinar automaticamente se será atualizado o servidor de desenvolvimento ou produção
# (ver documentação da função). Caso prefira definir manualmente, adicione ambiente='desenv' (ou 'prod')
# O nome do agente também é determinado por default através do hostname.
# ---------------------------------------------------------------------------------------------------------------------
def inicializar():
    global Gconfiguracao

    try:
        # Efetua inicialização
        # Neste ponto, se a versão do sapi_tableau estiver desatualizada será gerado uma exceção
        print_log("Efetuando inicialização")
        #sapisrv_inicializar(Gprograma, Gversao)  # Outros parâmetros: nome_agente='xxxx', ambiente='desenv'
        nome_arquivo_log = "log_sapi_tableau.txt"
        sapisrv_inicializar(Gprograma, Gversao, auto_atualizar=True, nome_arquivo_log=nome_arquivo_log)
        print_log('Inicializado com sucesso', Gprograma, ' - ', Gversao)

        # Obtendo arquivo de configuração
        print_log("Obtendo configuração")
        Gconfiguracao = sapisrv_obter_configuracao_cliente(Gprograma)
        print_log(Gconfiguracao)


    except SapiExceptionProgramaFoiAtualizado as e:
        print_log("Programa foi atualizado para nova versão em: ",e)
        print_log("Encerrando para ser reinicializado em versão correta")
        # Ao retornar False, o chamador entenderá que tem que atualizar o sapi_tableau, e encerrará a execução
        return False

    except SapiExceptionVersaoDesatualizada:
        print_log("sapi_tableau desatualizado. Não foi possível efetuar atualização automática. ")
        # Encerra sem sucesso
        return False

    except SapiExceptionProgramaDesautorizado:
        # Servidor sapi pode não estar respondendo (banco de dados inativo)
        # Logo, encerra e aguarda uma nova oportunidade
        print_log("AVISO: Não foi possível obter acesso (ver mensagens anteriores). Encerrando programa")
        # Ao retornar False, o chamador entenderá que tem que atualizar o sapi_tableau, e encerrará a execução
        return False

    except SapiExceptionFalhaComunicacao:
        # Se versão do sapi_tableau está desatualizada, irá tentar se auto atualizar
        print_log("Comunição com servidor falhou. Vamos encerrar e aguardar atualização, pois pode ser algum defeito no cliente")
        # Ao retornar False, o chamador entenderá que tem que atualizar o sapi_tableau, e encerrará a execução
        return False

    except BaseException as e:
        # Para outras exceçõs, irá ficar tentanto eternamente
        #print_log("[168]: Exceção sem tratamento específico. Avaliar se deve ser tratada: ", str(e))
        # Colocar isto aqui em uma função....
        # Talvez já jogando no log também...
        #exc_type, exc_value, exc_traceback = sys.exc_info()
        #traceback.print_exception(exc_type, exc_value, exc_traceback,
        #                          limit=2, file=sys.stdout)
        trc_string=traceback.format_exc()
        print_log("[168]: Exceção abaixo sem tratamento específico. Avaliar se deve ser tratada")
        print_log(trc_string)
        # Ao retornar False, o chamador entenderá que tem que atualizar o sapi_tableau, e encerrará a execução
        return False

    # Tudo certo
    return True


# Tenta obter uma tarefa com tipo contido em lista_tipo, para o storage (se for indicado)
def solicita_tarefas(lista_tipos, storage=None):
    for tipo in lista_tipos:

        # Registra em log
        log = "Solicitando tarefa com tipo=[" + tipo + "]"
        if storage is not None:
            log += " para storage =[" + storage + "]"
        else:
            log += " para qualquer storage"
        print_log(log)

        # Requisita tarefa
        (disponivel, tarefa) = sapisrv_obter_iniciar_tarefa(tipo, storage=storage)
        if disponivel:
            print_log("Tarefa disponível")
            return tarefa

    print_log("Nenhuma tarefa disponível")
    return None


# Tenta obter uma tarefa para exclusão
def solicita_tarefa_exclusao(lista_tipos, storage=None):
    for tipo in lista_tipos:

        # Registra em log
        log = "Solicitando tarefa para exclusão com tipo=[" + tipo + "]"
        if storage is not None:
            log += " para storage =[" + storage + "]"
        else:
            log += " para qualquer storage"
        print_log(log)

        # Requisita tarefa
        (disponivel, tarefa) = sapisrv_obter_excluir_tarefa(tipo, storage=storage)
        if disponivel:
            print_log("Tarefa para exclusão disponível")
            return tarefa

    print_log("Nenhuma tarefa na fila de exclusão")
    return None





# Atualiza arquivo de texto no servidor
# Fica em loop até conseguir
def armazenar_texto_tarefa(codigo_tarefa, titulo, conteudo):
    # Se a atualização falhar, fica tentando até conseguir
    # Se for problema transiente, vai resolver
    # Caso contrário, algum humano irá mais cedo ou mais tarde intervir
    while not sapisrv_armazenar_texto(tipo_objeto='tarefa',
                                      codigo_objeto=codigo_tarefa,
                                      titulo=titulo,
                                      conteudo=conteudo
                                      ):
        print_log("Falhou upload de texto para tarefa [", codigo_tarefa, "]. Tentando novamente")
        dormir(60)  # Tenta novamente em 1 minuto

    # Ok, conseguiu atualizar
    print_log("Efetuado upload de texto [", titulo, "] para tarefa [", codigo_tarefa, "]")


def armazenar_texto_log_iped(codigo_tarefa, caminho_log_iped):

    # Le arquivo de log do iped e faz upload
    if not os.path.exists(caminho_log_iped):
        print_log("Arquivo de log de IPED não existe, logo, upload não foi efetuado")
        return

    # Por enquanto, vamos ler tudo, mas talvez mais tarde seja melhor sintetizar, removendo informações sem valor
    # que só interesseriam para o desenvolvedor
    # Neste caso, talvez ter dois logs: O completo e o sintético.
    # Para arquivos maiores, terá que configurar no /etc/php.ini os parâmetros post_max_size e upload_max_filesize
    # para o tamanho necessário (atualmente no SETEC3 está bem baixo...8M)

    # Se precisar sintetizar no futuro, ver sapi_cellebrite => sintetizar_arquivo_xml
    # Fazer uma função específica
    conteudo = ""
    # with codecs.open(caminho_log_iped, "r", "utf-8") as fentrada:
    # Tem algo no arquivo de log que não é UTF8
    with open(caminho_log_iped, "r") as fentrada:
        for linha in fentrada:
            conteudo = conteudo + linha

    armazenar_texto_tarefa(codigo_tarefa, 'Arquivo de log do IPED', conteudo)


# Aborta tarefa.
# Retorna False sempre, para repassar para cima
def abortar(codigo_tarefa, texto_status):

    erro="Abortando [[tarefa:" + codigo_tarefa+ "]] em função de ERRO: " + texto_status

    # Registra em log
    print_log(erro)

    # Reportar erro para ficar registrado no servidor
    # Desta forma, é possível analisar os erros diretamente
    reportar_erro(erro)

    # Registra situação de devolução
    sapisrv_troca_situacao_tarefa_loop(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=GAbortou,
        texto_status=texto_status
    )

    # Ok
    print_log("Execução da tarefa abortada")

    return False


# Tratamento para erro no cliente
def reportar_erro(erro):
    try:
        # Registra no log (local)
        print_log("ERRO: ", erro)

        # Reportanto ao servidor, para registrar no log do servidor
        sapisrv_reportar_erro_cliente(erro)
        print_log("Erro reportado ao servidor")

    except Exception as e:
        # Se não conseguiu reportar ao servidor, deixa para lá
        # Afinal, já são dois erros seguidos (pode ser que tenha perdido a rede)
        print_log("Não foi possível reportar o erro ao servidor: ", str(e))



# ----------------------------------------------------------------------------------------------------------------------
# Remove da pasta de origem alguns arquivos que não serão processados pelo IPED
# Retorna:
#   Sucesso: True => Executado com sucesso,  False => Execução falhou
#   msg_erro: Se a execução falhou
#   lista_movidos: Lista de tuplas de pastas movidas (origem, destino)
# ----------------------------------------------------------------------------------------------------------------------
def mover_arquivos_sem_iped(caminho_origem, pasta_item):

    # ------------------------------------------------------------------------------------------------------------------
    # Verifica se pasta de origem contém algum arquivo que não deve ser indexado pelo IPED
    # ------------------------------------------------------------------------------------------------------------------
    lista_mover = list()
    lista_desconsiderar=['.ufdr', 'UFEDReader.exe']
    print_log("Verifica se na pasta de origem existem arquivos que não devem ser indexados pelo IPED")
    dirs = os.listdir(caminho_origem)
    for file in dirs:
        for desconsiderar in lista_desconsiderar:
            if desconsiderar in file:
                lista_mover.append(file)

    if len(lista_mover)==0:
        print_log("Não existe nenhum arquivo a ser movido antes de rodar o IPED")
        return (True, "", [])

    # ------------------------------------------------------------------------------------------------------------------
    # Move arquivos que não devem ser indexados para a pasta do item
    # ------------------------------------------------------------------------------------------------------------------
    lista_movidos=list()
    try:
        for arquivo in lista_mover:
            nome_antigo = montar_caminho(caminho_origem, arquivo)
            nome_novo = montar_caminho(pasta_item, arquivo)
            print_log("Arquivo", nome_antigo, "não será indexado pelo IPED")
            print_log("Renomeando arquivo", nome_antigo, "para", nome_novo)
            os.rename(nome_antigo, nome_novo)

        # Confere se renomeou
        if os.path.isfile(nome_antigo):
            raise Exception("Falhou: Arquivo", nome_antigo, "ainda existe")
        if not os.path.isfile(nome_novo):
            raise Exception("Falhou: Arquivo", nome_novo, "não existe")

        # Tudo certo, moveu
        # Inclui tupla na lista (nome_atual, nome_novo)
        lista_movidos.append((nome_antigo, nome_novo))

    except OSError as e:
        # Falhou o rename
        return (False, "[410] exceção durante rename: "+str(e), [])

    # Ok, tudo certo
    return (True, "", lista_movidos)


# ----------------------------------------------------------------------------------------------------------------------
# Restaura arquivo movidos (para não serem processados pelo iped)
# Retorna:
#   Sucesso: True => Executado com sucesso,
#            False => Execução falhou
#   msg_erro: Se a execução falhou
# ----------------------------------------------------------------------------------------------------------------------
def restaura_arquivos_movidos(lista_movidos):

    try:
        for (nome_antigo, nome_novo) in lista_movidos:
            print_log("Renomeando arquivo", nome_novo, "para", nome_antigo)
            os.rename(nome_novo, nome_antigo)

        # Confere se renomeou
        if os.path.isfile(nome_novo):
            raise Exception("Falhou: Arquivo", nome_novo, "ainda existe")
        if not os.path.isfile(nome_antigo):
            raise Exception("Falhou: Arquivo", nome_antigo, "não existe")

    except OSError as e:
        # Falhou o rename
        return (False, "[433] exceção durante rename: "+str(e), [])


# ----------------------------------------------------------------------------------------------------------------------
# Executa IPED
# Retorna (sucesso, msg_erro)
#   Sucesso: True => Executado com sucesso,  False => Execução falhou
#   msg_erro: Se a execução falhou
# ----------------------------------------------------------------------------------------------------------------------
def executa_iped(codigo_tarefa, comando, caminho_origem, caminho_destino, caminho_log_iped, caminho_tela_iped):

    # ------------------------------------------------------------------------------------------------------------------
    # Caminho de origem
    # ------------------------------------------------------------------------------------------------------------------
    print_log("Caminho de origem:", caminho_origem)
    if os.path.isfile(caminho_origem):
        print_log("Arquivo de origem encontrado no storage")
    elif os.path.exists(caminho_origem):
        print_log("Pasta de origem encontrada no storage")
    else:
        # Se não existe nem arquivo nem pasta, tem algo muito errado aqui
        erro = "Caminho de origem "+ caminho_origem + " não encontrado no storage"
        return (False, erro)

    # ------------------------------------------------------------------------------------------------------------------
    # Pasta de destino
    # ------------------------------------------------------------------------------------------------------------------
    # Se já existe conteúdo na pasta, verifica se foi concluído com sucesso
    if os.path.exists(caminho_destino):
        print_log("Pasta de destino já existe.")
        print_log("Verificando se dados na pasta de destino indicam que IPED foi executado com sucesso")
        if verificar_sucesso_iped(caminho_tela_iped):
            # Tudo certo, IPED finalizado
            # O processo que executou anteriormente deve ter falhado na atualização da situação
            # Desta forma, ajusta o situação da tarefa para IPED Finalizado e prossegue
            sapisrv_troca_situacao_tarefa_loop(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=GIpedFinalizado,
                texto_status="Execução anterior do IPED foi concluída com sucesso."
            )
            return (True, "")

    # Se pasta para armazenamento de resultado já existe, tem que limpar pasta antes
    # pois pode conter algum lixo de uma execução anterior
    if os.path.exists(caminho_destino):
        try:
            # Registra situação
            sapisrv_troca_situacao_tarefa_loop(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=GPastaDestinoCriada,
                texto_status="Execução anterior do IPED não foi concluída com sucesso. Reiniciando."
            )

            print_log("Excluindo pasta: "+caminho_destino)
            # Limpa pasta de destino
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status="Excluindo pasta de destino: "+ caminho_destino
            )
            shutil.rmtree(caminho_destino)
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status="Pasta de destino excluída"
            )
        except Exception as e:
            erro = "Não foi possível limpar pasta de destino da tarefa: " + str(e)
            # Aborta tarefa
            return (False, erro)

    # Não pode existir. Se existir, processo de exclusão acima falhou
    if os.path.exists(caminho_destino):
        erro = "Tentativa de excluir pasta falhou: Verifique se existe algo aberto na pasta, que esteja criando um lock em algum dos seus recursos"
        # Aborta tarefa
        return (False, erro)

    # Cria pasta de destino
    try:
        os.makedirs(caminho_destino)
    except Exception as e:
        erro = "Não foi possível criar pasta de destino: " + str(e)
        # Pode ter alguma condição temporária impedindo. Continuar tentando.
        return (False, erro)

    # Confere se deu certo
    if not os.path.exists(caminho_destino):
        erro = "Criação de pasta de destino falhou sem causar exceção!! Situação inesperada!"
        # Aborta tarefa
        return (False, erro)

    # Tudo certo, pasta criada
    sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa=codigo_tarefa, texto_status="Pasta de destino criada")

    # Executa comando do IPED
    deu_erro = False
    erro_exception=None
    try:
        # Registra comando de execução do IPED
        sapisrv_troca_situacao_tarefa_loop(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=GIpedExecutando,
            texto_status="Chamando IPED: " + comando
        )

        # Inicia subprocesso para acompanhamento do IPED
        # ------------------------------------------------
        nome_arquivo_log = obter_nome_arquivo_log()
        dados_pai_para_filho = obter_dados_para_processo_filho()
        label_processo = "acompanhar:" + str(codigo_tarefa)
        p_acompanhar = multiprocessing.Process(
            target=background_acompanhar_iped,
            args=(codigo_tarefa, caminho_tela_iped,
                  nome_arquivo_log, label_processo, dados_pai_para_filho
                  )
        )
        p_acompanhar.start()

        registra_processo_filho(label_processo, p_acompanhar)

        # Executa comando do IPED
        # Simula um erro de java não instalado
        # comando=comando.replace("java", "javaX")
        resultado = subprocess.check_output(comando, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)

    except subprocess.CalledProcessError as e:
        # Se der algum erro, não volta nada acima, mas tem como capturar pegando o output da exception
        erro_exception = str(e.output)
        deu_erro = True
    except Exception as e:
        # Alguma outra coisa aconteceu...
        erro_exception = str(e)
        deu_erro = True

    # Finaliza processo de acompanhamento do IPED
    print_log("Encerrando processo de acompanhamento de cópia")
    p_acompanhar.terminate()

    # Faz upload da tela de resultado do IPED (mensagens que seriam exibidas na tela)
    conteudo_tela=""
    # Upload do resultado do IPED
    with open(caminho_tela_iped, "r") as fentrada:
        for linha in fentrada:
            conteudo_tela = conteudo_tela + linha

    armazenar_texto_tarefa(codigo_tarefa, 'Resultado IPED', conteudo_tela)

    # Faz upload do log do IPED
    armazenar_texto_log_iped(codigo_tarefa, caminho_log_iped)

    if deu_erro:
        erro = "Chamada de IPED falhou. Para compreender, analise o arquivo de resultado."
        if erro_exception!="":
            erro = erro + ": " + erro_exception
        return (False, erro)

    # Se não deu erro (exit code), espera-se que o IPED tenha chegado até o final normalmente
    # Para confirmar isto, confere se existe o string abaixo
    if not verificar_sucesso_iped(caminho_tela_iped):
        # Algo estranho aconteceu, pois não retornou erro (via exit code),
        # mas também não retornou mensagem de sucesso na tela
        erro = "Não foi detectado indicativo de sucesso do IPED. Verifique arquivos de Resultado e Log."
        # Neste caso, vamos abortar definitivamente, para fazer um análise do que está acontecendo
        # pois isto não deveria acontecer jamais
        return (False, erro)

    # Tudo certo, IPED finalizado com sucesso
    sapisrv_troca_situacao_tarefa_loop(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=GIpedFinalizado,
        texto_status="IPED finalizado com sucesso")
    return (True, "")


# Acompanha a execução do Tableau e atualiza o status da tarefa
def background_acompanhar_tableau(
        codigo_tarefa,
        pasta_tableau,
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
    while True:

        # Se pasta do Tableau não existe, não tem o que acompanhar
        # Isto não deveria acontecer
        if not os.path.exists(pasta_tableau):
            print_log("Pasta para tableau não existe:", pasta_tableau)
            print_log("Abandonando acompanhamento desta tarefa")
            return

        # Verifica quantas pastas tem no pasta temporária do tableau
        # O normal é ter apenas uma subpasta, que o Tableau cria
        # ----
        # Não pode ter mais do que uma pasta, pois isto pode indicar
        # que o usuário iniciou mais de uma cópia no mesmo destino
        # Todo: Talvez permitir que tenha uma pasta que abortou e outra que está ok
        # Todo: Mas se for duas pela metadade, o usuário terá que excluir uma das portas
        qtd_pastas = 0
        for dirpath, dirnames, filenames in os.walk(pasta_tableau):
            qtd_pastas += 1
            subpasta=dirpath

        if qtd_pastas>2:
            texto_status="Existe mais de uma subpasta, indicando que houve mais de um processamento do Tableau para este item"
            abortar(codigo_tarefa, texto_status)
            return

        # Processa subpasta da imagem gerada
        print_log("Subpasta encontrada:", subpasta)


        # Verifica se já tem o primeiro arquivo
        # Por convenção, o arquivo de imagem do tableau deve ter nome tableau_imagem.E01
        primeiro_arquivo=Gtableau_imagem+".E01"
        caminho_primeiro_arquivo = montar_caminho(subpasta, primeiro_arquivo)
        if os.path.isfile(caminho_primeiro_arquivo):
            print_log("Encontrado arquivo:", primeiro_arquivo)
        else:
            texto_status="Não foi encontrado arquivo: "+primeiro_arquivo
            abortar(codigo_tarefa, texto_status)
            return


        # Verifica se já existe arquivo de log
        arquivo_log=Gtableau_imagem+".log"
        caminho_arquivo_log = montar_caminho(subpasta, arquivo_log)
        if os.path.isfile(caminho_arquivo_log):
            print_log("Encontrado arquivo de log:", caminho_arquivo_log)
            # Interrompe loop, pois agora irá somente analisar o resultado do log
            break

        # Calcula o tamanho da pasta do tableau e atualiza
        carac = obter_caracteristicas_pasta_ok(subpasta)
        if carac is not None:
            tam_pasta_tableau = carac.get("tamanho_total", None)
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status="Tamanho atual da pasta do tableau: " + converte_bytes_humano(tam_pasta_tableau)
            )
        else:
            print_log("Falhou na determinação do tamanho da pasta do tableau")

        # Pausa para evitar sobrecarga no servidor
        dormir(60, "pausa entre atualizações de status")

        # Fim do While - Loop eterno


    # Processa log do tableau, extraindo dados da tarefa para utilização no laudo
    (sucesso, dados_laudo)=parse_arquivo_log(caminho_arquivo_log)

    # Grava arquivo de log, para consulta do usuário

    # Atualiza situação da tarefa para sucesso





# Faz parse no arquivo de log do Tableau e extrai informações relevantes para laudo
# Recebe o arquivo de log, e o item correspondente

def parse_arquivo_log(caminho_arquivo_log, item):

    try:
        _parse_arquivo_log(caminho_arquivo_log, item)

    except Exception as e:
        ret = dict()
        ret["sucesso"] = False
        ret["erro"] = "Parse de log do Tableau falhou: " + str(e)
        ret["dados"] = dict()
        return ret


def _parse_arquivo_log(caminho_arquivo_log, item):

    # Estutura de dados de retorno
    ret = dict()
    ret["sucesso"]=False
    ret["erro"]=None
    ret["dados"]=dict()

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
    Total errors: 0
    Acquisition MD5:   cfdd6b92b8599309bbc8901d05ec2927
    Acquisition SHA-1: bb6bc7a155d22e748148b7f6100d50edabdb324c

    ---------------------Readback Verification Results----------------------

    Verification MD5:   cfdd6b92b8599309bbc8901d05ec2927
    Verification SHA-1: bb6bc7a155d22e748148b7f6100d50edabdb324c
    Status: Verified

    ------------------------------End of TD3 Log Entry------------------------------
    '''

    # Definição de identificadores de blocos
    blocos=dict()
    blocos["start"]="-----Start of TD3"
    blocos["source"]="----Source"
    blocos["destination"]="---Destination"
    blocos["result"]="---Disk Imaging Results"
    blocos["verification"]="---Readback Verification Results"

    # Definicção de tags de campos
    tags=dict()
    tags["task"]="Task: "
    tags["status"]="Status: "
    tags["created"]="Created: "
    tags["started"]="Started: "
    tags["closed"]="Closed: "
    tags["elapsed"]="Elapsed: "
    tags["user"]="User: "
    tags["case"]="Case ID:"
    tags["notes"]="Case Notes:"
    tags["imager_app"]="Imager App:"
    tags["imager_ver"]="Imager Ver:"
    tags["td3_sn"]="TD3 S/N:"
    tags["interface"]="Interface: "
    tags["modelo"]="Model: "
    tags["firmware_revision"]="Firmware revision:"
    tags["usb_serial_number"]="USB Serial number:"
    tags["capacity"]="Capacity in bytes:"
    tags["block_size"]="Block Size:"
    tags["block_count"]="Block Count:"
    tags["share_name"]="Share Name:"
    tags["output_file_format"]="Output file format:"
    tags["chunk_bytes"]="Chunk size in bytes:"
    tags["chunks_written"]="Chunks written:"
    tags["first_chunk"]="Filename of first chunk:"
    tags["total_erros"]="Total errors:"
    tags["aquisition_md5"]="Acquisition MD5:"
    tags["aquisition_sha1"]="Acquisition SHA-1:"
    tags["verification_md5"]="Verification MD5: "
    tags["verification_sha1"]="Verification SHA-1:"

    # Processa o arquivo de log
    with open(caminho_arquivo_log, "r") as fentrada:

        id_bloco = None
        valores = dict()
        for linha in fentrada:

            # Sanitiza
            # Troca tabulação por espaço
            #linha=linha.replace('\t',' ')

            processado = True

            # Verifica se é uma linha de início de bloco
            for b in blocos:
                if blocos[b] in linha:
                    id_bloco=b
                    break

            # Verifica se é linha de tag conhecido
            for t in tags:
                if tags[t] in linha:
                    id_tag=t
                    # Separa valor
                    # Task: Disk Image
                    partes=linha.split(':')
                    v=partes[1].strip()
                    # Armazena valor
                    chave=id_bloco+":"+id_tag
                    valores[chave]=v
                    #
                    break

            # Ok, prossegue para a proxima linha
            continue

    #var_dump(valores)
    #die('ponto756')

    # -----------------------------------------------------------------------------
    # O código acima irá produzir um dicionário sendo:
    # Chave: concatenação do bloco com o tag identificador do campo (ex: start:elapsed)
    # Valor: O que vem depois do tag
    # -----------------------------------------------------------------------------
    # Exemplo:
    '''
     valores={
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
     'source:usb_serial_number': '0060E049DF71EBB100005893',
     'destination:share_name': '//10.41.87.235/tableau',
     'result:aquisition_md5': 'cfdd6b92b8599309bbc8901d05ec2927',
     'result:aquisition_sha1': 'bb6bc7a155d22e748148b7f6100d50edabdb324c',
     'result:chunk_bytes': '2,147,483,648 (2.1 GB)',
     'result:chunks_written': '2',
     'result:first_chunk': '1023_17_parte_1/2017-09-21_14-31-52/temporario.E01',
     'result:output_file_format': 'E01 - EnCase format',
     'result:total_erros': '0',
     'verification:status': 'Verified',
     'verification:verification_md5': 'cfdd6b92b8599309bbc8901d05ec2927',
     'verification:verification_sha1': 'bb6bc7a155d22e748148b7f6100d50edabdb324c'
     }
    '''

    # Verifica se o resultado é sucesso
    # Se não for sucesso, não tem por que prosseguir,
    # pois operação terá que ser refeita
    resultado=valores.get('verification:status',None)
    if resultado is None:
        ret["erro"]= "Não foi possível identificar resultado final da imagem (não encontrado Bloco Readback Verification Results, com campo Status: Verified. Confirme se opção de verificação está ativa."
        ret["sucesso"]=False
        return ret

    # -----------------------------------------------------------------------------
    # Duplicação efetuada com SUCESSO
    # -----------------------------------------------------------------------------
    ret["sucesso"] = True

    # Dicionário para armazenamento de dados do componente que foi duplicado
    dlaudo = dict()
    dcomp = dict()

    # -----------------------------------------------------------------------------
    # Versão do tableau
    # -----------------------------------------------------------------------------
    # start:imager_ver': '2.0.0'
    versao=valores.get('start:imager_ver',None)
    if versao is None:
        ret["erro"]="Não foi possível identificar a versão do Tableau."
        ret["sucesso"]=False
        return ret

    if versao != '2.0.0':
        ret["erro"]="Versão do Tableau utilizado: "+versao+" é diferente da versão esperada (2.0.0)"
        ret["sucesso"]=False
        return ret

    tableau_versao=valores.get('start:imager_app',"?") + " " + versao
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

        # USB Serial number: NA8NMGTN
        'Serial number': 'sapiSerial',

        # Capacity in bytes: 3,926,949,888 (3.9 GB)
        'source:capacity': 'sapiTamanhoBytes',

        # Output file format: E01 - EnCase format
        'result:output_file_format': 'sapiFormatoArquivo',

        # Filename of first chunk: 1023_17_parte_1/2017-09-21_14-31-52/temporario.E01
        'result:first_chunk': 'sapiCaminhoImagemTemporario',

        # Total errors: 0
        'result:total_erros': 'sapiQuantidadeErros'

    }

    for r in relevantes:
        if (r in valores):
            chave_sapi=relevantes[r]
            dcomp[chave_sapi]=valores[r]


    #
    var_dump(dcomp)


    # ------------------------------------------------------------------------------
    # Ajuste no tamanho da mídia
    # ------------------------------------------------------------------------------
    tamanho=dcomp.get('sapiTamanhoBytes', None)
    if tamanho is None:
        ret["erro"]="Não foi possível identificar o tamanho da mídia de origem (source:capacity)"
        ret["sucesso"]=False
        return ret

    # 3,926,949,888(3.9 GB)
    partes=tamanho.split("(")
    t=partes[0].strip()
    t=t.replace(",","")
    try:
        tamanho=int(t)
    except:
        ret["erro"]="Não foi possível converter tamanho da mídia para inteiro:" + t
        ret["sucesso"]=False
        return ret

    dcomp['sapiTamanhoBytes']=tamanho

    # ------------------------------------------------------------------------------
    # Ajuste no tempo
    # ------------------------------------------------------------------------------
    tempo=dcomp.get('sapiTempoExecucaoSegundos', None)
    if tempo is None:
        ret["erro"]="Não foi possível identificar o tempo de execução da duplicação (start:elapsed)"
        ret["sucesso"]=False
        return ret
    
    # Elapsed: 1 hour 28 min 15 sec
    tempo_orginal=tempo
    tempo=tempo.replace(' ','')
    tempo=tempo.replace('day', ':d ')
    tempo=tempo.replace('hour', ':h ')
    tempo=tempo.replace('min', ':m ')
    tempo=tempo.replace('sec', ':s ')
    tempo=tempo.strip()
    partes_tempo=tempo.split(' ')

    tempo_segundos=0
    erro=None
    for p in partes_tempo:
        var_dump(p)
        #die('ponto983')

        x=p.split(':')
        if len(x)<2:
            erro="Formato de unidade de medida inesperado ("+p+")"
            break
        valor=int(x[0])
        unidade=x[1]
        if unidade=='d':
            valor=24*3600*valor
        elif unidade=='h':
            valor=3600*valor
        elif unidade=='m':
            valor=60*valor
        elif unidade=='s':
            valor=valor
        else:
            erro="Unidade de medida (" + unidade + ") inesperada"

        tempo_segundos = tempo_segundos + valor

    if erro is not None:
        ret["erro"] = "Fomato de elapsed ("+tempo_orginal+") inesperado : " + erro
        ret["sucesso"] = False
        return ret

    # Tudo certo
    dcomp['sapiTempoExecucaoSegundos']=tempo_segundos


    # TODO: Converte tempo para minutos
    # TODO: Imagem com erro Failure sumary
    # Todo: Calcular o tamanho dos erros (quando são erros de leitura) e o % do disco afetado
    # Todo: Detectar mensagens de cancelamento

    # Todo: Gerar registro no log se ficar mais de (5, 10, 20, 40, 80, vai dobrando) minutos sem nenhum progresso no tamanho da imagem


    # ------------------------------------------------------------------------------
    # Calculo da quantidade de erros
    # ------------------------------------------------------------------------------


    # ------------------------------------------------------------------------------
    # Tratamento para hashes
    # ------------------------------------------------------------------------------
    # Verification MD5:   cfdd6b92b8599309bbc8901d05ec2927
    # 'verification:verification_md5'

    # Verification SHA-1: bb6bc7a155d22e748148b7f6100d50edabdb324c
    # 'verification:verification_sha1'

    '''
    sapiHashes =>
        0 =>
        sapiHashAlgoritmo => sha256
        sapiHashDescricao => Hash do arquivo item03Arrecadacao03_extracao_iped/listaArquivos.csv
        sapiHashValor => 17a074d5608f35cdfc1f7cb5701f292da2597a1bc34533a7dc975fb8c01f878d
    '''

    # Armazena dados de hash
    h = dict()

    # Processa os hashes
    for tipo_hash in ('md5', 'sha1'):
        valor_hash=valores.get('verification:verification_'+tipo_hash,None)
        if valor_hash is not None:
            h["sapiHashDescricao"] = "Hash "+tipo_hash+" do conjunto de setores lidos do material " + item
            h["sapiHashValor"] = valor_hash
            h["sapiHashAlgoritmo"] = tipo_hash
        else:
            ret["erro"]="Não foi localizado o hash "+tipo_hash
            ret["sucesso"] = False
            return ret

    #
    lista_hash = [h]


    # Finalizado com sucesso
    finalizado_sucesso=True


    # conclui dados para laudo
    dlaudo["comp1"] = dcomp
    dlaudo["sapiQuantidadeComponentes"] = 1 #Só tem um componente
    dlaudo["sapiTipoAquisicao"] = "imagem"

    ret["sucesso"]=True
    ret["dados"]['laudo'] = dlaudo


    return ret


# Verifica se existe indicação que iped foi finalizado com sucesso
def verificar_sucesso_iped(caminho_tela_iped):

    # Será lido o arquivo de "tela" do IPED, ou seja, o arquivo que contém as mensagens
    print_log("Analisando arquivo de tela do IPED: [", caminho_tela_iped,"]")

    if not os.path.exists(caminho_tela_iped):
        print_log("Arquivo de resultado de IPED não encontrado")
        return False

    # Processa arquivo de tela
    with open(caminho_tela_iped, "r") as fentrada:
        for linha in fentrada:
            # Sucesso
            indicativo="IPED finalizado"
            if indicativo in linha:
                print_log("Indicativo de sucesso [", indicativo," ] encontrado.")
                return True
            # Erro
            indicativo = 'ERRO!!!'
            if indicativo in linha:
                print_log("Indicativo de erro [",indicativo,"] encontrado.")
                return False

    # Se não tem informação conclusiva, retorna falso
    print_log("Sem informação conclusiva na análise do arquivo de resultado do IPED")
    return False


def calcula_sha256_arquivo(caminho_arquivo, blocksize=2 ** 20):
    m = hashlib.sha256()
    with open(caminho_arquivo, "rb") as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            m.update(buf)
    return m.hexdigest()


def calcula_hash_iped(codigo_tarefa, caminho_destino):

    global Gdados_laudo

    sapisrv_atualizar_status_tarefa_informativo(
        codigo_tarefa=codigo_tarefa,
        texto_status="Calculando hash do resultado do IPED"
    )

    # Monta linha de comando
    nome_arquivo_calculo_hash = "Lista de Arquivos.csv"
    caminho_arquivo_calcular_hash = montar_caminho(caminho_destino, nome_arquivo_calculo_hash)

    try:
        algoritmo_hash = 'sha256'
        texto_status = "Calculando hash " + algoritmo_hash + " para " + caminho_arquivo_calcular_hash
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status=texto_status
        )
        valor_hash =calcula_sha256_arquivo(caminho_arquivo_calcular_hash)
    except Exception as e:
        erro = "Não foi possível calcular hash para " + nome_arquivo_calculo_hash + " => " + str(e)
        # Não deveria ocorrer este erro??? Abortar e analisar
        return (False, erro)

    # Extrai a subpasta de destino
    partes=caminho_destino.split("/")
    subpasta_destino=partes[len(partes)-1]
    if subpasta_destino=="":
        subpasta_destino = partes[len(partes) - 2]

    # Armazena dados de hash
    h = dict()
    h["sapiHashDescricao"] = "Hash do arquivo " + subpasta_destino + "/" + nome_arquivo_calculo_hash
    h["sapiHashValor"] = valor_hash
    h["sapiHashAlgoritmo"] = algoritmo_hash
    lista_hash = [h]

    Gdados_laudo['sapiHashes']=lista_hash

    print_log("Hash calculado para resultado do IPED: ", valor_hash, "(",algoritmo_hash,")")

    # Tudo certo, Hash calculado
    sapisrv_troca_situacao_tarefa_loop(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=GIpedHashCalculado,
        texto_status="Hash calculado com sucesso"
    )
    return (True, "")



# Calculo de tamanho da pasta de destino
def calcula_tamanho_total_pasta(caminho_destino):

    global Gtamanho_destino_bytes

    msg_erro=None
    try:
        carac_destino = obter_caracteristicas_pasta(caminho_destino)
        Gtamanho_destino_bytes = carac_destino["tamanho_total"]

        print_log("Tamanho total da pasta resultante do processamento do IPED: ", Gtamanho_destino_bytes)
        sucesso=True

    except OSError as e:
        msg_erro= "[1180] Falhou determinação de tamanho: " + str(e)
        sucesso=False
    except BaseException as e:
        msg_erro= "[1183] Falhou determinação de tamanho: " + str(e)
        sucesso=False

    return (sucesso, msg_erro)


# Recupera dados relevantes do log do IPED
def recupera_dados_laudo(codigo_tarefa, caminho_log_iped):

    global Gdados_laudo


    # Será lido o arquivo de log
    print_log("Recuperando dados para laudo do log do IPED: ", caminho_log_iped)
    sapisrv_atualizar_status_tarefa_informativo(
        codigo_tarefa=codigo_tarefa,
        texto_status="Recuperando dados para laudo do log do IPED"
    )

    if not os.path.exists(caminho_log_iped):
        erro="Arquivo de log do IPED não encontrado"
        return (False, erro)

    # Processa arquivo
    versao=None
    total_itens=None
    with open(caminho_log_iped, "r") as fentrada:
        for linha in fentrada:
            # Troca tabulação por espaço
            linha = linha.replace('\t', ' ')

            # Versão do IPED
            # 2017-01-31 17:12:11	[INFO]	Indexador e Processador de Evidências Digitais 3.11
            if "[INFO] Indexador e Processador" in linha:
                (inicio, numero_versao)=linha.split('Digitais')
                numero_versao=numero_versao.strip()
                if not numero_versao=="":
                    versao="IPED " + numero_versao

            # Quantidade de itens processados
            # 2017-01-31 17:21:19	[INFO]	Total processado: 153329 itens em 542 segundos (4084 MB)
            if "[INFO] Total processado:" in linha:
                match = re.search(r'processado: (\d+) itens', linha)
                if match:
                    total_itens=(match.group(1))

            # Todo: Como calcular a quantidade de itens com erro (que não foram processados...)


    if versao is None:
        erro="Não foi possível recuperar versão do IPED"
        return (False, erro)

    if total_itens is None:
        erro="Não foi possível recuperar quantidade total de itens processados"
        return (False, erro)

    # Armazena dados para laudo
    Gdados_laudo['sapiSoftwareVersao']=versao
    Gdados_laudo['sapiItensProcessados'] = total_itens

    # Todo: 'sapiItensProcessados':
    # Todo: 'sapiItensComErro':


    # Ok, finalizado com sucesso
    return (True, "")


# ------------------------------------------------------------------------------------------------------------------
# Conexão com storage
# ------------------------------------------------------------------------------------------------------------------

# Efetua conexão no ponto de montagem, dando tratamento em caso de problemas
def conectar_ponto_montagem_storage_ok(dados_storage):

    global Gponto_montagem

    # Se já montou, apenas retorna
    if Gponto_montagem is not None:
        return Gponto_montagem

    # Confirma que tem acesso ao storage escolhido
    nome_storage = dados_storage['maquina_netbios']
    print_log("Verificando conexão com storage", nome_storage)

    (sucesso, ponto_montagem, erro) = acesso_storage_windows(dados_storage, utilizar_ip=True, tipo_conexao='atualizacao')
    if not sucesso:
        erro = "Acesso ao storage " + nome_storage + " falhou. Verifique se servidor está acessível (rede) e disponível."
        # Talvez seja um problema de rede (trasiente)
        reportar_erro(erro)
        print_log("Problema insolúvel neste momento, mas possivelmente transiente")
        return False

    print_log("Storage", nome_storage, "acessível")

    Gponto_montagem=ponto_montagem

    return Gponto_montagem


# ------------------------------------------------------------------------------------------------------------------
# Exclusão de tarefa
# ------------------------------------------------------------------------------------------------------------------

# Executa uma tarefa de iped que esteja ao alcance do agente
# Retorna verdadeiro se executou uma tarefa e falso se não executou nada
def ciclo_excluir():

    # Se já tem tarefa sendo excluída
    # verifica a situação da tarefa
    if Gcodigo_tarefa_excluindo is not None:
        return tarefa_excluindo()
    else:
        return excluir_tarefa()

# Retorna verdadeiro se tarefa ainda está sendo excluída
def tarefa_excluindo():

    global Gcodigo_tarefa_excluindo

    print_log("Verificando se tarefa", Gcodigo_tarefa_excluindo, "ainda está sendo excluída")
    tarefa=recupera_tarefa_do_setec3(Gcodigo_tarefa_excluindo)

    excluindo=False
    excluindo_setec3 = False
    if tarefa is None:
        print_log("Não foi possível recuperar situação de tarefa do SETEC3. Presumindo que foi excluída com sucesso")
    else:
        codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
        if tarefa['excluida']=='t':
            print_log("Segundo SETEC3, exclusão da tarefa foi finalizada (tarefa foi excluída)")
            excluindo=False
            excluindo_setec3=False
        elif codigo_situacao_tarefa==GEmExclusao:
            print_log("Tarefa ainda está sendo excluída de acordo com SETEC3")
            excluindo=True
            excluindo_setec3=True
        else:
            print_log("Segundo SETEC3 tarefa não está mais sendo excluída. codigo_situacao_tarefa=",codigo_situacao_tarefa)

    # Verifica se o subprocesso de execução da tarefa ainda está rodando
    nome_processo="excluir:"+str(Gcodigo_tarefa_excluindo)
    processo=Gpfilhos.get(nome_processo, None)
    if processo is not None and processo.is_alive():
        # Ok, tarefa está sendo executada
        print_log("Subprocesso de exclusão da tarefa ainda está rodando")
        excluindo = True
    else:
        print_log("Subprocesso de exclusão da tarefa NÃO ESTÁ mais rodando")
        if excluindo_setec3:
            print_log("Como no setec3 ainda está em exclusão, isto provavelmente indica que o subprocesso de exclusão abortou")
            print_log("Desta forma, a tentativa de exclusão será abandonada. Isto gerará uma nova tentativa de exclusão")
            excluindo=False

    # Retorna se alguma condição acima indica que tarefa está excluindo
    if excluindo:
        print_log("Tarefa continua em exclusão")
        return True

    # Se não está mais excluindo
    print_log("Tarefa não está mais em exclusão")
    Gcodigo_tarefa_excluindo = None
    return False



# Retorna verdadeiro se uma tarefa foi excluída
def excluir_tarefa():

    global Gcodigo_tarefa_excluindo
    global Glabel_processo_excluindo

    print_log("Verificando se existe tarefa a ser excluída")

    # Solicita tarefa, dependendo da configuração de storage do agente
    outros_storages = True
    tarefa = None
    if Gconfiguracao["storage_unico"] != "":
        print_log("Este agente trabalha apenas com storage:", Gconfiguracao["storage_unico"])
        tarefa = solicita_tarefa_exclusao(Glista_ipeds_suportados, Gconfiguracao["storage_unico"])
        outros_storages = False
    elif Gconfiguracao["storage_preferencial"] != "":
        print_log("Este agente trabalha com storage preferencial:", Gconfiguracao["storage_preferencial"])
        tarefa = solicita_tarefa_exclusao(Glista_ipeds_suportados, Gconfiguracao["storage_preferencial"])
        outros_storages = True
    else:
        print_log("Este agente trabalha com QUALQUER storage")
        outros_storages = True

    # Se ainda não tem tarefa, e agente trabalha com outros storages, solicita para qualquer storage
    if tarefa is None and outros_storages:
        # Solicita tarefa para qualquer storage
        tarefa = solicita_tarefa_exclusao(Glista_ipeds_suportados)

    # Se não tem nenhuma tarefa para exdisponível, não tem o que fazer
    if tarefa is None:
        print_log("Nenhuma tarefa para exclusão na fila. Nada a ser excluído por enquanto.")
        return False

    # Ok, temos tarefa para ser excluída
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]
    print_log("Tarefa a ser excluída: ", codigo_tarefa)

    # Montar storage
    # ------------------------------------------------------------------
    ponto_montagem=conectar_ponto_montagem_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return False

    # ------------------------------------------------------------------
    # Pastas de destino da tarefa
    # ------------------------------------------------------------------
    caminho_destino = montar_caminho(ponto_montagem, tarefa["caminho_destino"])

    # Inicia procedimentos em background para excluir tarefa
    # --------------------------------------------
    print_log("Iniciando subprocesso para exclusão da tarefa IPED")
    # Os processo filhos irão atualizar o mesmo arquivo log do processo pai
    nome_arquivo_log = obter_nome_arquivo_log()

    # Inicia subprocesso para exclusão da tarefa
    # ------------------------------------------------------------------------------------------------------------------
    label_processo_excluir = "excluir:" + str(codigo_tarefa)
    dados_pai_para_filho = obter_dados_para_processo_filho()
    p_excluir = multiprocessing.Process(
        target=background_excluir_tarefa_iped,
        args=(tarefa, nome_arquivo_log, label_processo_excluir, dados_pai_para_filho,
              caminho_destino)
    )
    p_excluir.start()

    registra_processo_filho(label_processo_excluir, p_excluir)

    # Exclusão de tarefa foi iniciada em background
    Gcodigo_tarefa_excluindo = codigo_tarefa
    Glabel_processo_excluindo = label_processo_excluir
    print_log("Subprocesso para exclusão de tarefa iniciado. Retornado ao loop principal")
    return True


def background_excluir_tarefa_iped(tarefa, nome_arquivo_log, label_processo, dados_pai_para_filho,
              caminho_destino):

    # Preparativos para executar em background
    # ---------------------------------------------------
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

    # Execução em background
    # ---------------------------------------------------
    print_log("Início do subprocesso background_excluir_tarefa_iped")

    codigo_tarefa = tarefa["codigo_tarefa"]

    # Montar storage
    # ------------------------------------------------------------------
    ponto_montagem=conectar_ponto_montagem_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return False

    # Executa sequencia de tarefas para exclusão da tarefa
    # -----------------------------------------------------
    (sucesso, msg_erro)=executa_sequencia_exclusao_tarefa(
        tarefa,
        caminho_destino
    )

    if sucesso:
        print_log("Todas as etapas da exclusão efetuadas com sucesso")
    else:
        # Se ocorreu um erro, retorna a tarefa para o estado original, para tentar novamente
        # Reportar erro para ficar registrado no servidor
        # Desta forma, é possível analisar os erros diretamente
        erro = "Retornado tarefa [[tarefa:" + codigo_tarefa + "]] para início da exclusão em função de ERRO: " + msg_erro
        reportar_erro(erro)

        # Registra situação de devolução
        texto_status="Exclusão falhou: " + msg_erro + " Importante: Assegure-se que você não está acessando a pasta a ser excluída"
        sapisrv_troca_situacao_tarefa_loop(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=GFilaExclusao,
            texto_status=texto_status
        )
        print_log("Exclusão finalizada SEM SUCESSO")

    print_log("Fim subprocesso background_excluir_tarefa_iped")


# Executa cada um dos componentes do processamento do IPED em sequencia
def executa_sequencia_exclusao_tarefa(
        tarefa,
        caminho_destino,
):


    codigo_tarefa = tarefa["codigo_tarefa"]
    erro_excecao=False

    try:

        # 1) Ajustar status para indicar que exclusão foi iniciada
        # =======================================================
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="Exclusão de tarefa iniciada."
        )

        # 2) Exclui pasta da tarefa
        # ====================================
        (sucesso, msg_erro)=exclui_pasta_tarefa(codigo_tarefa, caminho_destino)
        if not sucesso:
            return (False, msg_erro)

        # 3) Ajusta ambiente Multicase (remove pasta da tarefa da lista de evidências)
        # ============================================================================
        (sucesso, msg_erro)=ajusta_multicase(tarefa, codigo_tarefa, caminho_destino)
        if not sucesso:
            return (False, msg_erro)

        # 4) Exclui tarefa no SETEC3
        # =========================
        sapisrv_excluir_tarefa_loop(codigo_tarefa=codigo_tarefa)

    except BaseException as e:
        # Pega qualquer exceção não tratada aqui, para jogar no log
        trc_string=traceback.format_exc()
        erro_excecao = True


    if erro_excecao:
        print_log(trc_string)
        # Tenta registrar no log o erro ocorrido
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="[1169] ERRO em exclusão de tarefa: " + trc_string
        )
        reportar_erro("Tarefa " + str(Gcodigo_tarefa_executando) + "Erro => " + trc_string)
        # subprocesso será abortado, e deixa o processo principal decidir o que fazer
        os._exit(1)


    # Tudo certo, todos os passos foram executados com sucesso
    # ========================================================
    return (True, "")


# ----------------------------------------------------------------------------------------------------------------------
# Exclusão de uma tarefa IPED
# ----------------------------------------------------------------------------------------------------------------------
def exclui_pasta_tarefa(codigo_tarefa, caminho_destino):

    print_log("Pasta de destino para excluir: ", caminho_destino)

    # Se pasta da tarefa não existe, não tem mais nada a fazer
    if not os.path.exists(caminho_destino):
        print_log("Pasta de destino não existe.")
        return (True, "")

    # Exclui pasta da tarefa
    try:
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="Excluindo pasta: "+caminho_destino
        )
        shutil.rmtree(caminho_destino)
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="Pasta de destino excluída"
        )
    except Exception as e:
        erro = "Não foi possível excluir pasta de destino da tarefa: " + str(e)
        return (False, erro)

    # Não pode existir. Se existir, exclusão acima falhou
    dormir(5, "Tempo para deixar sistema operacional perceber exclusão")
    if os.path.exists(caminho_destino):
        erro = "Tentativa de excluir pasta de destino falhou: Verifique se existe algo aberto na pasta, que esteja criando um lock em algum dos seus recursos"
        return (False, erro)

    # Tudo certo
    print_log("Exclusão efetuada com sucesso")
    return (True, "")


# ------------------------------------------------------------------------------------------------------------------
# Execução de tarefas de imagem
# ------------------------------------------------------------------------------------------------------------------

# Executa uma tarefa de iped que esteja ao alcance do agente
# Retorna verdadeiro se executou uma tarefa e falso se não executou nada

def executar_tarefas_tableau():


    # Recupera a lista de pasta das tarefas de imagem
    # que necessitam de pasta de destino
    # ---------------------------------------------------------------------------
    try:
        storage=Gconfiguracao["storage_unico"]
        print_log("Buscando tarefas de imagem para storage:", storage)
        (sucesso, msg_erro, tarefas_imagem) = sapisrv_chamar_programa(
            "sapisrv_obter_tarefas_imagem.php",
            {'storage': storage
             }
        )
    except BaseException as e:
        erro="Não foi possível recuperar a situação atualizada das tarefas do servidor"
        return (False, erro)

    if not sucesso:
        return (False, msg_erro)

    # var_dump(sucesso)
    var_dump(tarefas_imagem)
    # die('ponto1581')

    print_log("Foram recuperadas", len(tarefas_imagem), "tarefas de imagem")

    for t in tarefas_imagem:

        codigo_tarefa=t['codigo_tarefa']
        codigo_situacao_tarefa=int(t['codigo_situacao_tarefa'])

        # Se está na fila para criação de pasta,
        # Cria pasta para tarefa
        if codigo_situacao_tarefa==GFilaCriacaoPasta:
            criar_pasta_tableau(codigo_tarefa)

        # Se está aguardando PCF,
        # Verifica se upload já iniciou
        if codigo_situacao_tarefa==GAguardandoPCF:
            monitorar_tarefa(codigo_tarefa)

        # Se já está executando, monitora tarefa
        if codigo_situacao_tarefa == GTableauExecutando:
            monitorar_tarefa(codigo_tarefa)




def obter_tarefa(codigo_tarefa):

    global Gcache_tarefa

    # Recupera tarefa
    print_log("Buscando dados da tarefa", codigo_tarefa)
    tarefa = recupera_tarefa_do_setec3(codigo_tarefa)

    # Armazena em cache
    Gcache_tarefa[codigo_tarefa]=tarefa

    return tarefa



# Se tarefa já estiver em cache, devolve dados do cache
# Caso contrário, consulta o servidor para buscar os dados
def obter_tarefa_cache(codigo_tarefa):

    if codigo_tarefa in Gcache_tarefa:
        # Está em cache. Retorna valor do cache
        return Gcache_tarefa[codigo_tarefa]

    # Obtem tarefa que não está em cache
    return obter_tarefa(codigo_tarefa)



def criar_pasta_tableau(codigo_tarefa):

    print_log("Criação de pasta para tarefa",codigo_tarefa)

    # Recupera tarefa
    tarefa = obter_tarefa_cache(codigo_tarefa)
    if tarefa is None:
        print_log("Criação de pasta falhou, pois não foi possível recuperar tarefa")
        return False


    # Ok, temos trabalho a fazer
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]

    # Montar storage para a tarefa
    # Normalmete o storage está na própria máquina que está rodando
    # o sapi_tablau, mas vamos deixar genérico.
    # ------------------------------------------------------------------
    ponto_montagem=conectar_ponto_montagem_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return False

    # Verifica se pasta raiz do tableau existe
    pasta_raiz_tableau = montar_caminho(ponto_montagem,
                                   Gpasta_raiz_tableau)

    if not os.path.exists(pasta_raiz_tableau):
        print_log("ERRO: Pasta raiz do tableau não foi encontrada: ", pasta_raiz_tableau)
        print_log("Não é possível criar pasta para a tarefa.")
        print_log("Siga o roteiro de instalação do storage conforme definido na Wiki do SAPI")


    # Pasta para a tarefa
    pasta_tableau = montar_caminho(ponto_montagem,
                                   Gpasta_raiz_tableau,
                                   tarefa["dados_item"]["material_simples"])

    # Se pasta não existe, cria
    if not os.path.exists(pasta_tableau):
        # Cria pasta de destino
        try:
            print_log("Criando pasta", pasta_tableau)
            os.makedirs(pasta_tableau)
            print_log("Pasta criada com sucesso")
        except Exception as e:
            erro = "Não foi possível criar pasta: " + str(e)
            # Pode ter alguma condição temporária impedindo. Continuar tentando.
            return False


    # Se pasta de destino existe, atualiza a situação de tarefa para GAguardandoPCF
    if os.path.exists(pasta_tableau):
        sapisrv_troca_situacao_tarefa_loop(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=GAguardandoPCF,
            texto_status="Pasta para upload do tableau está pronta"
        )

    # Tudo certo
    return True


# Retorna verdadeiro se a tarefa já está sendo acompanhada
def tarefa_sendo_acompanhada(codigo_tarefa):
    return False



def monitorar_tarefa(codigo_tarefa):

    # Se tarefa já iniciou e está sendo acompanhada,
    # não há mais nada a fazer
    if tarefa_sendo_acompanhada(codigo_tarefa):
        # Não tem mais nada a fazer
        return True

    # Recupera dados da tarefa do cache,
    # para evitar sobrecarregar o servidor com requisições
    tarefa = obter_tarefa_cache(codigo_tarefa)

    # Montar storage para a tarefa
    # Normalmete o storage está na própria máquina que está rodando
    # o sapi_tablau, mas vamos deixar genérico.
    # ------------------------------------------------------------------------
    ponto_montagem=conectar_ponto_montagem_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return False

    # Pasta para a tarefa
    pasta_tableau = montar_caminho(ponto_montagem,
                                   Gpasta_raiz_tableau,
                                   tarefa["dados_item"]["material_simples"])

    # Se pasta não existe, tem algo erro aqui!!!
    if not os.path.exists(pasta_tableau):
        print_log("Erro: Pasta do tableau ", pasta_tableau,"não existe para tarefa", codigo_tarefa)
        return False

    # Se pasta da tarefa está vazia,
    # ou seja, ainda não foi iniciado o upload,
    # então não tem nada a fazer
    # Recupera tamanho da pasta
    carac = obter_caracteristicas_pasta_ok(pasta_tableau)
    if carac is None:
        return False

    if carac["tamanho_total"]==0:
        # Pasta está zerada (tamanho zero)
        # Logo, ainda não tem nada a fazer
        return False

    # Acompanha execução da tarefa de cópia
    deu_erro = False
    erro_exception=None
    try:

        if tarefa["codigo_situacao_tarefa"] != GTableauExecutando:
            # Registra comando de execução do IPED
            sapisrv_troca_situacao_tarefa_loop(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=GTableauExecutando,
                texto_status="Pasta do tableau com dados"
            )

        # Inicia processo para acompanhamento em background
        print_log("Tarefa: ", codigo_tarefa, "Pasta do tableau tem conteúdo. Iniciando acompanhamento")

        # Inicia subprocesso para acompanhamento do Tableau
        # ------------------------------------------------
        nome_arquivo_log = obter_nome_arquivo_log()
        dados_pai_para_filho = obter_dados_para_processo_filho()
        label_processo = "acompanhar:" + str(codigo_tarefa)
        p_acompanhar = multiprocessing.Process(
            target=background_acompanhar_tableau,
            args=(codigo_tarefa, pasta_tableau,
                  nome_arquivo_log, label_processo, dados_pai_para_filho
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
        print_log("Erro na chamada do acompanahmento de tarefa: ", erro_exception)
        return False


    time.sleep(100)
    print("Interrompendo principal para iniciar apenas uma tarefa")
    die('ponto1784')

    # Ok, tudo certo. O resto é com o processo em background
    return True


def resto():

    # kkk
    die('ponto1588')

    # ------------------------------------------------------------------
    # Pastas de origem e destino
    # ------------------------------------------------------------------
    caminho_origem  = montar_caminho(ponto_montagem, tarefa["caminho_origem"])
    caminho_destino = montar_caminho(ponto_montagem, tarefa["caminho_destino"])

    pasta_item = montar_caminho(ponto_montagem,
                                   tarefa["dados_solicitacao_exame"]["pasta_memorando"],
                                   tarefa["pasta_item"])

    # ------------------------------------------------------------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------------------------------------------------------------

    # Prepara parâmetros para execução das subatarefas do IPED
    # ========================================================
    tipo_iped = tarefa["tipo"]
    comando = Gconfiguracao["tipo_tarefa"][tipo_iped]["comando"]

    # Adiciona a pasta de origem e destino
    comando = comando + " -d " + caminho_origem + " -o " + caminho_destino

    # Define arquivo para log
    caminho_log_iped = montar_caminho(caminho_destino, "iped.log")
    comando = comando + " -log " + caminho_log_iped

    # Sem interface gráfica
    comando = comando + " --nogui "

    # Portable
    # Isto aqui é essencial. Caso contrário o multicase não funciona...
    comando = comando + " --portable "

    # Redireciona saída de tela (normal e erro) para arquivo
    caminho_tela_iped = montar_caminho(caminho_destino, "iped_tela.txt")
    comando = comando + " >" + caminho_tela_iped + " 2>&1 "

    # Para teste
    # comando='dir'
    # comando='java -version'
    # comando='java' #Executa mas com exit code =1

    # Para teste
    # caminho_origem  ="C:\\teste_iped\\Memorando_1086-16\\item11\\item11_extracao"
    # caminho_destino ="C:\\teste_iped\\Memorando_1086-16\\item11\\item11_extracao_iped"
    # comando='java -Xmx24G -jar c:\\iped-basico-3.11\\iped.jar -d ' + caminho_origem + " -o " + caminho_destino

    # var_dump(comando)

    # Inicia procedimentos em background para executar e acompanhar tarefa
    # Inicia subprocessos
    # --------------------------------------------
    print_log("Iniciando subprocesso para execução da sequencia do IPED")
    # Os processo filhos irão atualizar o mesmo arquivo log do processo pai
    nome_arquivo_log = obter_nome_arquivo_log()

    # Inicia processo filho para execução do iped
    # ------------------------------------------------------------------------------------------------------------------
    label_processo_executar = "executar:" + str(codigo_tarefa)
    dados_pai_para_filho=obter_dados_para_processo_filho()
    p_executar = multiprocessing.Process(
        target=background_executar_iped,
        args=(tarefa, nome_arquivo_log, label_processo_executar, dados_pai_para_filho,
              comando,
              caminho_origem, caminho_destino,
              caminho_log_iped, caminho_tela_iped, pasta_item)
    )
    p_executar.start()

    registra_processo_filho(label_processo_executar, p_executar)


    # Tarefa foi iniciada em background
    Gcodigo_tarefa_executando = codigo_tarefa
    Glabel_processo_executando = label_processo_executar
    print_log("Subprocessos para execução iniciado. Retornado ao loop principal")
    return True



def background_executar_iped(tarefa, nome_arquivo_log, label_processo, dados_pai_para_filho,
                             comando,
                             caminho_origem, caminho_destino,
                             caminho_log_iped, caminho_tela_iped, pasta_item):

    # Preparativos para executar em background
    # ---------------------------------------------------
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

    # Execução em background
    # ---------------------------------------------------
    print_log("Início do subprocesso background_executar_iped")

    codigo_tarefa = tarefa["codigo_tarefa"]

    (sucesso, msg_erro)=executa_sequencia_iped(
        tarefa,
        comando,
        caminho_origem,
        caminho_destino,
        caminho_log_iped,
        caminho_tela_iped,
        pasta_item
    )

    if sucesso:
        # Tudo certo, finalizado com sucesso
        dados_relevantes = dict()
        dados_relevantes['laudo'] = Gdados_laudo
        sapisrv_troca_situacao_tarefa_loop(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=GFinalizadoComSucesso,
            texto_status="Tarefa de IPED completamente concluída",
            dados_relevantes=dados_relevantes,
            tamanho_destino_bytes=Gtamanho_destino_bytes
        )
        print_log("Tarefa finalizada com sucesso")
    else:
        # Se ocorreu um erro, aborta tarefa
        # Isto fará com que o processo principal se encerre, gerando a auto atualização dos componentes
        # sapi_tableau, iped, etc
        print_log("ERRO: ", msg_erro)
        abortar(codigo_tarefa, msg_erro)
        print_log("Tarefa foi abortada")

    print_log("Fim subprocesso background_executar_iped")


# Executa cada um dos componentes do processamento do IPED em sequencia
def executa_sequencia_iped(
        tarefa,
        comando,
        caminho_origem,
        caminho_destino,
        caminho_log_iped,
        caminho_tela_iped,
        pasta_item):

    # Inicializa dados para laudo
    global Gdados_laudo
    Gdados_laudo = dict()


    codigo_tarefa = tarefa["codigo_tarefa"]
    erro_excecao=False

    try:

        # 1) Retira da pasta alguns arquivos que não precisam ser indexados (ex: UFDR)
        # ===========================================================================
        # TODO: Isto aqui não está legal...tem que refazer com conceito de pasta
        # temporária (xxx_ignorados)
        #(sucesso, msg_erro, lista_movidos)=mover_arquivos_sem_iped(
        #    caminho_origem,
        #    pasta_item
        #)
        #if not sucesso:
        #    return (False, msg_erro)


        # 2) IPED
        # ====================================
        # Executa IPED
        (sucesso, msg_erro)=executa_iped(codigo_tarefa, comando,
                                         caminho_origem, caminho_destino, caminho_log_iped,
                                         caminho_tela_iped)
        if not sucesso:
            return (False, msg_erro)

        # 3) Recupera dados do log para utilizar em laudo
        # ===============================================
        (sucesso, msg_erro)=recupera_dados_laudo(codigo_tarefa, caminho_log_iped)
        if not sucesso:
            return (False, msg_erro)

        # 4) Cálculo de HASH
        # ====================================
        # Calcula hash
        (sucesso, msg_erro)=calcula_hash_iped(codigo_tarefa, caminho_destino)
        if not sucesso:
            return (False, msg_erro)

        # 5) Ajusta ambiente para Multicase
        # =================================
        (sucesso, msg_erro)=ajusta_multicase(tarefa, codigo_tarefa, caminho_destino)
        if not sucesso:
            return (False, msg_erro)

        # 6) Retorna para a pasta os arquivos que não precisavam ser processados pelo IPED
        # ================================================================================
        # Todo: Quando refizer o passo 1, refazer a restauração
        #(sucesso, msg_erro) = restaura_arquivos_movidos(lista_movidos)
        #if not sucesso:
        #    return (False, msg_erro)

        # 7) Calcula o tamanho final da pasta do IPED
        (sucesso, msg_erro) = calcula_tamanho_total_pasta(caminho_destino)
        if not sucesso:
            return (False, msg_erro)


    except BaseException as e:
        # Pega qualquer exceção não tratada aqui, para jogar no log
        trc_string=traceback.format_exc()
        erro_excecao = True


    if erro_excecao:
        print_log(trc_string)
        # Tenta registrar no log o erro ocorrido
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="ERRO em sapi_tableau: " + trc_string
        )
        reportar_erro("Tarefa " + str(Gcodigo_tarefa_executando) + "Erro => " + trc_string)
        # subprocesso será abortado, e deixa o processo principal decidir o que fazer
        os._exit(1)


    # Tudo certo, todos os passos foram executados com sucesso
    # ========================================================
    return (True, "")


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
            print_tela_log("Aguardando encerramento de", len(lista),"processo(s). Situação incomum!")
        # Aguarda e repete, até finalizar tudo...isto não deveria acontecer....
        time.sleep(2)

    # Ok, tudo encerrado
    # -----------------------------------------------------------------------------------------------------------------
    print_log(" ===== FINAL ", Gprograma, " - (Versao", Gversao, ")")
    os._exit(1)




# ======================================================================
# Rotina Principal 
# ======================================================================

def main():

    # Processa parâmetros logo na entrada, para garantir que configurações relativas a saída sejam respeitads
    sapi_processar_parametros_usuario()

    # Se não estiver em modo background (opção do usuário),
    # liga modo dual, para exibir saída na tela e no log
    if not modo_background():
        ligar_log_dual()

    # Cabeçalho inicial do programa
    # ------------------------------------------------------------------------------------------------------------------
    # Verifica se programa já está rodando (outra instância)
    if existe_outra_instancia_rodando(Gcaminho_pid):
        print("Já existe uma instância deste programa rodando.")
        print("Abortando execução, pois só pode haver uma única instância deste programa")
        sys.exit(0)

    # Inicialização do programa
    # -----------------------------------------------------------------------------------------------------------------
    print_log(" ===== INÍCIO ", Gprograma, " - (Versao", Gversao, ")")

    # Inicializa programa
    if not inicializar():
        # Falhou na inicialização, talvez falha de comunicação, talvez mudança de versão...
        finalizar_programa()

    while True:

        # Execução
        #alguma_pasta_criada = ciclo_executar()
        #algo_excluido = ciclo_excluir()

        executar_tarefas_tableau()
        dormir(60, "Pausa entre ciclo de execução de tarefas de imagens")
        if not inicializar():
            # Falhou na inicialização, talvez falha de comunicação, talvez mudança de versão...
            # Irá finalizar, e o scheduler vai reiniciar o programa no próximo ciclo
            finalizar_programa()


        # #alguma_pasta_criada = ciclo_criar_pasta_imagem()
        #
        # #if alguma_pasta_criada or algo_excluido:
        #
        # #if alguma_pasta_criada:
        # # Como servidor não está ocioso, faz uma pequena pausa e prossegue
        # #    #time.sleep(60)
        # #    #continue
        # #else:
        #     # Se não fez nada no ciclo,
        #     # faz uma pausa para evitar sobrecarregar o servidor com requisições
        #     dormir(GdormirSemServico)
        #     # Depois que volta da soneca da ociosidade e reinicializa
        #     # pois algo pode ter mudado
        #     # Se isto acontecer, finaliza sapi_tableau para que seja atualizado
        #     if not inicializar():
        #         # Falhou na inicialização, talvez falha de comunicação, talvez mudança de versão...
        #         finalizar_programa()

# ----------------------------------------------------------------------------------
# Chamada para rotina principal
# ----------------------------------------------------------------------------------
if __name__ == '__main__':

    ret=parse_arquivo_log("tableau_imagem.log", "item01Arrecadacao01")
    var_dump(ret)
    die('ponto2152')

    main()

