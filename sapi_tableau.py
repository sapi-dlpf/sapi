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
        sapisrv_inicializar_ok(Gprograma, Gversao, auto_atualizar=True, nome_arquivo_log=nome_arquivo_log)
        print_log('Inicializado com sucesso', Gprograma, ' - ', Gversao)

        # Obtendo arquivo de configuração
        print_log("Obtendo configuração")
        Gconfiguracao = sapisrv_obter_configuracao_cliente(Gprograma)
        print_log(Gconfiguracao)


    except SapiExceptionProgramaFoiAtualizado as e:
        print_log("Programa foi atualizado para nova versão em: ",e)
        print_log("Encerrando para ser reinicializadoem versão correta")
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


# Acompanha a execução do IPED e atualiza o status da tarefa
def background_acompanhar_iped(codigo_tarefa, caminho_tela_iped,
                               nome_arquivo_log, label_processo, dados_pai_para_filho):

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

    print_log("Processo de acompanhamento de IPED")

    # Fica em loop infinito. Será encerrado pelo pai (com terminate)
    while True:

        if os.path.isfile(caminho_tela_iped):
            print_log("Arquivo de tela de iped ainda não existe. Aguardando")
            time.sleep(30)

        # Le arquivo de resultado (tela) e busca pela última mensagem de situação e projeção
        # Exemplo:
        # IPED-2017-01-31 17:14:11 [MSG] Processando 29308/39593 (25%) 31GB/h Termino em 0h 5m 33s
        texto_status=None
        with open(caminho_tela_iped, "r") as fentrada:
            for linha in fentrada:
                # Troca tabulação por espaço
                linha=linha.replace('\t',' ')
                # Procura por linha de status
                if "[MSG] Processando" in linha:
                    texto_status=linha

        # Atualiza status
        if texto_status is not None:
            print_log("Atualizando status para tarefa",codigo_tarefa,":", texto_status)
            sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)
            # Intervalo entre atualizações de status
            dormir(GtempoEntreAtualizacoesStatus, "Dormindo entre atualização de status do IPED")
        else:
            # Como ainda não atualizou o status, vamos dormir por um período menor
            # Assim pega a primeira atualização de status logo que sair
            dormir(30)


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


