# -*- coding: utf-8 -*-
#
# ===== PYTHON 3 ======
#
# ======================================================================================================================
# SAPI - Sistema de Apoio a Procedimentos de Informática
#
# Componente: sapi_iped
# Objetivo: Agente para execução de IPED em dados do storage
# Funcionalidades:
#  - Conexão com o servidor SAPI para obter lista de tarefas de iped a serem executadas.
#  - Criação de pasta para armazenamento da extração no storage
#  - Execução de IPED
#  - Cálculo de hash final
#  - Atualização do servidor da situação da tarefa
# Histórico:
#  - v1.0 : Inicial
#  - v1.5 : Tratamento para versão de IPED desatualizado. Neste caso, encerra programa
#           para permitir que entre em execução o programa de atualização
#           O programa também é encerrado sempre quando não existe nenhuma tarefa a ser efetuada,
#           ou quando ocorrem erros não previstos,
#           visando aproveitar este intervalo atualizar a versão, deixando o programa mais tolerante a falhas.
#  - v1.8 : Exclusão de tarefa de iped, compatibilização com sapilib0.8 (tolerância a falha de comunicação)
#  - v1.9 : Nova versão do IPED (3.14.2), com algumas mudanças estruturais
#  - V2.0: Versão para uso em múltiplas unidades: controle de unidade, auto-update e outras mudanças estruturais
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

# Wiki
Gwiki_sapi = "http://10.41.84.5/wiki/index.php/SAPI_Manual_de_instalação_e_configuração"


# Constantes relacionadas com utilização de storage
# -----------------------------------------------------------------------
def CONST_storage_unico():
    return "Único"


def CONST_storage_preferencial():
    return "Preferencial"


def CONST_storage_todos():
    return "Todos"


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
Gprograma = "sapi_iped"
Gversao = "2.0.3"

# Controle de tempos/pausas
GtempoEntreAtualizacoesStatus = 180
GdormirSemServico = 60
GmodoInstantaneo = False
# GmodoInstantaneo = True


Gcaminho_pid = "sapi_iped_pid.txt"

# Configuracao
Gconfiguracao = dict()
Gunidade = None
Gunidade_sigla = None
Giped_profiles_habilitados = None

# IPED
GnomeProgramaInterface = "IPED-SearchApp.exe"

# Execução de tarefa
Gcodigo_tarefa_executando = None
Glabel_processo_executando = None

# Exclusão de tarefa
Gcodigo_tarefa_excluindo = None
Glabel_processo_excluindo = None

# Dados resultantes, para atualização da tarefa
Gtamanho_destino_bytes = None

# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi.py, para evitar dependência
from sapilib_2_0 import *


# **********************************************************************
# PRODUCAO
# **********************************************************************


# ======================================================================
# Funções auxiliares
# ======================================================================


# Faz um pausa por alguns segundos
# Dependendo de parâmetro, ignora a pausa
def dormir(tempo, rotulo=None):
    texto = "Dormindo por " + str(tempo) + " segundos"
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
    global Gunidade
    global Gunidade_sigla
    global Giped_profiles_habilitados

    # Lista de ipeds disponíveis para execução
    lista_ipeds_ok = list()

    try:
        # Efetua inicialização
        # Neste ponto, se a versão do sapi_iped estiver desatualizada será gerado uma exceção
        print_log("Efetuando inicialização")
        sapisrv_inicializar(Gprograma, Gversao,
                            auto_atualizar=True, )  # Outros parâmetros: nome_agente='xxxx', ambiente='desenv'

        # Obtendo arquivo de configuração
        print_log("Obtendo configuração")
        Gconfiguracao = sapisrv_obter_configuracao_agente(Gprograma)
        if (Gconfiguracao is not None):
            print_log(Gconfiguracao)
        else:
            erro = "Agente não pode ser executado, pois não possui configuração registrada ou habilitada. Para configurar e registrar agente, rode sapi_iped.py novamente com a opção --config (exemplo: python sapi_iped.py --config). Se o agente foi desabilitado, verifique no SAPI Admin (SETEC3)"
            print_log(erro)
            sapisrv_reportar_erro(erro)
            return False

    except SapiExceptionVersaoDesatualizada:
        # Se versão do sapi_iped está desatualizada, irá tentar se auto atualizar
        erro = "AVISO: sapi_iped desatualizado. Encerrando programa para verificar se auto-update resolve. Se não resolver, consulte a configuração, e verifique se os arquivos no storage de deployment estão atualizados"
        print_log(erro)
        sapisrv_reportar_erro(erro)
        # Ao retornar False, o chamador entenderá que tem que encerrar a execução
        return False

    except SapiExceptionProgramaDesautorizado:
        # Programa com versão incorreta
        # Auto-update provavelmente irá resolver
        erro = "AVISO: Programa sem acesso autorizado (ver mensagens detalhadas em sistema/log). Contate o desenvolvedor."
        print_log(erro)
        sapisrv_reportar_erro(erro)
        # Ao retornar False, o chamador entenderá que tem que encerrar a execução
        return False

    except SapiExceptionFalhaComunicacao:
        # Falha de comunicação
        erro = "Comunição com servidor falhou. Vamos encerrar e aguardar atualização, pois pode ser algum defeito no cliente"
        print_log(erro)
        # Ao retornar False, o chamador entenderá que tem que encerrar a execução
        return False

    except SapiExceptionGeral as e:
        # Algo inesperado
        erro = "Houve alguma falha incomum sem tratamento definido. Verifique o log na pasta sistema/log para mais detalhes. Erro detectado: " + str(
            e)
        print_log(erro)
        sapisrv_reportar_erro(erro)
        # Ao retornar False, o chamador entenderá que tem que encerrar a execução
        return False

    except SapiExceptionProgramaFoiAtualizado as e:
        # Algo inesperado
        aviso = "Versão desatualizada de sapi_iped foi atualizada automaticamente: " + str(e)
        print_log(aviso)
        sapisrv_reportar_aviso(aviso)
        # Ao retornar False, o chamador entenderá que tem que encerrar a execução
        return False

    except BaseException as e:
        # Para outras exceçõs, irá ficar tentanto eternamente
        # print_log("[168]: Exceção sem tratamento específico. Avaliar se deve ser tratada: ", str(e))
        # Colocar isto aqui em uma função....
        # Talvez já jogando no log também...
        # exc_type, exc_value, exc_traceback = sys.exc_info()
        # traceback.print_exception(exc_type, exc_value, exc_traceback,
        #                          limit=2, file=sys.stdout)
        trc_string = traceback.format_exc()
        print_log("[168]: Exceção abaixo sem tratamento específico. Avaliar se deve ser tratada")
        print_log(trc_string)
        # Ao retornar False, o chamador entenderá que tem que atualizar o sapi_iped, e encerrará a execução
        sapisrv_reportar_erro(trc_string)
        return False

    # Deprecated
    # A partir da versão 2.0, a validação do ambiente é efetuado durante
    # a configuração da máquina --config
    # -----------------------------------------------------
    # # Verifica se máquina corresponde à configuração recebida, ou seja, se todos os programas de IPED
    # # que deveriam estar instalados realmente estão instalados
    # for t in Gconfiguracao["tipo_tarefa"]:
    #     tipo = Gconfiguracao["tipo_tarefa"][t]
    #     pasta_programa = tipo["pasta_programa"]
    #     if os.path.exists(pasta_programa):
    #         #print_log("Pasta de iped ", pasta_programa, " localizada")
    #         lista_ipeds_ok.append(t)
    #     else:
    #         erro = "Não foi localizada pasta de iped: " + str(pasta_programa) + "  Verifique se os arquivos do servidor de deployment estão ok (ver manual de instalação do SAPI no WIKI do SETEC3)"
    #         sapisrv_reportar_erro(erro)
    #
    # if len(lista_ipeds_ok) == 0:
    #     # Como não achou IPED, provavelmente está configurado no servidor
    #     # para que seja utilizado uma nova versão
    #     # Tenta atualizar sapi_iped para sanar o problema
    #     tentar_atualizar_sapi_iped=True
    #     erro = "Nenhum IPED (na versão correta) encontrado nesta máquina. Possivel problema de deployment. Verifique troubleshooting do SAPI no WIKI do SETEC3"
    #     sapisrv_reportar_erro(erro)
    #     # Ao retornar False, o chamador entenderá que tem que atualizar o sapi_iped, e encerrará a execução
    #     return False


    # Armazena algumas configurações que serão utilizadas com mais frequencia em globais,
    # para evitar a passagem de parâmetros excessiva
    Gunidade = Gconfiguracao['unidade']
    Gunidade_sigla = Gconfiguracao['unidade_sigla']

    Giped_profiles_habilitados = Gconfiguracao["iped_profiles_habilitados"]

    if (Giped_profiles_habilitados) == 0:
        erro = "Nenhum tipo de tarefa definido para IPED. Verifique lista de profiles de IPED configurados."
        sapisrv_reportar_erro(erro)
        # Ao retornar False, o chamador entenderá que tem que atualizar o sapi_iped, e encerrará a execução
        return False

    '''
    # Deprecated: Agora vem já vem pronto do servidor
    # Os dados técnicos da configuração são recebidos em um subitem denonimado 'configuracao'
    # Converte Processa pagina resultante em formato JSON
    try:
        # Converte de string para json
        cfg = json.loads(Gconfiguracao["configuracao"])
    except BaseException as e:
        print_tela_log("- Configuração recebida é inválida (não é json)")
        print_tela_log(Gconfiguracao["configuracao"])
        return False
    # Para facilitar, copia os elementos para o nível de cima
    # Isto facilita a codificacao
    # Ao invés de     : Gconfiguracao["configuracao"][k]
    # podemos escrever: Gconfiguracao[k]
    for k in cfg:
        Gconfiguracao[k]=cfg[k]
    # Para deixar mais clean e evitar confusão,
    # exclui o texto de configuracao
    del Gconfiguracao["configuracao"]
    '''

    # Tudo certo
    return True