# Ajuste para execução multicase
def ajusta_multicase(tarefa, codigo_tarefa, caminho_destino):

    # Situação informativa
    # -------------------------------------------------------------
    sapisrv_atualizar_status_tarefa_informativo(
        codigo_tarefa=codigo_tarefa,
        texto_status="Efetuando ajuste para IPED multicase"
    )

    # Montar storage
    # ------------------------------------------------------------------
    ponto_montagem=conectar_ponto_montagem_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        erro="Não foi possível conectar no storage"
        return (False, erro)

    # ------------------------------------------------------------------------------------------------------------------
    # Pastas relacionadas
    # ------------------------------------------------------------------------------------------------------------------
    # O iped multicase possui a seguinte estrutura:
    # Memorando_xxxx_xx
    #   + multicase
    #     + indexador
    #       + lib
    #       + conf
    #       + Ferramenta de Pesquisa.exe
    #       + iped-itens.txt
    #
    # Cada item possui a seguinte estrutura
    # Memorando_xxxx_xx
    #   + item01Arrecadacao01
    #   + item01Arrecadacao01_iped
    #     + IPED-SearchApp.exe
    #     + Lista de Arquivos.csv
    #     + indexador
    #       + lib
    #       + conf
    #       + ....
    #
    # ------------------------------------------------------------------------------------------------------------------

    # Ajusta caminho de destino
    caminho_destino = caminho_destino + "\\"

    # Extraí pasta do memorando
    # Localiza pasta do item no caminho de destino
    inicio_pasta_item = caminho_destino.find(tarefa["pasta_item"])
    caminho_memorando = caminho_destino[0:inicio_pasta_item]

    # Caminho para bat
    nome_bat = "ferramenta_pesquisa.bat"
    caminho_bat = montar_caminho(caminho_memorando, nome_bat)

    caminho_iped_multicase      = montar_caminho(caminho_memorando,"multicase")

    # Recupera a lista de pasta das tarefas IPED que foram concluídas com sucesso
    # ---------------------------------------------------------------------------
    codigo_solicitacao_exame_siscrim=tarefa["dados_solicitacao_exame"]["codigo_documento_externo"]
    try:
        (sucesso, msg_erro, tarefas_iped_sucesso) = sapisrv_chamar_programa(
            "sapisrv_obter_tarefas.php",
            {'tipo': 'iped%',
             'codigo_solicitacao_exame_siscrim': codigo_solicitacao_exame_siscrim
             }
        )
    except BaseException as e:
        erro="Não foi possível recuperar a situação atualizada das tarefas do servidor"
        return (False, erro)

    if not sucesso:
        return (False, msg_erro)


    # Processa tarefas iped,
    # selecionando apenas as que já passaram pela fase do IPED
    # ---------------------------------------------------------------------
    caminhos_tarefas_iped_finalizado=list()
    for t in tarefas_iped_sucesso:
        tarefa_finalizada=t["tarefa"]
        # Problema: O teste >=GIpedFinalizado pode ser um problema no futuro...
        # se algum dia for inserido um código de erro maior que 62...
        # Códigos de erro (abortado, por exemplo) tem que ser pequenos,
        # obrigatoriamente no início do range
        codigo_situacao_tarefa=int(tarefa_finalizada["codigo_situacao_tarefa"])
        if codigo_situacao_tarefa>=GIpedFinalizado:
            caminhos_tarefas_iped_finalizado.append(tarefa_finalizada["caminho_destino"])

    # Se não tem nenhuma tarefa com iped Finalizado
    # exclui a extrutura multicase e encerra
    if len(caminhos_tarefas_iped_finalizado) == 0:
        print_log("Não possui nenhuma tarefa com iped finalizado. Multicase será excluído")
        return excluir_multicase(caminho_iped_multicase, caminho_bat)

    # Ok, existem tarefas concluídas com sucesso, prossegue na montagem do multicase

    # Confere se todas as pastas das tarefas finalizadas estão ok
    # -------------------------------------------------------------
    for caminho_destino in caminhos_tarefas_iped_finalizado:
        pasta_iped=montar_caminho(ponto_montagem, caminho_destino)
        if not os.path.exists(pasta_iped):
            erro="[756] Não foi encontrada pasta de IPED de tarefa concluída"+pasta_iped
            return (False, erro)

        # Verifica integridade da pasta
        if os.path.exists(montar_caminho(pasta_iped, "indexador", "lib")) \
                and os.path.exists(montar_caminho(pasta_iped, "indexador", "conf")) \
                and os.path.isfile(montar_caminho(pasta_iped, GnomeProgramaInterface)):
            print_log("Pasta", pasta_iped," está íntegra")
        else:
            erro="[765] Pasta de IPED danificada: "+pasta_iped
            return (False, erro)

    # A primeira pasta de IPED será utilizada como modelo, para copiar lib e outros componentes
    # para o multicase
    caminho_iped_origem=montar_caminho(ponto_montagem, caminhos_tarefas_iped_finalizado[0])

    # Código antigo, para verificar pastas _iped
    # Confere se todas as pastas de tarefas iped concluídas existem
    # -------------------------------------------------------------
    # qtd_pastas_iped=0
    # lista_pastas=list()
    # caminho_iped_origem=None
    # for root, subdirs, files in os_walklevel(caminho_memorando, level=1):
    #     if ("_iped" in root):
    #         # Converte caminho absoluto em relativo
    #         # Exemplo:
    #         # De    \\gtpi-sto-01\storage\Memorando_1086-16\item11\item11_extracao_iped
    #         # para  ..\item11\item11_extracao_iped'
    #         pasta="..\\" +root.replace(caminho_memorando,'')
    #         lista_pastas.append(pasta)
    #         qtd_pastas_iped=qtd_pastas_iped+1
    #         # Verifica se abaixo deste pasta existe uma pasta indexador/lib
    #         # Se existir, guarda para uso futuro
    #         if caminho_iped_origem is None:
    #             if      os.path.exists(montar_caminho(root,"indexador", "lib"))\
    #                 and os.path.exists(montar_caminho(root,"indexador", "conf"))\
    #                 and os.path.isfile(montar_caminho(root,GnomeProgramaInterface)):
    #                 caminho_iped_origem=root


    # Cria estrutura multicase, copiando elementos da pasta caminho_iped_origem para caminho_iped_multicase
    # -----------------------------------------------------------------------------------------------------

    # Pasta para o indexador do multicase
    caminho_indexador_multicase = montar_caminho(caminho_iped_multicase, "indexador")

    # Cria pastas para multicase, se ainda não existirem
    try:
        if not os.path.exists(caminho_iped_multicase):
            os.makedirs(caminho_iped_multicase)

        if not os.path.exists(caminho_indexador_multicase):
            os.makedirs(caminho_indexador_multicase)
    except Exception as e:
        erro = "[818] Não foi possível criar estrutura de pasta para multicase " + str(e)
        return (False, erro)

    # Confere criação de pasta
    if os.path.exists(caminho_iped_multicase):
        print_log("Encontrada pasta" + caminho_iped_multicase)
    else:
        erro = "[791] Situação inesperada: Pasta " + caminho_iped_multicase + " não existe"
        return (False, erro)

    if os.path.exists(caminho_indexador_multicase):
        print_log("Encontrada pasta" + caminho_indexador_multicase)
    else:
        erro = "[797] Situação inesperada: Pasta " + caminho_indexador_multicase + " não existe"
        return (False, erro)


    # ------------------------------------------------------------------------------------------------------------------
    # Pasta LIB => Esta pasta contém os programas java e bibliotecas utilizados na pesquisa
    # Efetua a cópia da pasta lib de um item para a pasta do multicase caso isto não tenha sido feito anteriormente
    # ------------------------------------------------------------------------------------------------------------------
    caminho_lib_origem      =montar_caminho(caminho_iped_origem   , "indexador", "lib")
    caminho_lib_multicase   =montar_caminho(caminho_iped_multicase, "indexador", "lib")

    # Se pasta lib não existe, cria pasta, copiando da pasta de processamento de IPED do item
    if not os.path.exists(caminho_lib_multicase):
        try:
            # Cria pasta de lib
            print_log("Copiando lib " + caminho_iped_origem +
                      " para lib da pasta multicase " + caminho_lib_multicase)
            shutil.copytree(caminho_lib_origem, caminho_lib_multicase)
        except Exception as e:
            erro = "Não foi possível copiar lib para multicase: " + str(e)
            return (False, erro)

    # Confere se lib existe
    if os.path.exists(caminho_lib_multicase):
        print_log("Encontrada pasta " + caminho_lib_multicase + ": ok")
    else:
        erro = "[823] Situação inesperada: Pasta [" + caminho_lib_multicase + "] foi copiada MAS NÃO existe"
        return (False, erro)

    # ------------------------------------------------------------------------------------------------------------------
    # Pasta CONF => Copia a pasta conf do item para a pasta do iped multicase, caso isto ainda não tenha sido feito
    # A rigor, cada item pode ter uma configuração independente, logo existe um problema conceitual aqui.
    # Mas como todos são rodados pelo sistema, isto não deve dar diferença
    # ------------------------------------------------------------------------------------------------------------------
    caminho_conf_origem     =montar_caminho(caminho_iped_origem,      "indexador", "conf")
    caminho_conf_multicase  =montar_caminho(caminho_iped_multicase,   "indexador", "conf")

    # Se pasta conf não existe, cria pasta, copiando da pasta de processamento de IPED do item
    if not os.path.exists(caminho_conf_multicase):
        try:
            print_log("Copiando conf do item" + caminho_conf_origem +
                      " para conf da pasta multicase" + caminho_conf_multicase)
            shutil.copytree(caminho_conf_origem, caminho_conf_multicase)
        except Exception as e:
            erro = "Não foi possível copiar para multicase: " + str(e)
            return (False, erro)

    # Confere se conf existe
    if os.path.exists(caminho_conf_multicase):
        print_log("Encontrada pasta", caminho_conf_multicase, ": ok")
    else:
        erro = "[848] Situação inesperada: Pasta" + caminho_conf_multicase + "não existe"
        return (False, erro)

    # ------------------------------------------------------------------------------------------------------------------
    # Copia IPED-SearchApp.exe para pasta do multicase
    # ------------------------------------------------------------------------------------------------------------------
    caminho_de   = montar_caminho(caminho_iped_origem,  GnomeProgramaInterface)
    caminho_para = montar_caminho(caminho_iped_multicase, GnomeProgramaInterface)
    try:
        print_log("Copiando arquivo" + caminho_de + "para" + caminho_para)
        shutil.copy(caminho_de, caminho_para)
    except Exception as e:
        erro = "Não foi possível copiar" + caminho_de + "para" + caminho_para +": " + str(e)
        return (False, erro)

    # Confere se copiou ok
    if os.path.isfile(caminho_para):
        print_log("Encontrado arquivo", caminho_para)
    else:
        erro = "[867] Situação inesperada: Arquivo " + caminho_para + " não existe"
        return (False, erro)

    # ------------------------------------------------------------------------------------------------------------------
    # Gera arquivo contendo as listas de pasta dos itens, para ser utilizado na opção multicase
    # Este passo sempre é executado e o arquivo é refeito, refletindo o conteúdo completo da pasta
    # ------------------------------------------------------------------------------------------------------------------
    arquivo_pastas="iped-itens.txt"
    caminho_arquivo_pastas = montar_caminho(caminho_iped_multicase, arquivo_pastas)

    # # Recupera lista de pastas com processamento por IPED
    # qtd_pastas_iped=0
    # lista_pastas=list()
    # for root, subdirs, files in os_walklevel(caminho_memorando, level=1):
    #     if ("_iped" in root):
    #         # Converte caminho absoluto em relativo
    #         # Exemplo:
    #         # De    \\gtpi-sto-01\storage\Memorando_1086-16\item11\item11_extracao_iped
    #         # para  ..\item11\item11_extracao_iped'
    #         pasta="..\\" +root.replace(caminho_memorando,'')
    #         lista_pastas.append(pasta)
    #         qtd_pastas_iped=qtd_pastas_iped+1
    lista_pastas = list()
    for p in caminhos_tarefas_iped_finalizado:
        # Converte caminho absoluto em relativo
        # Exemplo:
        # De    \\gtpi-sto-01\storage\Memorando_1086-16\item11\item11_extracao_iped
        # para  ..\item11\item11_extracao_iped'
        #pasta="..\\" +p.replace(caminho_memorando,'')
        inicio_pasta_item = p.find("\\item")
        if inicio_pasta_item==-1:
            inicio_pasta_item = p.find("/item")
            if inicio_pasta_item == -1:
                erro = "[945] Não foi encontrada subpasta do item em " + p
                return (False, erro)

        #print(inicio_pasta_item)
        p_comecando_item = p[inicio_pasta_item:]
        #print(p_comecando_item)
        pasta = ".." + p_comecando_item
        #print(pasta)

        #zzz
        #print_log("pasta para ajustar", p)
        #print_log("Caminho memorando: ", caminho_memorando)
        print_log("Multicase: Incluido em ", arquivo_pastas, "a pasta",pasta)
        lista_pastas.append(pasta)


    # Criar/recria arquivo
    try:
        print_log("Criando/Atualizando arquivo [" + caminho_arquivo_pastas + "]")
        # Cria arquivo
        f = open(caminho_arquivo_pastas, 'w')
        # Escreve lista de pastas, cada pasta em uma linha
        f.write("\n".join(lista_pastas))
        f.close()
    except Exception as e:
        erro = "Não foi possível criar arquivo: " + str(e)
        # Neste caso, aborta tarefa, pois este erro deve ser analisado
        return (False, erro)

    # ------------------------------------------------------------------------------------------------------------------
    # Cria arquivo bat "ferramenta_pesquisa.bat"
    # Este será o arquivo que o usuário irá clicar para invocar o IPED multicase
    # ------------------------------------------------------------------------------------------------------------------
    conteudo_bat="""
@echo off
REM SAPI - Carregamento do caso no iped, modo multicase
REM ====================================================================================
REM echo %~d0
REM Se nao tem drive, exibe mensagem explicativa
IF "%~d0" == "\\\\" (
  echo .
  echo *** ERRO: Nao existe drive, IPED nao pode ser invocado ***
  echo .
  echo Problema:
  echo - Voce estah tentando invocar a ferramenta de pesquisa direto de uma pasta compartilhada da rede, que nao estah mapeada.
  echo .
  echo Solucao:
  echo - Efetue um mapeamento da pasta de rede para um letra, por exemplo z:
  echo - Navegue para pasta mapeada e clique novamente sobre ferramenta_pesquisa.bat
  echo .
  pause
  exit
)

REM Ajusta diretório corrente para a pasta de armazenamento do multicase
REM --------------------------------------------------------------------
CD /D %~dp0
CD multicase

REM Executa Ferramenta de Pesquisa, passando os parâmetros para multicase
REM --------------------------------------------------------------------
"xxx_programa_interface.exe" -multicases iped-itens.txt

echo Carregando IPED (Indexador e Processador de Evidencias Digitais). Aguarde alguns segundos...
REM Isto aqui embaixo é só um truque para dar um sleep para dar tempo do IPED carregar
ping -n 120 127.0.0.1 > nul

REM =========================================================================
REM Para debug
REM Se o comando acima falhar, habilitar as linhas a seguir (retirar o REM)
REM para poder observar a mensagem de erro
REM =========================================================================
REM java -jar "indexador/lib/iped-search-app.jar -multicases iped-itens.txt"
REM pause
"""

    # Troca o nome do programa do executavel
    conteudo_bat=conteudo_bat.replace("xxx_programa_interface.exe", GnomeProgramaInterface)

    # Se não existe, cria
    if not os.path.isfile(caminho_bat):
        try:
            print_log("Criando arquivo [" + caminho_bat + "]")
            # Cria arquivo
            f = open(caminho_bat, 'w')
            f.write(conteudo_bat)
            f.close()
        except Exception as e:
            erro = "Não foi possível criar arquivo: " + str(e)
            # Neste caso, aborta tarefa, pois este erro deve ser analisado
            return (False, erro)

    # Confere se arquivo existe
    if os.path.isfile(caminho_bat):
        print_log("Encontrado arquivo [" + caminho_bat + "]: ok")
    else:
        erro = "[976] Situação inesperada: Arquivo [" + caminho_bat + "] não existe"
        return (False, erro)

    # Tudo certo, ajuste multicase concluído
    sapisrv_troca_situacao_tarefa_loop(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=GIpedMulticaseAjustado,
        texto_status="Ajuste multicase efetuado")
    return (True, "")

# Retorna: (sucess/insucesso, erro)
def excluir_multicase(caminho_iped_multicase, caminho_bat):

    print_log("Efetuando exclusão de componentes multicase")
    try:
        # Exclui pasta multicase
        if os.path.exists(caminho_iped_multicase):
            shutil.rmtree(caminho_iped_multicase)
            print_log("Excluída pasta:", caminho_iped_multicase)
        else:
            print_log("Pasta multicase", caminho_iped_multicase, "não existe")
        # Exclui bat de pesquisa
        if os.path.isfile(caminho_bat):
            os.remove(caminho_bat)
            print_log("Excluído arquivo:", caminho_bat)
        else:
            print_log("Arquivo", caminho_bat, "não existe")

        # Sucesso
        return (True, "")

    except Exception as e:
        erro = "Erro na exclusão de multicase: " + str(e)
        # Neste caso, aborta tarefa, pois este erro deve ser analisado
        return (False, erro)

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

    return ponto_montagem


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

    print_log("Buscando tarefas de imagem que necessitam de pasta para armazenamento")

    # Recupera a lista de pasta das tarefas de imagem
    # que necessitam de pasta de destino
    # ---------------------------------------------------------------------------
    try:
        (sucesso, msg_erro, tarefas_imagem) = sapisrv_chamar_programa(
            "sapisrv_obter_tarefas_imagem.php",
            {'storage': Gconfiguracao["storage_unico"]
             }
        )
    except BaseException as e:
        erro="Não foi possível recuperar a situação atualizada das tarefas do servidor"
        return (False, erro)

    if not sucesso:
        return (False, msg_erro)

    # var_dump(sucesso)
    # var_dump(tarefas_imagem)
    # die('ponto1581')

    # Cria pasta para tarefas
    for t in tarefas_imagem:

        print(t)

        # Tem que estar aguardando criação de pasta
        if int(t['codigo_situacao_tarefa'])!=int(GFilaCriacaoPasta):
            continue

        # Ok, pasta deve ser criada
        criar_pasta_tableau(t['codigo_tarefa'])