# Tenta obter uma tarefa com tipo contido em lista_tipo, para o storage (se for indicado)
def solicita_tarefas(lista_tipos, storage=None):
    for tipo in lista_tipos:

        # Por convenção, o SAPI WEB adiciona o prefixo IPED- nas tarefas do tipo iped
        # Além disso, o tipo é sempre lowercase
        tipo_ajustado = "IPED-" + tipo
        tipo_ajustado = tipo_ajustado.lower()

        # Registra em log
        log = "Solicitando tarefa da unidade=[" + Gunidade_sigla + "]" + \
              " com tipo=[" + tipo_ajustado + "]"
        if storage is not None:
            log += ", storage=[" + storage + "]"
        else:
            log += " para qualquer storage"
        print_log(log)

        # Requisita tarefa
        (disponivel, tarefa) = sapisrv_obter_iniciar_tarefa(tipo_ajustado, unidade=Gunidade, storage=storage)
        if disponivel:
            print_log("Tarefa disponível")
            return tarefa

    print_log("Nenhuma tarefa disponível")
    return None


# Tenta obter uma tarefa para exclusão
def solicita_tarefa_exclusao(lista_tipos, storage=None):
    # Exclui qualquer tarefa que inicia por 'iped-'
    # Isto permite que o administrador crie e exclua livremente os perfis sapi_iped
    # Por convenção, o SAPI WEB adiciona o prefixo IPED- nas tarefas do tipo iped
    # Além disso, o tipo é sempre lowercase
    tipo_excluir = "iped-excluir"

    # Registra em log
    log = "Solicitando exclusão de tarefa da unidade=[" + Gunidade_sigla + "]" + \
          " com tipo=[" + tipo_excluir + "]"
    if storage is not None:
        log += " para storage =[" + storage + "]"
    else:
        log += " para qualquer storage"
    print_log(log)

    # Requisita tarefa
    (disponivel, tarefa) = sapisrv_obter_excluir_tarefa(tipo_excluir, Gunidade, storage=storage)
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
    erro = "Abortando [[tarefa:" + codigo_tarefa + "]] em função de ERRO: " + texto_status

    # Registra em log
    print_log(erro)

    # Reportar erro para ficar registrado no servidor
    # Desta forma, é possível analisar os erros diretamente
    sapisrv_reportar_erro(erro)

    # Registra situação de devolução
    sapisrv_troca_situacao_tarefa_loop(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=GAbortou,
        texto_status=texto_status
    )

    # Ok
    print_log("Execução da tarefa abortada")

    return False


# Recupera dados de tarefa do servidor
def recupera_tarefa_do_setec3(codigo_tarefa):
    tarefa = None
    try:
        # Recupera dados atuais da tarefa do servidor,
        (sucesso, msg_erro, tarefa) = sapisrv_chamar_programa(
            "sapisrv_consultar_tarefa.php",
            {'codigo_tarefa': codigo_tarefa}
        )

        # Insucesso. Provavelmente a tarefa não foi encontrada
        if (not sucesso):
            # Sem sucesso
            print_log("[371] Recuperação de dados atualizados do SETEC da tarefa", codigo_tarefa, "FALHOU: ",
                      msg_erro)
            return None

    except BaseException as e:
        print_log("[376] Recuperação de dados atualizados do SETEC da tarefa", codigo_tarefa, "FALHOU: ",
                  str(e))
        return None

    return tarefa


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
    lista_desconsiderar = ['.ufdr', 'UFEDReader.exe']
    print_log("Verifica se na pasta de origem existem arquivos que não devem ser indexados pelo IPED")
    dirs = os.listdir(caminho_origem)
    for file in dirs:
        for desconsiderar in lista_desconsiderar:
            if desconsiderar in file:
                lista_mover.append(file)

    if len(lista_mover) == 0:
        print_log("Não existe nenhum arquivo a ser movido antes de rodar o IPED")
        return (True, "", [])

    # ------------------------------------------------------------------------------------------------------------------
    # Move arquivos que não devem ser indexados para a pasta do item
    # ------------------------------------------------------------------------------------------------------------------
    lista_movidos = list()
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
        return (False, "[410] exceção durante rename: " + str(e), [])

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
        return (False, "[433] exceção durante rename: " + str(e), [])


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
        erro = "Caminho de origem " + caminho_origem + " não encontrado no storage"
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

            print_log("Excluindo pasta: " + caminho_destino)
            # Limpa pasta de destino
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status="Excluindo pasta de destino: " + caminho_destino
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
    erro_exception = None
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
            args=(codigo_tarefa,
                  caminho_tela_iped,
                  nome_arquivo_log,
                  label_processo,
                  dados_pai_para_filho
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
        erro_exception = str(e)
        deu_erro = True
    except Exception as e:
        # Alguma outra coisa aconteceu...
        erro_exception = str(e)
        deu_erro = True

    # Finaliza processo de acompanhamento do IPED
    print_log("Encerrando processo de acompanhamento de cópia")
    p_acompanhar.terminate()

    # Faz upload da tela de resultado do IPED (mensagens que seriam exibidas na tela)
    conteudo_tela = ""
    # Upload do resultado do IPED
    with open(caminho_tela_iped, "r") as fentrada:
        for linha in fentrada:
            conteudo_tela = conteudo_tela + linha

    armazenar_texto_tarefa(codigo_tarefa, 'Resultado IPED', conteudo_tela)

    # Faz upload do log do IPED
    armazenar_texto_log_iped(codigo_tarefa, caminho_log_iped)

    if deu_erro:
        erro = "Chamada de IPED falhou. Para compreender, analise o arquivo de resultado."
        if erro_exception != "":
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
def background_acompanhar_iped(codigo_tarefa,
                               caminho_tela_iped,
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

    print_log("Processo de acompanhamento de IPED")

    # Fica em loop infinito. Será encerrado pelo pai (com terminate)
    while True:

        if not os.path.isfile(caminho_tela_iped):
            print_log("Arquivo de tela de iped", caminho_tela_iped, "ainda não existe. Aguardando")
            dormir(30)
            continue

        # Le arquivo de resultado (tela) e busca pela última mensagem de situação e projeção
        # Exemplo:
        texto_status = None
        linha = None
        with open(caminho_tela_iped, "r") as fentrada:
            for linha in fentrada:
                # Troca tabulação por espaço
                linha = linha.replace('\t', ' ')
                # Ignora se estiver em branco
                if linha.strip() == "":
                    continue
                # Formato da linha de status na versão 3.12
                # IPED-2017-01-31 17:14:11 [MSG] Processando 29308/39593 (25%) 31GB/h Termino em 0h 5m 33s
                if "[MSG] Processando" in linha:
                    texto_status = linha
                else:
                    # Formato da linha de status na versão 3.14
                    # 2018-09-28 11:12:22	[MSG]	[indexer.process.ProgressConsole]			Processando 28028/54313 (74%) 68GB/h Termino em 0h 0m 37s
                    matchObj = re.match(r'^(.*)\[MSG\].*(Processando .*)$', linha, re.I)
                    if matchObj:
                        texto_status = matchObj.group(1).strip() + " " + matchObj.group(2).strip()

        # Atualiza status
        if texto_status is not None:
            print_log("Atualizando status para tarefa", codigo_tarefa, ":", texto_status)
            sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)
            # Intervalo entre atualizações de status
            dormir(GtempoEntreAtualizacoesStatus, "Dormindo entre atualização de status do IPED")
        else:
            # Como ainda não atualizou o status, vamos dormir por um período menor
            # Assim pega a primeira atualização de status logo que sair
            print_log("Atenção: Não foi encontrado texto de status no arquivo", caminho_tela_iped)
            if linha is not None:
                print_log("Ultima linha = ", linha)
            dormir(30)


# Verifica se existe indicação que iped foi finalizado com sucesso
def verificar_sucesso_iped(caminho_tela_iped):
    # Será lido o arquivo de "tela" do IPED, ou seja, o arquivo que contém as mensagens
    print_log("Analisando arquivo de tela do IPED: [", caminho_tela_iped, "]")

    if not os.path.exists(caminho_tela_iped):
        print_log("Arquivo de resultado de IPED não encontrado")
        return False

    # Processa arquivo de tela
    with open(caminho_tela_iped, "r") as fentrada:
        for linha in fentrada:
            # Sucesso
            indicativo = "IPED finalizado"
            if indicativo in linha:
                print_log("Indicativo de sucesso [", indicativo, " ] encontrado.")
                return True
            # Sucesso (Mensagem em Inglês, a partir da versão 3.12.4)
            indicativo = "IPED finished"
            if indicativo in linha:
                print_log("Indicativo de sucesso [", indicativo, " ] encontrado.")
                return True
            # Erro
            indicativo = 'ERRO!!!'
            if indicativo in linha:
                print_log("Indicativo de erro [", indicativo, "] encontrado.")
                return False
            # Erro (Mensagem em Inglês)
            indicativo = 'ERROR!!!'
            if indicativo in linha:
                print_log("Indicativo de erro [", indicativo, "] encontrado.")
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
        valor_hash = calcula_sha256_arquivo(caminho_arquivo_calcular_hash)
    except Exception as e:
        erro = "Não foi possível calcular hash para " + nome_arquivo_calculo_hash + " => " + str(e)
        # Não deveria ocorrer este erro??? Abortar e analisar
        return (False, erro)

    # Extrai a subpasta de destino
    partes = caminho_destino.split("/")
    subpasta_destino = partes[len(partes) - 1]
    if subpasta_destino == "":
        subpasta_destino = partes[len(partes) - 2]

    # Armazena dados de hash
    h = dict()
    h["sapiHashDescricao"] = "Hash do arquivo " + subpasta_destino + "/" + nome_arquivo_calculo_hash
    h["sapiHashValor"] = valor_hash
    h["sapiHashAlgoritmo"] = algoritmo_hash
    lista_hash = [h]

    armazenar_dados_laudo('sapiHashes', lista_hash)

    print_log("Hash calculado para resultado do IPED: ", valor_hash, "(", algoritmo_hash, ")")

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
    ponto_montagem = conectar_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        erro = "Não foi possível conectar no storage"
        return (False, erro)

    # ------------------------------------------------------------------------------------------------------------------
    # Pastas relacionadas
    # ------------------------------------------------------------------------------------------------------------------
    # A estrutura da pasta multicase é similar à estrutura de um item, com as seguintes diferenças:
    # - Não possui dados (indices, thumbs), pois isto será buscado de cada um dos itens
    # - Possui um arquivo contendo uma lista de pasta, as quais possuem os dados (indices) propriamente ditos.
    # - Possui pastas com bibliotecas e dados auxiliares utilizados pela interface
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
    #       + pasta diversas....
    #       + index (dados do indice)
    #       + Thumbs (thumbnails gerados)
    #
    # O iped multicase possui a seguinte estrutura:
    # Memorando_xxxx_xx
    #   + multicase
    #     + IPED-SearchApp.exe
    #     + iped-itens.txt
    #     + indexador (similar ao de um item qualquer, mas sem os dados)
    #       + lib
    #       + conf
    #       + pastas diversas, exceto pastas de dados (index, thumbs)
    #
    #
    # A rigor, cada item pode ter uma configuração independente, logo existe um problema conceitual aqui.
    # Mas como todos são rodados pelo sistema, isto não deve dar diferença
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

    caminho_iped_multicase = montar_caminho(caminho_memorando, "multicase")

    # Recupera a lista de pasta das tarefas IPED que foram concluídas com sucesso
    # ---------------------------------------------------------------------------
    codigo_solicitacao_exame_siscrim = tarefa["dados_solicitacao_exame"]["codigo_documento_externo"]
    try:
        (sucesso, msg_erro, tarefas_iped_sucesso) = sapisrv_chamar_programa(
            "sapisrv_obter_tarefas.php",
            {'tipo': 'iped%',
             'codigo_solicitacao_exame_siscrim': codigo_solicitacao_exame_siscrim
             }
        )
    except BaseException as e:
        erro = "Não foi possível recuperar a situação atualizada das tarefas do servidor"
        return (False, erro)

    if not sucesso:
        return (False, msg_erro)

    # Processa tarefas iped,
    # selecionando apenas as que já passaram pela fase do IPED
    # ---------------------------------------------------------------------
    caminhos_tarefas_iped_finalizado = list()
    for t in tarefas_iped_sucesso:
        tarefa_finalizada = t["tarefa"]
        # Problema: O teste >=GIpedFinalizado pode ser um problema no futuro...
        # se algum dia for inserido um código de erro maior que 62...
        # Códigos de erro (abortado, por exemplo) tem que ser pequenos,
        # obrigatoriamente no início do range
        codigo_situacao_tarefa = int(tarefa_finalizada["codigo_situacao_tarefa"])
        if codigo_situacao_tarefa >= GIpedFinalizado:
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
        pasta_iped = montar_caminho(ponto_montagem, caminho_destino)
        if not os.path.exists(pasta_iped):
            erro = "[756] Não foi encontrada pasta de IPED de tarefa concluída" + pasta_iped
            return (False, erro)

        # Verifica integridade da pasta
        if os.path.exists(montar_caminho(pasta_iped, "indexador", "lib")) \
                and os.path.exists(montar_caminho(pasta_iped, "indexador", "conf")) \
                and os.path.isfile(montar_caminho(pasta_iped, GnomeProgramaInterface)):
            print_log("Pasta", pasta_iped, " está íntegra")
        else:
            erro = "[765] Pasta de IPED danificada: " + pasta_iped
            return (False, erro)

    # A primeira pasta de IPED será utilizada como modelo, para copiar lib e outros componentes
    # para o multicase
    caminho_iped_origem = montar_caminho(ponto_montagem, caminhos_tarefas_iped_finalizado[0])

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

    # ---------------------------------------------------------------------------------------------------
    # Copia arquivos e pastas do item para pasta multicase
    # ---------------------------------------------------------------------------------------------------

    # A lista abaixo contém as pasta necessárias (talvez algumas sejam até mesmo superfluas)
    # na versão 3.14.2.
    # Para versões novas, é possível que sejam necessárias novas pastas.
    # Este método de copiar apenas as pastas necessárias (ao invés de copiar tudo, ou copiar todas
    # exceto algumas conhecidas) é menos versátil (requer mais manutenção, se forem incluídas novas pastas)
    # mas é mais robusto, evitando geração de resultados imprevisíveis em caso de novas versões que possuam
    # estruturas de pastas incompatíveis.
    # ---------------------------------------------------------------------------------------------------
    lista_pastas_copiar = list()
    lista_pastas_copiar.append("conf")
    lista_pastas_copiar.append("data")
    lista_pastas_copiar.append("htm")
    lista_pastas_copiar.append("htmlreport")
    lista_pastas_copiar.append("lib")  # Contém os programas java e bibliotecas utilizados na pesquisa
    lista_pastas_copiar.append("tools")
    lista_pastas_copiar.append("view")
    # Não copia pasta de dados: index, thumbs

    for pasta_copiar in lista_pastas_copiar:
        caminho_item_origem = montar_caminho(caminho_iped_origem, "indexador", pasta_copiar)
        caminho_multicase = montar_caminho(caminho_iped_multicase, "indexador", pasta_copiar)

        # Se pasta não existe, cria pasta, copiando da pasta de processamento de IPED do item
        if not os.path.exists(caminho_multicase):
            try:
                # Cria pasta de lib
                print_log("Copiando " + caminho_iped_origem +
                          " para pasta multicase " + caminho_multicase)
                shutil.copytree(caminho_item_origem, caminho_multicase)
            except Exception as e:
                erro = "Não foi possível copiar pasta para multicase: " + str(e)
                return (False, erro)

        # Confere se pasta existe
        if os.path.exists(caminho_multicase):
            print_log("Encontrada pasta " + caminho_multicase + ": ok")
        else:
            erro = "[823] Situação inesperada: Pasta [" + caminho_multicase + "] foi copiada MAS NÃO existe"
            return (False, erro)

    # A lista abaixo contém os arquivos da pasta indexador que tem que ser copiado para a pasta multicase
    lista_arquivos_copiar = list()
    lista_arquivos_copiar.append("IPEDConfig.txt")
    lista_arquivos_copiar.append("LocalConfig.txt")

    for arquivo_copiar in lista_arquivos_copiar:
        caminho_de = montar_caminho(caminho_iped_origem, "indexador", arquivo_copiar)
        caminho_para = montar_caminho(caminho_iped_multicase, "indexador", arquivo_copiar)

        try:
            print_log("Copiando arquivo" + caminho_de + "para" + caminho_para)
            shutil.copy(caminho_de, caminho_para)
        except Exception as e:
            erro = "Não foi possível copiar " + caminho_de + " para " + caminho_para + " : " + str(e)
            return (False, erro)

        # Confere se copiou ok
        if os.path.isfile(caminho_para):
            print_log("Encontrado arquivo", caminho_para)
        else:
            erro = "[867] Situação inesperada: Arquivo " + caminho_para + " não existe"
            return (False, erro)

    # ------------------------------------------------------------------------------------------------------------------
    # Copia IPED-Search-App.exe para pasta do multicase
    # ------------------------------------------------------------------------------------------------------------------
    caminho_de = montar_caminho(caminho_iped_origem, GnomeProgramaInterface)
    caminho_para = montar_caminho(caminho_iped_multicase, GnomeProgramaInterface)
    try:
        print_log("Copiando arquivo" + caminho_de + "para" + caminho_para)
        shutil.copy(caminho_de, caminho_para)
    except Exception as e:
        erro = "Não foi possível copiar" + caminho_de + "para" + caminho_para + ": " + str(e)
        return (False, erro)

    # Confere se copiou ok
    if os.path.isfile(caminho_para):
        print_log("Encontrado arquivo", caminho_para)
    else:
        erro = "[867] Situação inesperada: Arquivo " + caminho_para + " não existe"
        return (False, erro)

    # DEPRECATED
    # Substituido pelo código generalizado acima, que copia lib, conf e outras pastas
    # # ------------------------------------------------------------------------------------------------------------------
    # # Pasta LIB => Esta pasta contém os programas java e bibliotecas utilizados na pesquisa
    # # Efetua a cópia da pasta lib de um item para a pasta do multicase caso isto não tenha sido feito anteriormente
    # # ------------------------------------------------------------------------------------------------------------------
    # caminho_lib_origem      =montar_caminho(caminho_iped_origem   , "indexador", "lib")
    # caminho_lib_multicase   =montar_caminho(caminho_iped_multicase, "indexador", "lib")
    #
    # # Se pasta lib não existe, cria pasta, copiando da pasta de processamento de IPED do item
    # if not os.path.exists(caminho_lib_multicase):
    #     try:
    #         # Cria pasta de lib
    #         print_log("Copiando lib " + caminho_iped_origem +
    #                   " para lib da pasta multicase " + caminho_lib_multicase)
    #         shutil.copytree(caminho_lib_origem, caminho_lib_multicase)
    #     except Exception as e:
    #         erro = "Não foi possível copiar lib para multicase: " + str(e)
    #         return (False, erro)
    #
    # # Confere se lib existe
    # if os.path.exists(caminho_lib_multicase):
    #     print_log("Encontrada pasta " + caminho_lib_multicase + ": ok")
    # else:
    #     erro = "[823] Situação inesperada: Pasta [" + caminho_lib_multicase + "] foi copiada MAS NÃO existe"
    #     return (False, erro)
    #
    # # ------------------------------------------------------------------------------------------------------------------
    # # Pasta CONF => Copia a pasta conf do item para a pasta do iped multicase, caso isto ainda não tenha sido feito
    # # A rigor, cada item pode ter uma configuração independente, logo existe um problema conceitual aqui.
    # # Mas como todos são rodados pelo sistema, isto não deve dar diferença
    # # ------------------------------------------------------------------------------------------------------------------
    # caminho_conf_origem     =montar_caminho(caminho_iped_origem,      "indexador", "conf")
    # caminho_conf_multicase  =montar_caminho(caminho_iped_multicase,   "indexador", "conf")
    #
    # # Se pasta conf não existe, cria pasta, copiando da pasta de processamento de IPED do item
    # if not os.path.exists(caminho_conf_multicase):
    #     try:
    #         print_log("Copiando conf do item" + caminho_conf_origem +
    #                   " para conf da pasta multicase" + caminho_conf_multicase)
    #         shutil.copytree(caminho_conf_origem, caminho_conf_multicase)
    #     except Exception as e:
    #         erro = "Não foi possível copiar para multicase: " + str(e)
    #         return (False, erro)
    #
    # # Confere se conf existe
    # if os.path.exists(caminho_conf_multicase):
    #     print_log("Encontrada pasta", caminho_conf_multicase, ": ok")
    # else:
    #     erro = "[848] Situação inesperada: Pasta" + caminho_conf_multicase + "não existe"
    #     return (False, erro)


    # ------------------------------------------------------------------------------------------------------------------
    # Gera arquivo contendo as listas de pasta dos itens, para ser utilizado na opção multicase
    # Este passo sempre é executado e o arquivo é refeito, refletindo o conteúdo completo da pasta
    # ------------------------------------------------------------------------------------------------------------------
    arquivo_pastas = "iped-itens.txt"
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
        # pasta="..\\" +p.replace(caminho_memorando,'')
        inicio_pasta_item = p.find("\\item")
        if inicio_pasta_item == -1:
            inicio_pasta_item = p.find("/item")
            if inicio_pasta_item == -1:
                erro = "[945] Não foi encontrada subpasta do item em " + p
                return (False, erro)

        # print(inicio_pasta_item)
        p_comecando_item = p[inicio_pasta_item:]
        # print(p_comecando_item)
        pasta = ".." + p_comecando_item
        # print(pasta)

        # zzz
        # print_log("pasta para ajustar", p)
        # print_log("Caminho memorando: ", caminho_memorando)
        print_log("Multicase: Incluido em ", arquivo_pastas, "a pasta", pasta)
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
    conteudo_bat = """
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
REM java -jar indexador/lib/iped-search-app.jar -multicases iped-itens.txt
REM pause
"""

    # Troca o nome do programa do executavel
    conteudo_bat = conteudo_bat.replace("xxx_programa_interface.exe", GnomeProgramaInterface)

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

    msg_erro = None
    try:
        carac_destino = obter_caracteristicas_pasta(caminho_destino)
        Gtamanho_destino_bytes = carac_destino["tamanho_total"]

        print_log("Tamanho total da pasta resultante do processamento do IPED: ", Gtamanho_destino_bytes)
        sucesso = True

    except OSError as e:
        msg_erro = "[1180] Falhou determinação de tamanho: " + str(e)
        sucesso = False
    except BaseException as e:
        msg_erro = "[1183] Falhou determinação de tamanho: " + str(e)
        sucesso = False

    return (sucesso, msg_erro)


# Recupera dados relevantes do log do IPED
def recupera_dados_laudo(codigo_tarefa, caminho_log_iped):
    # Será lido o arquivo de log
    print_log("Recuperando dados para laudo do log do IPED: ", caminho_log_iped)
    sapisrv_atualizar_status_tarefa_informativo(
        codigo_tarefa=codigo_tarefa,
        texto_status="Recuperando dados para laudo do log do IPED"
    )

    if not os.path.exists(caminho_log_iped):
        erro = "Arquivo de log do IPED não encontrado"
        return (False, erro)

    # Processa arquivo
    versao = None
    total_itens = None
    with open(caminho_log_iped, "r") as fentrada:
        for linha in fentrada:
            # Troca tabulação por espaço
            linha = linha.replace('\t', ' ')

            # Versão do IPED
            # 2017-01-31 17:12:11	[INFO]	Indexador e Processador de Evidências Digitais 3.11
            # 2018-07-09 17:33:28	[INFO]	[gpinf.indexer.IndexFiles]			Indexador e Processador de Evidências Digitais 3.14.2
            if "Indexador e Processador de Evidências Digitais" in linha:
                (inicio, numero_versao) = linha.split('Digitais')
                numero_versao = numero_versao.strip()
                if not numero_versao == "":
                    versao = "IPED " + numero_versao

            # Quantidade de itens processados
            # 2017-01-31 17:21:19	[INFO]	Total processado: 153329 itens em 542 segundos (4084 MB)
            if "[INFO] Total processado:" in linha:
                match = re.search(r'processado: (\d+) itens', linha)
                if match:
                    total_itens = (match.group(1))

            # A partir de 3.14.2 começou a exibir textos em inglês
            # 2018-07-09 17:33:43	[INFO]	[indexer.process.Statistics]			Total processed: 15 items in 14 seconds (4 MB)
            if "Total processed:" in linha:
                match = re.search(r'processed: (\d+) items', linha)
                if match:
                    total_itens = (match.group(1))

                    # Todo: Como calcular a quantidade de itens com erro (que não foram processados...)

    if versao is None:
        erro = "Não foi possível recuperar versão do IPED"
        return (False, erro)

    if total_itens is None:
        erro = "Não foi possível recuperar quantidade total de itens processados"
        return (False, erro)

    # Armazena dados para laudo
    armazenar_dados_laudo('sapiSoftwareVersao', versao)
    armazenar_dados_laudo('sapiItensProcessados', total_itens)

    # Todo: 'sapiItensProcessados':
    # Todo: 'sapiItensComErro':


    # Ok, finalizado com sucesso
    return (True, "")


# ------------------------------------------------------------------------------------------------------------------
# Conexão com storage
# ------------------------------------------------------------------------------------------------------------------

# Efetua conexão no storage, dando tratamento em caso de problemas
# Se tudo der certo, retorna o ponto de montagem
def conectar_storage_ok(dados_storage):
    # Confirma que tem acesso ao storage escolhido
    storage_id = dados_storage['storage_id']
    print_log("Verificando conexão com storage", storage_id)

    (sucesso, ponto_montagem, erro) = acesso_storage_windows(
        dados_storage,
        utilizar_ip=True,
        tipo_conexao='atualizacao')

    if not sucesso:
        erro = "Acesso ao storage " + storage_id + " falhou. Verifique se servidor está acessível (rede) e disponível."
        # Talvez seja um problema de rede (trasiente)
        sapisrv_reportar_erro(erro)
        print_log("Problema insolúvel neste momento, mas possivelmente transiente")
        return False

    print_log("Storage", storage_id, "acessível")

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
    tarefa = recupera_tarefa_do_setec3(Gcodigo_tarefa_excluindo)

    excluindo = False
    excluindo_setec3 = False
    if tarefa is None:
        print_log("Não foi possível recuperar situação de tarefa do SETEC3. Presumindo que foi excluída com sucesso")
    else:
        codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
        if tarefa['excluida'] == 't':
            print_log("Segundo SETEC3, exclusão da tarefa foi finalizada (tarefa foi excluída)")
            excluindo = False
            excluindo_setec3 = False
        elif codigo_situacao_tarefa == GEmExclusao:
            print_log("Tarefa ainda está sendo excluída de acordo com SETEC3")
            excluindo = True
            excluindo_setec3 = True
        else:
            print_log("Segundo SETEC3 tarefa não está mais sendo excluída. codigo_situacao_tarefa=",
                      codigo_situacao_tarefa)

    # Verifica se o subprocesso de execução da tarefa ainda está rodando
    nome_processo = "excluir:" + str(Gcodigo_tarefa_excluindo)
    processo = Gpfilhos.get(nome_processo, None)
    if processo is not None and processo.is_alive():
        # Ok, tarefa está sendo executada
        print_log("Subprocesso de exclusão da tarefa ainda está rodando")
        excluindo = True
    else:
        print_log("Subprocesso de exclusão da tarefa NÃO ESTÁ mais rodando")
        if excluindo_setec3:
            print_log(
                "Como no setec3 ainda está em exclusão, isto provavelmente indica que o subprocesso de exclusão abortou")
            print_log(
                "Desta forma, a tentativa de exclusão será abandonada. Isto gerará uma nova tentativa de exclusão")
            excluindo = False

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

    # Solicita tarefa para excluir,
    # dependendo da configuração de storage do agente
    outros_storages = True
    tarefa = None
    unidade = Gconfiguracao["unidade"]
    if Gconfiguracao["storage_escopo"] == CONST_storage_unico():
        print_log("Este agente trabalha apenas com storage:", Gconfiguracao["storage_selecionado"])
        tarefa = solicita_tarefa_exclusao(
            Giped_profiles_habilitados,
            Gconfiguracao["storage_selecionado"])
        outros_storages = False
    elif Gconfiguracao["storage_escopo"] == CONST_storage_preferencial():
        print_log("Este agente trabalha com storage preferencial:", Gconfiguracao["storage_selecionado"])
        tarefa = solicita_tarefa_exclusao(
            Giped_profiles_habilitados,
            Gconfiguracao["storage_selecionado"])
        outros_storages = True
    else:
        print_log("Este agente trabalha com QUALQUER storage")
        outros_storages = True

    # Se ainda não tem tarefa, e agente trabalha com outros storages, solicita para qualquer storage
    if tarefa is None and outros_storages:
        # Solicita tarefa para qualquer storage
        tarefa = solicita_tarefa_exclusao(Giped_profiles_habilitados)

    # Se não tem nenhuma tarefa para disponível, não tem o que fazer
    if tarefa is None:
        print_log("Nenhuma tarefa para exclusão na fila. Nada a ser excluído por enquanto.")
        return False

    # Ok, temos tarefa para ser excluída
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]
    print_log("Tarefa a ser excluída: ", codigo_tarefa)

    # Montar storage
    # ------------------------------------------------------------------
    ponto_montagem = conectar_storage_ok(tarefa["dados_storage"])
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
    ponto_montagem = conectar_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return False

    # Executa sequencia de tarefas para exclusão da tarefa
    # -----------------------------------------------------
    (sucesso, msg_erro) = executa_sequencia_exclusao_tarefa(
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
        sapisrv_reportar_erro(erro)

        # Registra situação de devolução
        texto_status = texto("ERRO na exclusão:",
                             msg_erro,
                             " Verifique a mensagem de erro. ",
                             " Dica: Assegure-se que a pasta a ser excluída não está sendo acessada,"
                             " por exemplo: IPED (interface gráfica do usuário) em execução,"
                             " ou algum arquivo da pasta esteja aberto."
                             " Analise e corrija este problemas de depois tente EXCLUIR NOVAMENTE a tarefa"
                             )
        sapisrv_troca_situacao_tarefa_loop(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=GAbortou,
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
    erro_excecao = False

    try:

        # 1) Ajustar status para indicar que exclusão foi iniciada
        # =======================================================
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="Exclusão de tarefa iniciada."
        )

        # 2) Exclui pasta da tarefa
        # ====================================
        (sucesso, msg_erro) = exclui_pasta_tarefa(codigo_tarefa, caminho_destino)
        if not sucesso:
            return (False, msg_erro)

        # 3) Ajusta ambiente Multicase (remove pasta da tarefa da lista de evidências)
        # ============================================================================
        (sucesso, msg_erro) = ajusta_multicase(tarefa, codigo_tarefa, caminho_destino)
        if not sucesso:
            return (False, msg_erro)

        # 4) Exclui tarefa no SETEC3
        # =========================
        sapisrv_excluir_tarefa_loop(codigo_tarefa=codigo_tarefa)

    except BaseException as e:
        # Pega qualquer exceção não tratada aqui, para jogar no log
        trc_string = traceback.format_exc()
        erro_excecao = True

    if erro_excecao:
        print_log(trc_string)
        # Tenta registrar no log o erro ocorrido
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="[1169] ERRO em exclusão de tarefa: " + trc_string
        )
        sapisrv_reportar_erro("Tarefa " + str(Gcodigo_tarefa_executando) + "Erro => " + trc_string)
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
            texto_status="Excluindo pasta: " + caminho_destino
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
# Execução de tarefa
# ------------------------------------------------------------------------------------------------------------------