def criar_pasta_tableau(codigo_tarefa):

    # kkk
    print_log("Criação de pasta para tarefa",codigo_tarefa)

    # Recupera tarefa
    print_log("Buscando dados da tarefa", codigo_tarefa)
    tarefa = recupera_tarefa_do_setec3(codigo_tarefa)

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
        erro="Não foi possível conectar ao storage"
        return False

    # Verifica se pasta raiz do tableau existe
    pasta_raiz_tableau = montar_caminho(ponto_montagem,
                                   Gpasta_raiz_tableau)

    if not os.path.exists(pasta_raiz_tableau):
        print_log("ERRO: Pasta raiz do tableau não foi encontrada: ", pasta_raiz_tableau)
        print_log("Não é possível criar pasta para a tarefa.")
        print_log("Siga o roteiro de instalação do storage conforme definido na Wiki do SAPI")


    # Pasta para a tarefa
    # kkk
    pasta_tableau = montar_caminho(ponto_montagem,
                                   Gpasta_raiz_tableau,
                                   tarefa["dados_item"]["material_simples"])

    # Verifica se pasta já existe
    if os.path.exists(pasta_tableau):
        print("AVISO: Pasta já existe para tarefa que está em situação de criação de pasta")
        print("Existe alguma inconsistência")
    else:
        # Cria pasta de destino
        try:
            print_log("Criando pasta", pasta_tableau)
            os.makedirs(pasta_tableau)
            print_log("Pasta criada com sucesso")
        except Exception as e:
            erro = "Não foi possível criar pasta: " + str(e)
            # Pode ter alguma condição temporária impedindo. Continuar tentando.
            return False


    # Se pasta de destino existe,
    # Atualiza a situação de tarefa para GAguardandoPCF

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



# ------------------------------------------------------------------------------------------------------------------
# Execução de tarefa
# ------------------------------------------------------------------------------------------------------------------

# Executa criação de pasta para armazenamento de imagem
def ciclo_criar_pasta_imagem():

    return executar_nova_tarefa()




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
    main()