# Executa uma tarefa de iped que esteja ao alcance do agente
# Retorna verdadeiro se executou uma tarefa e falso se não executou nada
def ciclo_executar():
    # Se já tem tarefa rodando IPED,
    # Verifica a situação da tarefa, comandos, etc
    if Gcodigo_tarefa_executando is not None:
        return tarefa_executando()
    else:
        return executar_nova_tarefa()


# Retorna verdadeiro se tarefa ainda está executando
def tarefa_executando():
    global Gcodigo_tarefa_executando

    print_log("Verificando se tarefa", Gcodigo_tarefa_executando, "ainda está executando")
    tarefa = recupera_tarefa_do_setec3(Gcodigo_tarefa_executando)

    executando = False
    executando_setec3 = False
    if tarefa is None:
        print_log("Não foi possível recuperar situação de tarefa do SETEC3.")
        # Como não conseguimos confirmação do servidor, vamos presumir que tarefa ainda está executando
        executando = True
    else:
        if tarefa["executando"] == 't':
            print_log("Tarefa ainda está executando de acordo com SETEC3")
            executando = True
            executando_setec3 = True
        else:
            print_log("Segundo SETEC3 tarefa não está mais executando")
            # Se resultado não foi de sucesso, interrompe execução do sapi_iped
            # para permitir que seja feito um update,
            # o qual pode permitir que a condição de falha seja superada
            codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
            if codigo_situacao_tarefa != GFinalizadoComSucesso:
                print_log("Tarefa não foi concluída com sucesso (ex: abortada, excluída pelo usuário, reiniciada)")
                print_log(
                    "Encerrando programa (e todos os filhos), para reiniciar procedimento (inclusive update) para sanar estas diversas situações")
                finalizar_programa()

    # Verifica se o subprocesso de execução da tarefa ainda está rodando
    nome_processo = "executar:" + str(Gcodigo_tarefa_executando)
    processo = Gpfilhos.get(nome_processo, None)
    if processo is not None and processo.is_alive():
        # Ok, tarefa está sendo executada
        print_log("Subprocesso de execução da tarefa ainda está rodando")
        executando = True
    else:
        print_log("Subprocesso de execução da tarefa NÃO ESTÁ mais rodando")
        if executando_setec3:
            print_log(
                "Como no setec3 ainda está em execução, isto provavelmente indica que o subprocesso de execução abortou")
            print_log("Desta forma, a tarefa será abortada e o programa encerrado, visando tentar sanar o problema")
            # Aborta tarefa
            abortar(Gcodigo_tarefa_executando, "Processo de execução abortou. Verifique log do servidor")
            print_log("Tarefa foi abortada e sapi_iped finalizado")
            finalizar_programa()

    # Retorna se alguma condição acima indica que tarefa está executando
    if executando:
        return True

    # Se não está mais executando
    Gcodigo_tarefa_executando = None
    return False


# Monta linha de comando para execução do IPED
def montar_comando_iped(iped_comando,
                        caminho_origem,
                        caminho_destino,
                        profile_iped):
    # Prepara parâmetros para execução das subatarefas do IPED
    # ========================================================

    # Adiciona o perfil do IPED
    comando = iped_comando + " -profile " + profile_iped

    # Adiciona a pasta de origem
    comando = comando + " -d " + caminho_origem

    # Adiciona a pasta de destino
    comando = comando + " -o " + caminho_destino

    # Sem interface gráfica
    comando = comando + " --nogui "

    # Portable
    # Isto aqui é essencial. Caso contrário o multicase não funciona...
    comando = comando + " --portable "

    # Define arquivo para log
    caminho_log_iped = montar_caminho(caminho_destino, "iped.log")
    comando = comando + " -log " + caminho_log_iped

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

    return (comando, caminho_tela_iped, caminho_log_iped)


# Retorna verdadeiro se uma nova tarefa foi iniciada
def executar_nova_tarefa():
    global Gcodigo_tarefa_executando
    global Glabel_processo_executando

    print_log("Solicitando tarefa de iped")

    # var_dump(Gconfiguracao)

    # Solicita tarefa, dependendo da configuração de storage do agente
    outros_storages = True
    tarefa = None
    if Gconfiguracao["storage_escopo"] == CONST_storage_unico():
        print_log("Este agente trabalha apenas com storage:", Gconfiguracao["storage_selecionado"])
        tarefa = solicita_tarefas(Giped_profiles_habilitados, Gconfiguracao["storage_selecionado"])
        outros_storages = False
    elif Gconfiguracao["storage_escopo"] == CONST_storage_preferencial():
        print_log("Este agente trabalha com storage preferencial:", Gconfiguracao["storage_selecionado"])
        tarefa = solicita_tarefas(Giped_profiles_habilitados, Gconfiguracao["storage_selecionado"])
        outros_storages = True
    else:
        print_log("Este agente trabalha com QUALQUER storage")
        outros_storages = True

    # Se ainda não tem tarefa, e agente trabalha com outros storages, solicita para qualquer storage
    if tarefa is None and outros_storages:
        # Solicita tarefa para qualquer storage
        tarefa = solicita_tarefas(Giped_profiles_habilitados)

    # Se não tem nenhuma tarefa disponível, não tem o que fazer
    if tarefa is None:
        print_log("Nenhuma tarefa de IPED fornecida pelo servidor. Nada a ser executado por enquanto.")
        return False

    # Ok, temos trabalho a fazer
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]
    inicializar_dados_laudo()  # Inicia armazenamento de dados para laudo

    # Verifica se é uma retomada de tarefa, ou seja,
    # uma tarefa que foi iniciada mas que não foi concluída
    retomada = False
    if tarefa["executando"] == 't':
        retomada = True

    # Indicativo de início
    if retomada:
        print_log("Retomando tarefa interrompida: ", codigo_tarefa)
    else:
        print_log("Iniciando tarefa: ", codigo_tarefa)

    # Montar storage
    # ------------------------------------------------------------------
    ponto_montagem = conectar_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        erro = "Não foi possível conectar no storage"
        abortar(codigo_tarefa, erro)
        return False

    # ------------------------------------------------------------------
    # Pastas de origem e destino
    # ------------------------------------------------------------------
    caminho_origem = montar_caminho(ponto_montagem, tarefa["caminho_origem"])
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

    # O tipo da tarefa contem o profile
    # Exemplo: iped-forensics => profile = forensics
    profile_iped = tarefa["tipo"]
    profile_iped = profile_iped.replace("iped-", "")

    # Armazena tipo de profile utilizado
    armazenar_dados_laudo('sapiIpedProfile', profile_iped)

    (comando, caminho_tela_iped, caminho_log_iped) = montar_comando_iped(
        Gconfiguracao["iped_comando"],
        caminho_origem,
        caminho_destino,
        profile_iped)

    #
    # var_dump(comando)
    # die('ponto1953')

    # # Deprecated...tudo isto foi jogado para montar_comando_iped
    # comando = Gconfiguracao["tipo_tarefa"][tipo_iped]["comando"]
    # # Adiciona a pasta de origem e destino
    # comando = comando + " -d " + caminho_origem + " -o " + caminho_destino
    # # Define arquivo para log
    # caminho_log_iped = montar_caminho(caminho_destino, "iped.log")
    # comando = comando + " -log " + caminho_log_iped
    # # Sem interface gráfica
    # comando = comando + " --nogui "
    # # Portable
    # # Isto aqui é essencial. Caso contrário o multicase não funciona...
    # comando = comando + " --portable "
    # # Redireciona saída de tela (normal e erro) para arquivo
    # caminho_tela_iped = montar_caminho(caminho_destino, "iped_tela.txt")
    # comando = comando + " >" + caminho_tela_iped + " 2>&1 "

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
    dados_pai_para_filho = obter_dados_para_processo_filho()
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

    (sucesso, msg_erro) = executa_sequencia_iped(
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
        dados_relevantes['laudo'] = obter_dados_laudo_armazenados()
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
        # sapi_iped, iped, etc
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
    codigo_tarefa = tarefa["codigo_tarefa"]
    erro_excecao = False

    try:

        # 1) Retira da pasta alguns arquivos que não precisam ser indexados (ex: UFDR)
        # ===========================================================================
        # TODO: Isto aqui não está legal...tem que refazer com conceito de pasta
        # temporária (xxx_ignorados)
        # (sucesso, msg_erro, lista_movidos)=mover_arquivos_sem_iped(
        #    caminho_origem,
        #    pasta_item
        # )
        # if not sucesso:
        #    return (False, msg_erro)


        # 2) IPED
        # ====================================
        # Executa IPED
        (sucesso, msg_erro) = executa_iped(codigo_tarefa, comando,
                                           caminho_origem, caminho_destino, caminho_log_iped,
                                           caminho_tela_iped)
        if not sucesso:
            return (False, msg_erro)

        # 3) Recupera dados do log para utilizar em laudo
        # ===============================================
        (sucesso, msg_erro) = recupera_dados_laudo(codigo_tarefa, caminho_log_iped)
        if not sucesso:
            return (False, msg_erro)

        # 4) Cálculo de HASH
        # ====================================
        # Calcula hash
        (sucesso, msg_erro) = calcula_hash_iped(codigo_tarefa, caminho_destino)
        if not sucesso:
            return (False, msg_erro)

        # 5) Ajusta ambiente para Multicase
        # =================================
        (sucesso, msg_erro) = ajusta_multicase(tarefa, codigo_tarefa, caminho_destino)
        if not sucesso:
            return (False, msg_erro)

        # 6) Retorna para a pasta os arquivos que não precisavam ser processados pelo IPED
        # ================================================================================
        # Todo: Quando refizer o passo 1, refazer a restauração
        # (sucesso, msg_erro) = restaura_arquivos_movidos(lista_movidos)
        # if not sucesso:
        #    return (False, msg_erro)

        # 7) Calcula o tamanho final da pasta do IPED
        (sucesso, msg_erro) = calcula_tamanho_total_pasta(caminho_destino)
        if not sucesso:
            return (False, msg_erro)


    except BaseException as e:
        # Pega qualquer exceção não tratada aqui, para jogar no log
        trc_string = traceback.format_exc()
        erro_excecao = True

    if erro_excecao:
        print_log(trc_string)
        # Tenta registrar no log o erro ocorrido
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="ERRO em sapi_iped: " + trc_string
        )
        sapisrv_reportar_erro("Tarefa " + str(Gcodigo_tarefa_executando) + "Erro => " + trc_string)
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
            print_tela_log("Aguardando encerramento de", len(lista), "processo(s). Situação incomum!")
        # Aguarda e repete, até finalizar tudo...isto não deveria acontecer....
        time.sleep(2)

    # Ok, tudo encerrado
    # -----------------------------------------------------------------------------------------------------------------
    print_log(" ===== FINAL ", Gprograma, " - (Versao", Gversao, ")")
    os._exit(1)


# -----------------------------------------------------------------------
# --config: Modo de configuração
# ----------------------------------------------------------------------
def exibir_configuracao_sap_iped(cfg, titulo="Configuração sapi_iped"):
    print(titulo)
    print_centralizado("-")
    print_formulario(label="Unidade", largura_label=30, valor=cfg.get("unidade_sigla", ""))
    print_formulario(label="Storages de atuação", largura_label=30, valor=cfg.get("storage_escopo", ""))
    print_formulario(label="Storage selecionado", largura_label=30, valor=cfg.get("storage_selecionado", ""))
    print_formulario(label="IPED: Caminho jar", largura_label=30, valor=cfg.get("iped_caminho_jar", ""))
    print_formulario(label="IPED: Comando", largura_label=30, valor=cfg.get("iped_comando", ""))
    print_formulario(label="IPED: Versão", largura_label=30, valor=cfg.get("iped_versao", ""))
    print_formulario(label="IPED: Profiles habilitados", largura_label=30,
                     valor=cfg.get("iped_profiles_habilitados", ""))
    print_formulario(label="Java: Caminho", largura_label=30, valor=cfg.get("java_path", ""))
    print_formulario(label="Java: Versão", largura_label=30, valor=cfg.get("java_versao", ""))
    print_centralizado("")


def cfg_definir():
    return console_executar_tratar_ctrc(funcao=_cfg_definir)


# Carrega situação de arquivo
# ----------------------------------------------------------------------
def _cfg_definir():
    # Armazenará todos os parâmetros de configuração
    cfg = dict()

    # Inicialização básica, para executar parte em modo interativo
    nome_arquivo_log = "log_sapi_iped.txt"
    sapisrv_inicializar_ok(Gprograma, Gversao, auto_atualizar=True, nome_arquivo_log=nome_arquivo_log)
    print_log('Inicializado com sucesso', Gprograma, ' - ', Gversao)

    # Cabeçalho
    cls()
    print(Gprograma + " (v" + Gversao + "): - Modo de configuração")
    print("=======================================================")
    print("Dica: Para interromper, utilize CTR-C")
    print("")

    # Verifica se já existe configuração
    # ----------------------------------
    configuracao_existente = sapisrv_obter_configuracao_agente(Gprograma)
    if configuracao_existente != None:

        exibir_configuracao_sap_iped(configuracao_existente, "Configuração ATUAL")

        print_atencao()
        print("- Este agente já possui configuração registrada.")
        print("- Se você prosseguir, a configuração atual será sobreposta")
        if not prosseguir_configuracao():
            return False
    else:
        # Pode ser a primeira configuração. Dá as dicas:
        print("- Pré-requisitos para configuração do agente sapi_iped:")
        print("1) Você deve possuir direito de administração no SAPI.")
        print("2) Deve ter sido feita a configuração dos profiles IPED que ficarão habilitados para o SAPI.")
        print("3) Deve existir no mínimo um storage SAPI configurado e registrado na sua unidade.")
        print("4) O IPED deve ter sido previamente instalado nesta máquina e sua configuração revisada.")
        print("   Dica: Não esqueça de revisar o LocalConfig.txt e revisar/criar profiles customizados")
        print("- Em caso de dúvida sobre algum destes pontos, ver: ", Gwiki_sapi)
        print()
        if not prosseguir_configuracao():
            return False

    # Guarda dados básicos do programa
    cfg['agenteSAPI'] = Gprograma
    cfg['agenteSAPI_versao'] = Gversao

    if not login_sapi():
        return False

    # Verifica se usuário tem direito de administrador
    if not obter_param_usuario("adm_sapi"):
        print("- ERRO: Este programa requerer direito de administração do SAPI")
        print("  Ver:", Gwiki_sapi)
        return False

    unidade = obter_param_usuario("codigo_unidade_lotacao")
    ip_cliente = obter_param_usuario("ip_cliente")
    host_name = socket.gethostname()
    sigla_unidade = obter_param_usuario("sigla_unidade_lotacao")

    cfg['configurador_conta_usuario'] = obter_param_usuario('conta_usuario')
    cfg['unidade'] = unidade
    cfg['unidade_sigla'] = sigla_unidade
    cfg['computador_ip'] = ip_cliente
    cfg['computador_hostname'] = host_name

    # Verifica se usuário tem direito de administrador
    if not obter_param_usuario("adm_sapi"):
        print("- ERRO: Para efetuar a configuração você precisa de direito de administrador no SAPI.")
        print("  Ver:", Gwiki_sapi)
        return False

    # Recupera lista de storages da unidade de lotação do usuário
    # -----------------------------------------------------------
    print()
    print("Storages registrados na unidade")
    print("-" * 65)
    print_tela_log("- Recuperando lista de storages. Aguarde...")
    lista_storages = obter_lista_storages_unidade(unidade=unidade, tipo='trabalho')
    if not isinstance(lista_storages, list) or len(lista_storages) == 0:
        print("- ERRO: Para configurar o sapi_iped deve existir pelo menos um storage registrado na unidade",
              sigla_unidade)
        print("  Ver:", Gwiki_sapi)
        return False

    q = 0
    for sto in lista_storages:
        # var_dump(sto)
        # die('ponto2335')
        q += 1
        if (q == 1):
            # Cabecalho
            print('%2s  %-60s' % ("Sq", "Storage_id : Descrição do storage"))
            print("-" * 65)
        # Exibe elemento
        print('%2d  %-60s' % (q, sto["storage_id"] + " : " + sto["descricao"]))

    # Recupera lista de perfis de IPED da unidade de lotação do usuário
    # -------------------------------------------------------------------
    print()
    print("Lista de profiles IPED")
    print("-" * 100)
    dict_perfil = obter_dict_perfil_iped(unidade)
    if not isinstance(dict_perfil, dict):
        # Algum erro aconteceu...finaliza
        print("- Dicionário de perfis do IPED inconsistente")
        return False

    # Se ainda não tem nenhum storage, finaliza
    if len(dict_perfil) == 0:
        print("- ERRO: Não existe nenhum perfil para sapi_iped configurado na unidade", sigla_unidade)
        print("  Ver:", Gwiki_sapi)
        return False

    q = 0
    for id_perfil in dict_perfil:
        q += 1
        if (q == 1):
            # Cabecalho
            print('%2s %-100s' % ("", "Profile : Descrição"))
            print("-" * 100)
        # Exibe elemento
        print('%2d %-100s' % (q, id_perfil + " : " + dict_perfil[id_perfil]))

    print()
    print("- Verifique se os dados acima correspondem à sua expectativa.")
    print(
        "- Caso contrário, para evitar retrabalho, primeiro ajuste a configuração destes elementos e depois retorne aqui.")
    if not pergunta_sim_nao("< Prosseguir?", default="n"):
        print("- Configuração cancelada pelo usuário.")
        return False

    cfg["iped_profiles_habilitados"] = list(dict_perfil.keys())

    # Escopo de storages
    # -----------------------------------------------
    lista_opcoes = [
        (CONST_storage_unico(), "Processa tarefas armazenadas em um único storage."),
        (CONST_storage_preferencial(), "Processa tarefas armazenadas em um certo storage (preferencial), "
                                       "\n    mas se ficar ocioso, processa tarefas de qualquer storage"),
        (CONST_storage_todos(), "Processa tarefas de qualquer storage.")
    ]

    print()
    storage_escopo = dialogo_selecionar_opcao(
        label="Storages de Atuação (Escopo)",
        ajuda="- Indique sobre qual(is) storage(s) este agente sapi_iped irá atuar.",
        lista_opcoes=lista_opcoes)
    cfg['storage_escopo'] = storage_escopo

    # Nome do storage
    # --------------------------------------------------------
    storage = ''
    label_selecionar_storage = ''
    selecionar_storage = False
    if storage_escopo == CONST_storage_unico():
        selecionar_storage = True
        label_selecionar_storage = "Selecione storage único (exclusivo)"
    if storage_escopo == CONST_storage_preferencial():
        selecionar_storage = True
        label_selecionar_storage = "Selecione storage preferencial"

    if selecionar_storage:
        storage = _cfg_selecionar_storage(lista_storages, label_selecionar_storage)
        if storage is None:
            # Usuário não selecionou o storage (provavelmente CTR-C)
            return False

        cfg['storage_selecionado'] = storage['storage_id']
        config_storage_teste = storage['configuracao']
    else:
        # Se não tem um storage específico associado,
        # pega o primeiro para fazer teste de conexão
        config_storage_teste = lista_storages[0]['configuracao']
        print("- Como este sapi_iped dever funcionar com qualquer storage, será utilizado no teste o",
              config_storage_teste["storage_id"])

    # -------------------------------------------------------------------
    # Montar storage
    # ------------------------------------------------------------------
    print()
    print("Conexão com storage")
    print("-------------------")
    ponto_montagem = conectar_storage_atualizacao_ok(config_storage_teste)
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return False
    print("- Conectado com sucesso no storage", config_storage_teste["storage_id"])
    debug("- Pasta de montagem:", ponto_montagem)

    # -------------------------------------------------------------------
    # Seleciona jar de execução do IPED
    # -------------------------------------------------------------------
    print()
    print("Caminho para IPED")
    print("-----------------")
    print("- Na janela gráfica aberta, selecione o arquivo jar do IPED (iped.jar) a ser executado")

    # Cria janela para indicação de arquivo JAR do IPED
    root = tkinter.Tk()
    j = JanelaTk(master=root)
    iped_caminho_jar = j.selecionar_arquivo([('JAR do IPED', '*.jar')], titulo="Selecione arquivo JAR do IPED")
    root.destroy()

    if iped_caminho_jar is None or iped_caminho_jar == '':
        print("- Caminho para jar não selecionado")
        return False
    cfg['iped_caminho_jar'] = iped_caminho_jar
    print("- Caminho do jar do IPED selecionado: ", iped_caminho_jar)

    # -------------------------------------------------------------------
    # Java que veio com IPED está ok
    # -------------------------------------------------------------------
    # Monta caminho para java embutido no IPED
    (iped_raiz, iped_jar) = os.path.split(iped_caminho_jar)
    java_path = os.path.join(iped_raiz, "jre", "bin", "java.exe")

    print()
    print("Confere instalação JAVA")
    print("------------------------")
    print_tela_log("- Caminho para java embutido no IPED", java_path)
    print_tela_log("- Verificando versão do java")

    # Comando para execução do IPED
    # comando='java -version'
    comando = java_path + ' -version'

    (sucesso, msg_erro, saida) = executa_comando_os(comando)
    if not sucesso:
        print_tela_log("- Comando:")
        print(comando)
        print_tela_log("- ERRO: Execução falhou")
        if msg_erro != "":
            print(msg_erro)
        return False
    saida = str(saida).strip()
    print_tela_log("- Versão: ")
    print(saida)
    if not ('java version' in saida):
        print_tela_log("- ERRO: Não foi encontrado indicativo de versão java")
        return False
    if not ('64-Bit' in saida):
        print_atencao()
        print_tela_log("- AVISO: Versão java não parece ser 64 bits. Confira")
        if not pergunta_sim_nao("< Prosseguir?", default="n"):
            print("- Configuração cancelada pelo usuário.")
            return False

    cfg['java_path'] = java_path
    cfg['java_versao'] = saida

    # -------------------------------------------------------------------
    # IPED instalado?
    # -------------------------------------------------------------------
    print()
    print("Conferindo versão do IPED")
    print("-------------------------")

    # Comando para execução do IPED
    iped_comando = cfg['java_path'] + ' -jar ' + iped_caminho_jar
    comando = iped_comando + ' --help '
    print_tela_log("- Comando de execucao do IPED:", iped_comando)

    # Saida para arquivo
    caminho_tela_iped = "teste_iped_tela_saida.txt"
    comando = comando + " >" + caminho_tela_iped + " 2>&1 "

    debug("- Invocando iped com comando")
    debug(comando)
    (sucesso, msg_erro, saida) = executa_comando_os(comando)
    # Aqui não podemos testar se comando foi executado com sucesso,
    # pois quando o IPED recebe --help retorna exit code 1
    # como se tivesse dado erro
    # Então vamos checar apenas o arquivo de resultado, se está ok
    # if not sucesso:
    #    print("- ERRO: Execução falhou")
    #    if msg_erro!="":
    #        print(msg_erro)
    #    return False

    # Le conteúdo da tela de resultado para:
    # 1) Confirmar que IPED foi executado
    # 2) Identificar a versão do IPED
    versao_iped = ""
    resultado_iped = ""
    if os.path.isfile(caminho_tela_iped):
        with open(caminho_tela_iped, "r") as fentrada:
            for linha in fentrada:
                if "Indexador e Processador de Evidências Digitais" in linha:
                    (inicio, numero_versao) = linha.split('Digitais')
                    numero_versao = numero_versao.strip()
                    if not numero_versao == "":
                        versao_iped = numero_versao
                    else:
                        print("- Não foi possível reconhecer a versão do IPED na linha: " + linha)
                resultado_iped = resultado_iped + linha

    # Se não achou versão....pode ter várias causas
    if versao_iped == "":
        print(comando)
        print("- Resultado:")
        print_console(resultado_iped)
        print()
        print_tela_log(
            "- Não foi possível reconhecer a versão do IPED. Assegure-se que IPED e seus requisitos estão adequadamente instalados")
        return False

    # Simula um versão, para testar comportamento
    # versao_iped="3.15.1"
    # versao_iped="3.25.1"

    debug("- IPED invocado com sucesso.")
    print_tela_log("- Versão do IPED detectada: ", versao_iped)

    # Verifica se versão do IPED é compatível com SAPI
    partes_versao = versao_iped.split(".")
    # var_dump(partes_versao)
    # die('ponto2241')
    if int(partes_versao[0]) < 3 or int(partes_versao[1]) < 14:
        print_tela_log("- ERRO: sapi_iped requer iped com versão igual ou superior a 3.14.xx")
        return False

    # Verifica se a versão do IPED é "homologada"
    lista_versoes_iped = ['3.14.2', '3.14.3', '3.14.4']
    # lista_versoes_iped=['3.14.2', '3.14.3']
    if versao_iped not in lista_versoes_iped:
        print_atencao()
        print_tela_log("- Versão do IPED", versao_iped,
                       "detectada não está na lista de versões homologadas pelo sapi_iped", str(lista_versoes_iped))
        print(
            "- Isto não significa que não irá funcionar. Significa apenas que esta versão nunca foi testada com o sapi_iped.")
        print(
            "- Versões com formatos de saída e log muito diferentes das homologadas, podem apresentar mal funcionamento, ")
        print("  pois o sapi_iped pode não conseguir interpretar o resultado do iped.")
        if not prosseguir_configuracao():
            return False

    cfg['iped_comando'] = iped_comando
    cfg['iped_versao'] = versao_iped

    # --------------------------------------------------------------------
    # Teste de execução do IPED, simulando situação real (storage)
    # --------------------------------------------------------------------
    print()
    print("Teste de execução SIMULADA do IPED")
    print("----------------------------------")
    print(
        "- A seguir serão efetuados vários testes para assegurar que o IPED está adequadamente configurado para ser utilizado pelo SAPI.")
    print("- Será feita uma simulação realista, incluindo conexão com storage e utilização de profiles configurados.")
    print("- Este testes podem demorar alguns minutos.")
    if not prosseguir_configuracao():
        return False
    if not _cfg_testar_iped(config_storage_teste, dict_perfil, cfg['iped_comando']):
        # As mensagens de erro já foram dadas pela subrotina
        return False

    # --------------------------------------------------------------------
    # Confirma configuração
    # --------------------------------------------------------------------
    print()
    print("- OK. Sucesso. Passou por todos os testes")
    print()

    # Exibe configuração formatada
    exibir_configuracao_sap_iped(cfg, "Configuração a ser gravada")

    print()
    print("- Confira se a configuração acima está correta.")
    print("- Se você prosseguir, a configuração será registrada no SAPI WEB")
    print("  e este agente ficará habilitado para executar tarefas.")
    if not prosseguir_configuracao():
        return False

    # Registrar configuração
    # ------------------------
    print("- Registrando configuração no SETEC3. Aguarde...")
    (sucesso, msg_erro) = sapisrv_registrar_configuracao_cliente(
        programa=Gprograma,
        configuracao=cfg,
        ip=ip_cliente,
        unidade=unidade)
    if not sucesso:
        print("- ERRO: ", msg_erro)
        return False

    # Finalizado com sucesso
    # ------------------------
    print()
    print("SUCESSO")
    print("-------")
    print("- Configuração armazenada com sucesso no servidor SETEC3")
    print("- Para que o sapi_iped começe a executar tarefas, invoque-o novamente, SEM a opção --config")
    return True


def _cfg_selecionar_storage(lista_storages, label):
    print()
    print(label)
    print("-" * 65)

    q = 0
    for sto in lista_storages:
        q += 1
        if (q == 1):
            # Cabecalho
            print('%2s  %-60s' % ("Sq", "Storage"))
            print("-" * 65)
        # Exibe elemento
        print('%2d  %-60s' % (q, sto["storage_id"] + " : " + sto["descricao"]))

    while True:
        #
        print()
        sq_storage = input(
            "< Indique o número de sequência (Sq) do storage: ")
        sq_storage = sq_storage.strip()

        if not sq_storage.isdigit():
            print("- Entre com o número sequencial do storage")
            print("- Digite <CTR><C> para cancelar")
            continue

        # Verifica se existe na lista
        sq_storage = int(sq_storage)
        if not (1 <= sq_storage <= len(lista_storages)):
            # Número não é válido
            print("Entre com o sequencial do storage, entre 1 e ", str(len(lista_storages)))
            continue

        ix_storage = int(sq_storage) - 1

        # Ok, selecionado
        print()
        storage = lista_storages[ix_storage]
        break

    # Devolve storage selecionado
    return storage


# Confirma se usuário deseja prosseguir com configuração
def prosseguir_configuracao():
    if not pergunta_sim_nao("< Prosseguir?", default="n"):
        print("- Configuração cancelada pelo usuário.")
        return False

    # Usuário deseja prosseguir
    return True


# Testa o IPED para cada um dos profiles,
# garantindo que todos estão funcionado ok
def _cfg_testar_iped(config_storage_teste, dict_perfil, iped_comando):
    # return True

    # Monta comando iped
    # ------------------------------------------------------------------------------------------------------------------
    for profile_iped in dict_perfil:

        while True:
            print()
            print("Testando execução do iped com -profile", profile_iped)
            print("---------------------------------------------------------")
            # print_atencao()
            # print("- Alguns dos comandos abaixo podem demorar alguns minutos. Aguarde o resultado...")

            (sucesso, mensagem_erro, conteudo_tela, conteudo_log) = \
                testar_iped(config_storage_teste, iped_comando, profile_iped)

            if sucesso:
                # Como deu certo, interrompe o loop (vai para próximo profile, se houver)
                print("- IPED executado com SUCESSO para profile", profile_iped)
                break

            if sucesso == False:
                print_tela_log("- Tentativa de execução do IPED falhou.")
                print_tela_log("- ERRO: ", mensagem_erro)
                if conteudo_log != "":
                    print()
                    print("Log do IPED")
                    print("-----------")
                    print(conteudo_log)
                if conteudo_tela != "":
                    print()
                    print("Tela de resultado")
                    print("------------------")
                    print(conteudo_tela)
                # analisar_erro_iped()
                print()
                print(
                    "- Analise o erro acima, corrija a configuração do IPED, e quando estiver tudo ok, tente novamente")
                prosseguir = pergunta_sim_nao("< Tentar novamente?", default="n")
                if not prosseguir:
                    print("- Configuração cancelada pelo usuário.")
                    return False

    # Tudo certo. Todos os profiles foram validados
    return True


def testar_iped(config_storage_teste, iped_comando, profile_iped):
    # Prepara pasta para execucao do IPED
    # Conecta no storage de destino
    # -------------------------------------------------------------
    ponto_montagem = conectar_storage_atualizacao_ok(config_storage_teste)
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return False

    print_tela_log("- Conectado com sucesso no storage", config_storage_teste["storage_id"])
    print_tela_log("- Pasta de montagem:", ponto_montagem)

    # Monta pastas para processamento
    # ------------------------------------------------------------------------------------------------------------------
    # caminho_origem  ="C:\\teste_iped\\Memorando_1086-16\\item11\\item11_extracao"
    # caminho_destino ="C:\\teste_iped\\Memorando_1086-16\\item11\\item11_extracao_iped"

    # Cria pasta geral para o teste (simulação de pasta do memorando)
    # ---------------------------------------------------------------
    maquina = get_ip_local()
    pasta_teste_memorando = os.path.join(ponto_montagem, "teste_sapi_iped_" + maquina)
    print_tela_log("- Dados para teste serão gravados na pasta:", pasta_teste_memorando)
    # Se já existe pasta de teste, exclui antes de prosseguir
    if os.path.exists(pasta_teste_memorando):
        print_tela_log("- Pasta já existe. Excluindo pasta.")
        try:
            shutil.rmtree(pasta_teste_memorando)
        except Exception as e:
            print_tela_log("- ERRO: Não foi possível limpar pasta de teste: " + str(e))
            return False

    # Não pode existir. Se existir, processo de exclusão acima falhou
    if os.path.exists(pasta_teste_memorando):
        print_tela_log(
            "- [2481] ERRO: Tentativa de excluir pasta de teste falhou: Verifique se existe algo aberto na pasta, que esteja criando um lock em algum dos seus recursos")
        return False
    try:
        os.makedirs(pasta_teste_memorando)
    except Exception as e:
        print_tela_log("- [2488] ERRO: Não foi possível criar pasta de teste: " + str(e))
        return False

    # Confere se deu certo
    if not os.path.exists(pasta_teste_memorando):
        print_tela_log("- [2493] ERRO: Criação de pasta de teste falhou sem causar exceção!! Situação inesperada!")
        return False

    # Prepara pasta de origem (simulação de pasta de arquisição de dados)
    # -------------------------------------------------------------------
    caminho_origem = os.path.join(pasta_teste_memorando, "item01_dados")
    try:
        # Cria a subpasta para origem
        os.makedirs(caminho_origem)

        # Cria um arquivo na pasta de origem
        caminho_arquivo_teste = os.path.join(caminho_origem, "arquivo1.txt")
        print_tela_log("- Criando arquivo: ", caminho_arquivo_teste)
        file = open(caminho_arquivo_teste, "w")
        file.write("Arquivo para testar execução do IPED")
        file.close()

    except Exception as e:
        print_tela_log("- [2488] ERRO: Não foi possível criar arquivo para teste do iped: " + str(e))
        return False

    print_tela_log("- Arquivo criado com sucesso")

    # Caminho para pasta de destino
    # ------------------------------------------------------------------------------------------------------------------
    caminho_destino = os.path.join(pasta_teste_memorando, "item01_iped")
    print_tela_log("- Criando pasta para destino do IPED: ", caminho_destino)
    try:
        os.makedirs(caminho_destino)
    except Exception as e:
        print_tela_log("- [2488] ERRO: Não foi possível criar pasta:  " + str(e))
        return False
    # Confere se deu certo
    if not os.path.exists(caminho_destino):
        print_tela_log("- [2493] ERRO: Criação de pasta falhou sem causar exceção!! Situação inesperada!")
        return False

    (comando, caminho_tela_iped, caminho_log_iped) = montar_comando_iped(
        iped_comando,
        caminho_origem,
        caminho_destino,
        profile_iped)

    print_tela_log("- Executando IPED com comando abaixo.")
    print_tela_log(comando)
    print("- Isto pode demorar alguns minutos. Aguarde...")
    (sucesso, msg_erro, saida) = executa_comando_os(comando)

    # Recupera conteudo da tela, se existir
    conteudo_tela = ""
    if os.path.isfile(caminho_tela_iped):
        with open(caminho_tela_iped, "r") as ftela:
            conteudo_tela = ftela.read()

    # Recupera conteudo do log, se existir
    conteudo_log = ""
    if os.path.isfile(caminho_log_iped):
        with open(caminho_log_iped, "r") as flog:
            conteudo_log = flog.read()

    # Se deu erro na chamada, retorna todos dados para análise
    if not sucesso:
        return (False, msg_erro, conteudo_tela, conteudo_log)

    # Se não deu erro (exit code),
    # espera-se que o IPED tenha chegado até o final normalmente
    # Para confirmar isto, confere se existe o string abaixo
    if not verificar_sucesso_iped(caminho_tela_iped):
        # Algo estranho aconteceu, pois não retornou erro (via exit code),
        # mas também não retornou mensagem de sucesso na tela
        msg_erro = "Não foi detectado indicativo de sucesso do IPED. Verifique tela e log."
        # Neste caso, vamos abortar definitivamente, para fazer um análise do que está acontecendo
        # pois isto não deveria acontecer jamais
        return (False, msg_erro, conteudo_tela, conteudo_log)

    # Tudo certo, IPED finalizado com sucesso
    # ---------------------------------------
    # Exclui pasta geral
    if os.path.exists(pasta_teste_memorando):
        print_tela_log("- Excluindo pasta utilizada no teste:", pasta_teste_memorando)
        try:
            shutil.rmtree(pasta_teste_memorando)
        except Exception as e:
            print_tela_log("- ERRO: Não foi possível excluir pasta de teste: " + str(e))
            return False

    # Retorna, devolvendo dados para chamador
    return (True, "", conteudo_tela, conteudo_log)


# ======================================================================
# Rotina Principal
# ======================================================================

def main():
    # Processa parâmetros logo na entrada, para garantir que configurações relativas a saída sejam respeitads
    sapi_processar_parametros_usuario()

    # Tratamento para configuração
    # ------------------------------------
    if modo_config():
        cfg_definir()
        # Depois que finaliza a configuração, encerrar o programa
        finalizar_programa()
        sys.exit(0)

    # if not cfg_carregar():
    #    print_tela_log("Agente sapi_iped não está configurado. Para entrar em modo de configuração, utilize opção --config")
    #    sys.exit(0)

    # Cabeçalho inicial do programa
    # ------------------------------------------------------------------------------------------------------------------
    # Verifica se programa já está rodando (outra instância)
    if existe_outra_instancia_rodando(Gcaminho_pid):
        print("Já existe uma instância deste programa rodando.")
        print("Abortando execução, pois só pode haver uma única instância deste programa")
        sys.exit(0)

    # Inicialização do programa
    # -----------------------------------------------------------------------------------------------------------------
    # Se não estiver em modo background (opção do usuário),
    # liga modo dual, para exibir saída na tela e no log
    if not modo_background():
        ligar_log_dual()

    print_log(" ===== INÍCIO ", Gprograma, " - (Versao", Gversao, ")")

    # Inicializa e obtem a lista de ipeds que estão aptos a serem executados nesta máquina
    if not inicializar():
        # Falhou na inicialização, talvez falha de comunicação, talvez mudança de versão...
        finalizar_programa()

    while True:

        if Giped_profiles_habilitados is None or len(Giped_profiles_habilitados) == 0:
            # Se existe alguma condição que impede a execução (Por exemplo: iped em versão ultrapassada),
            # interrompe o loop, e finaliza
            # Mensagens adequadas já foram dadas na função inicializar()
            # Desta forma, a rotina de atualização baixará uma nova versão do sapi_iped e iped
            # que podem vir a regularizar a situação
            finalizar_programa()

        # Execução
        algo_executado = ciclo_executar()
        algo_excluido = ciclo_excluir()

        if algo_executado or algo_excluido:
            # Como servidor não está ocioso, faz uma pequena pausa e prossegue
            time.sleep(60)
            continue
        else:
            # Se não fez nada no ciclo,
            # faz uma pausa para evitar sobrecarregar o servidor com requisições
            dormir(GdormirSemServico)
            # Depois que volta da soneca da ociosidade e reinicializa
            # pois algo pode ter mudado (versão do IPED por exemplo)
            # Se isto acontecer, finaliza sapi_iped para que seja atualizado
            if not inicializar():
                # Falhou na inicialização, talvez falha de comunicação, talvez mudança de versão...
                finalizar_programa()


if __name__ == '__main__':
    main()

