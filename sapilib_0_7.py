# *********************************************************************************************************************
# *********************************************************************************************************************
# *********************************************************************************************************************
#        BIBLIOTECA DE FUNÇÕES GERAIS DO SAPI PARA PYTHON (SAPILIB)
# 
#
# CONCEITOS:
#
# a) Incorporação no código
# ----------------------------------------------------------------------------------------------------------------------
# - Esta biblioteca é utiliza por todos os programas python do sistema SAPI
# - Para evitar colocar na produção um código com dependência,
#   particularmente para os programas que serão baixados do servidor Web e executados em máquinas diversas,
#   utiliza-se a inserção desta biblioteca no código de produção.
# - Durante o estágio de desenvolvimento esta biblioteca é mantida em arquivo separado,
#   sendo importada integralmente para os programas sapi através do comando:
#   from sapi import *
# - Quando prepara-se o código para produção, o comando acima é substituido pelo código integral desta biblioteca
# - Isto evita dependência (na produção) e evita redundância de código (durante o desenvolvimento)
#
# b) Funções com sufixo _ok
# ----------------------------------------------------------------------------------------------------------------------
# - Existem várias funções com nomes similares, se diferenciando apenas por um sufixo _ok
# - As funções que tem sufixo _ok, irão tratar os erros por sua própria conta, normalmente abortando
#   caso ocorra algum erro. Ou seja, o chamador esperar que tudo ocorra 'ok',
#   e abre mão do controle caso ocorra algum erro.
# - As funções que não tem sufixo _ok, por outro lado, esperam que o controle seja devolvido
#   caso ocorra algum erro. Esta chamadas tem que ser tratadas com try.
#
# - Recomenda-se que as funções _ok sejam utilizadas em alguns pontos de programas interativos,
#   mostrando o erro e interrompendo a operação, se o erro não for tratável.
# - Para os agentes autônomos do SAPI, não é aconselhável utilizar funções _ok, uma vez que
#   os agente autônomos devem ser altamente tolerante a falhas.
#
# - Histórico:
#   0.5.3 - Agregou funções que estavam no agente_demo
#   0.5.4 - Ajustes diversos.
#   0.6   - Programas escritos para versão 0.5.x devem ser ajustados para versão 0.6
#         - Principais modificações:
#            - Função de inicialização para determinação de IP do servidor,
#              verificação de habilitação de programas clientes, etc
#            - Incorporação de funções de alto nível da API, com prefixo sapisrv, que antes estavam nos clientes
#            - Funcionalide de post (ao invés de get) para enviar json grandes
#         - O que desenvolvedor tem que mudar:
#           1) chamar sapisrv_inicializar(Gnome_programa, Gversao) logo no início do programa
#           2) Utilizar funções de alto nível sapisrv_obter_iniciar_tarefa e sapisrv_atualizar_tarefa de sapilib
#              ao invés das funções atualmente definidas dentro do próprio código do programa.
#   0.6.1 - Ajustado para nas chamadas ao servidor passar também o programa de execução
#   0.7   - Melhoria na tolerância a falhas, exibindo mensagens explicativas dos problemas.
#
# *********************************************************************************************************************
# *********************************************************************************************************************
#                  INICIO DO SAPI_LIB
# *********************************************************************************************************************
# *********************************************************************************************************************

# Módulos utilizados
import codecs
import datetime
import json
import os
import pprint
import sys
import urllib
import urllib.parse
import urllib.request
import subprocess
import http.client
import socket
import tkinter
from tkinter import filedialog


# ---------- Constantes (na realidade variáveis Globais) ------------
Gversao_sapilib = "0.7"

# Valores de codigo_situacao_status (para atualizar status de tarefas)
# --------------------------------------------------------------------
GManterSituacaoAtual = 0
GAguardandoPCF = 1
GSemPastaNaoIniciado = 1
GAguardandoProcessamento = 5
GAbortou = 8
GDespachadoParaAgente = 20
GPastaDestinoCriada = 30
GEmAndamento = 40
GIpedExecutando = 60
GIpedFinalizado = 62
GIpedHashCalculado = 65
GIpedMulticaseAjustado = 68

GFinalizadoComSucesso = 95

# Configuração dos ambientes
# --------------------------
Gconf_ambiente = dict()
# Todo: Incluir o IP na VLAN do setec3 nas listas abaixo
# --- Desenvolvimento ---
Gconf_ambiente['desenv'] = {
    'nome_ambiente': 'DESENVOLVIMENTO',
    'servidor_protocolo': 'http',
    'ips': ['10.41.84.5', '10.41.84.5'],
    'servidor_porta': 80,
    'servidor_sistema': 'setec3_dev'
}
# --- Produção ---
Gconf_ambiente['prod'] = {
    'nome_ambiente': 'PRODUCAO',
    'servidor_protocolo': 'http',
    'ips': ['10.41.84.5', '10.41.84.5'],
    'servidor_porta': 80,
    'servidor_sistema': 'setec3'
}

# Definido durante inicializacao
# --------------------------------
Ginicializado = False
Gparini = dict()  # Parâmetros de inicialização


# Controle de mensagens/log
GlogDual = False

# =====================================================================================================================
# Funções de ALTO NÍVEL relacionadas com acesso ao servidor (sapisrv_*)
#
# Todas as funções de alto nível possuem prefixo 'sapisrv'
#
# Utilize preferencialmente estas funções, pois possuem uma probabilidade menor de alteração na interface (parâmetros).
# Caso novos parâmetros sejam incluídos, serão opcionais.
# =====================================================================================================================

# Liga log dual, fazendo com que todas as mensagens de log sejam exibidas também em tela
# Isto faz com que qualquer print_log (e não apenas o print_log_dual) exiba a saída em tela,
# além de escrever no log
def ligar_log_dual():
    global GlogDual
    GlogDual = True

# Desliga log_dual. print_log irá gravar apenas no log.
# Apenas chamadas explícitas à função print_log_dual exibirão a saida no log e na tela.
def desligar_log_dual():
    global GlogDual
    GlogDual = False


# Função de inicialização para utilização do sapisrv:
# - nome_programa (obrigatório) : Nome do programa em execução
# - versao_programa (obrigatório): Versão do programa em execução
# - nome_agente : Default: hostname
# - ambiente : 'desenv' ou 'prod'
#              Default: 'desenv' se houver arquivo 'desenvolvimento_nao_excluir.txt' na pasta. Caso contrário, 'prod'
# ----------------------------------------------------------------------------------------------------------------------
def _sapisrv_inicializar_internal(nome_programa, versao, nome_agente=None, ambiente=None):
    # Atualiza estas globais
    global Ginicializado
    global Gparini

    # Se já foi inicializado, despreza, pois só pode haver uma inicialização por execução
    if Ginicializado:
        return

    # Nome do programa
    if nome_programa is None:
        # obrigatório
        erro_fatal("Nome do programa não informado")
    Gparini['programa'] = nome_programa

    # Vesão do programa
    if versao is None:
        # Obrigatório
        erro_fatal("Versão não informada")
    Gparini['programa_versao'] = versao

    # Nome do Agente
    if nome_agente is None:
        # Default
        nome_agente = socket.gethostbyaddr(socket.gethostname())[0]
    Gparini['nome_agente'] = nome_agente

    # Ambiente
    if ambiente is None:
        # Verifica se na pasta que está sendo executado existe arquivo desenvolvimento_nao_excluir.txt
        # Se existir, aceita isto como um sinalizador que está rodando em ambiente de desenvolvimento
        arquivo_desenvolvimento = 'desenvolvimento_nao_excluir.txt'
        if os.path.isfile(arquivo_desenvolvimento):
            ambiente = 'desenv'

    if ambiente is None:
        # Default
        ambiente = 'prod'

    # Determina IP que servidor está respondendo (máquina executante pode estar na rede geral ou na VLAN)
    amb = Gconf_ambiente[ambiente]
    conectou = False
    for ip in amb['ips']:
        # Monta URL
        url_base = amb['servidor_protocolo'] + '://' + ip + ':' + str(amb['servidor_porta']) + \
                   '/' + amb['servidor_sistema'] + '/'
        conectou = testa_comunicacao_servidor_sapi(url_base)
        if conectou:
            Gparini['ambiente'] = ambiente
            Gparini['nome_ambiente'] = amb['nome_ambiente']
            # Servidor
            Gparini['servidor_protocolo'] = amb['servidor_protocolo']
            Gparini['servidor_ip'] = ip
            Gparini['servidor_porta'] = amb['servidor_porta']
            Gparini['servidor_sistema'] = amb['servidor_sistema']
            Gparini['url_base'] = url_base
            # Como token, por equanto será utilizado um valor fixo
            Gparini['servidor_token'] = 'token_fixo_v0_7'
            # ok
            break

    if not conectou:
        # Gera execeção, para deixar chamador decidir o que fazer
        raise SapiExceptionFalhaComunicacao("Nenhum servidor respondeu.")

    # Verifica se versão do programa está habilitada a rodar, através de chamada ao servidor
    # Todo: Implementar verificações no servidor (agente, programa/versão)
    # programa_habilitado(Gparini['nome_programa'], Gparini['versao'])
    # simulação de erros:
    # raise SapiExceptionAgenteDesautorizado("Máquina com ip 10.41.58.58 não autorizada para executar tal programa")
    # raise SapiExceptionProgramaDesautorizado("Este programa xxxx na versão zzz não está autorizado")

    # Tudo certo
    Ginicializado = True
    print_log("Inicializado SAPILIB: Agente= ", _obter_parini('nome_agente'),
              " Ambiente= ", _obter_parini('nome_ambiente'),
              " Servidor=  ", _obter_parini('servidor_ip'))

    return


# Função de inicialização para utilização do sapisrv
# Se ocorrer algum erro, ABORTA
# ----------------------------------------------------------------------------------------------------------------------
def sapisrv_inicializar_ok(*args):
    try:
        sapisrv_inicializar(*args)

    except BaseException as e:
        print_tela_log("Erro na inicialização: " + str(e))
        print("Para mais detalhes consulte o arquivo de log (sapi_log.txt)")
        sys.exit(1)


# Função de inicialização para utilização do sapisrv
# ----------------------------------------------------------------------------------------------------------------------
def sapisrv_inicializar(*args):
    try:
        _sapisrv_inicializar_internal(*args)

    except SapiExceptionFalhaComunicacao as e:
        # Exibe erro e passa para cima
        print_tela_log("Falha na comunicação: ", e)
        print("Para mais detalhes consulte o arquivo de log (sapi_log.txt)")
        raise

    except SapiExceptionProgramaDesautorizado as e:
        # Exibe erro e passa para cima
        print_tela_log("Programa/versão não foi autorizado pelo servidor: ", e)
        print("Verifique no SETEC3 qual o programa/versão indicado para a tarefa a ser executada")
        raise

    except SapiExceptionAgenteDesautorizado as e:
        # Exibe erro e passa para cima
        print_tela_log("Agente (máquina) desautorizado: ", e)
        print("Assegure-se de estar utilizando uma máquina homologada")
        raise

    except BaseException as e:
        # Exibe erro e passa para cima
        print_tela_log("Erro na inicialização: " + str(e))
        print("Para mais detalhes consulte o arquivo de log (sapi_log.txt)")
        raise

# Reporta ao servidor um erro ocorrido no cliente
# Parâmetros:
#   programa: Nome do programa
#   ip (opcional): IP da máquina
def sapisrv_reportar_erro_cliente(
        erro
):
    # Lista de parâmetros
    param = dict()
    param['erro'] = erro

    # Invoca sapi_srv
    (sucesso, msg_erro, configuracao) = sapisrv_chamar_programa(
        "sapisrv_reportar_erro_cliente.php",
        param,
        abortar_insucesso=False,
        registrar_log=True
    )

    # Chamada respondida com falha
    # Talvez seja um erro intermitente.
    # Agente tem que ser tolerante a erros, e ficar tentando sempre.
    # Logo, iremos registrar no log e levantar uma exceção, deixando o chamador decidir o que fazer
    if not sucesso:
        print_log_dual("sapisrv_reportar_erro_cliente.php: ", msg_erro)
        # Não tem tarefa disponível para processamento
        raise SapiExceptionGeral("Não foi possível reportar erro ao servidor")

    # Não tem o que retornar
    return True


# Obtem a configuração de um programa cliente
# Parâmetros:
#   programa: Nome do programa
#   ip (opcional): IP da máquina
def sapisrv_obter_configuracao_cliente(
        programa,
        ip=None
):
    # Lista de parâmetros
    param = dict()
    param['programa'] = programa
    if (ip is not None):
        param['ip'] = ip

    # Invoca sapi_srv
    (sucesso, msg_erro, configuracao) = sapisrv_chamar_programa(
        "sapisrv_obter_configuracao_cliente.php",
        param,
        abortar_insucesso=False,
        registrar_log=True
    )

    # Chamada respondida com falha
    # Talvez seja um erro intermitente.
    # Agente tem que ser tolerante a erros, e ficar tentando sempre.
    # Logo, iremos registrar no log e levantar uma exceção, deixando o chamador decidir o que fazer
    if not sucesso:
        print_log_dual("sapisrv_obter_configuracao_cliente.php", msg_erro)
        # Não tem tarefa disponível para processamento
        raise SapiExceptionGeral("Não foi possível obter configuração")

    # Configuração obtida com sucesso
    return configuracao


# Obtem e inicia (atômico) uma tarefa de um certo tipo (iped-ocr, ief, etc)
# Parâmetros opcionais:
#  storage: Quando o agente tem conexão limitada (apenas um storage)
#  tamanho_minimo e tamanho_maximo (em bytes): Util para selecionar
#    tarefas grandes ou pequenas, o que possivelmente irá corresponder
#    ao esforço computacional.
def sapisrv_obter_iniciar_tarefa(
        tipo,
        storage=None,
        dispositivo=None,
        tamanho_minimo=None,
        tamanho_maximo=None,
):
    # Lista de parâmetros
    param = dict()
    param['tipo'] = tipo
    if (storage is not None):
        param['storage'] = storage
    if (dispositivo is not None):
        param['dispositivo'] = dispositivo
    if (tamanho_minimo is not None):
        param['tamanho_minimo'] = tamanho_minimo
    if (tamanho_maximo is not None):
        param['tamanho_maximo'] = tamanho_maximo

    # Invoca sapi_srv
    try:
        (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
            "sapisrv_obter_iniciar_tarefa.php",
            param,
            abortar_insucesso=False,
            registrar_log=True
        )
    except BaseException as e:
        print_log_dual("Exception na chamada do sapisrv_obter_iniciar_tarefa.php: ", e)
        print_log_dual("Presumindo erro intermitente. Continuando para tentar novamente mais tarde")
        return (False, None)

    # Chamada respondida com falha
    # Talvez seja um erro intermitente.
    # Agente tem que ser tolerante a erros, e ficar tentando sempre.
    # Logo, iremos registrar no log e devolver ao chamador como uma simples "Ausência" de tarefas
    if not sucesso:
        print_log_dual("Erro na chamada do sapisrv_obter_iniciar_tarefa", msg_erro)
        # Não tem tarefa disponível para processamento
        return (False, None)

    # Chamada respondida com sucesso
    # Servidor pode retornar dois valores possíveis:
    #  disponivel=0: Não tem tarefa
    #  disponivel=1: Tem tarefa para processamento
    if resultado["disponivel"] == 0:
        # Não tem nenhuma tarefa disponível
        return (False, None)
    else:
        # Retornou uma tarefa para processamento
        return (True, resultado["tarefa"])






# Atualiza status da tarefa do sapisrv
# ----------------------------------------------------------------------------------------------------------------------
def sapisrv_atualizar_status_tarefa(codigo_tarefa, codigo_situacao_tarefa, status, dados_relevantes=None,
                                    registrar_log=False):
    # Parâmetros
    param = {'codigo_tarefa': codigo_tarefa,
             'codigo_situacao_tarefa': codigo_situacao_tarefa,
             'status': status
             }

    metodo_invocar = 'get'
    if dados_relevantes is not None:
        dados_relevantes_json = json.dumps(dados_relevantes, sort_keys=True)
        param['dados_relevantes_json'] = dados_relevantes_json
        # Se tem atualização de dados_relevantes, invoca via post, pois url pode estourar no get
        metodo_invocar = 'post'

    # Invoca sapi_srv
    (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
        "sapisrv_atualizar_tarefa.php", param, registrar_log, metodo=metodo_invocar)

    # Registra em log
    if registrar_log:
        if sucesso:
            print_log_dual("Atualizado status no servidor: ", status)
        else:
            # Se der erro, registra no log e prossegue (tolerância a falhas)
            print_log_dual("Não foi possível atualizar status no servidor", msg_erro)

    # Retorna se teve ou não sucesso, e caso negativo a mensagem de erro
    return (sucesso, msg_erro)



# Atualiza status da tarefa do sapisrv
# ----------------------------------------------------------------------------------------------------------------------
def sapisrv_armazenar_texto(tipo_objeto, codigo_objeto, titulo, conteudo, registrar_log=False):
    # Parâmetros
    param = {'tipo_objeto': tipo_objeto,
             'codigo_objeto': codigo_objeto,
             'titulo': titulo,
             'conteudo': conteudo
             }

    metodo_invocar = 'post'

    # Invoca sapi_srv
    (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
        "sapisrv_armazenar_texto.php", param, registrar_log, metodo=metodo_invocar)

    # Registra em log
    if registrar_log:
        if sucesso:
            print_log_dual("Atualizado texto no servidor: ", titulo)
        else:
            # Se der erro, registra no log e prossegue (tolerância a falhas)
            print_log_dual("Não foi possível atualizar texto no servidor: ", msg_erro)

    # Retorna se teve ou não sucesso, e caso negativo a mensagem de erro
    return (sucesso, msg_erro)


# Invoca Sapi server (sapisrv)
# ----------------------------------------------------------------------------------------------------------------------
def sapisrv_chamar_programa(programa, parametros, abortar_insucesso=False, registrar_log=False, metodo='get'):
    # Adiciona o token aos parâmetros
    # Por equanto, vamos utilizar como token a versão da sapilib
    # Posteriormente, quando houver validação do software, substituir por algo mais elaborado
    parametros['execucao_nome_agente'] = _obter_parini('nome_agente')
    parametros['execucao_programa'] = _obter_parini('programa')
    parametros['execucao_programa_versao'] = _obter_parini('programa_versao')
    parametros['token'] = _obter_parini('servidor_token')

    # xxx
    try:
        if metodo == 'get':
            return _sapisrv_chamar_programa_get(programa, parametros, registrar_log)
        elif metodo == 'post':
            return _sapisrv_chamar_programa_post(programa, parametros, registrar_log)
        else:
            erro_fatal("sapisrv_chamar_programa: Método inválido: ", metodo)
    except BaseException as e:
        if abortar_insucesso:
            # As mensagens explicativas do erro já foram impressas
            erro_fatal("sapisrv_chamar_programa: Abortando após erro (abortar_insucesso=True)")
        else:
            print_log("sapisrv_chamar_programa: Repassando exception para chamador")
            raise

# Invoca Sapi server (sapisrv), contando com sucesso.
# Se ocorrer uma exceção, será exibido mensagem e abortado.
# Se o servidor responder com 'Sucesso=0', será exibo mensagem e aborta.
# Importante: 'Sucesso=0' não é necessariamente um erro. Pode ser uma condição normal, se os parâmetros ainda não foram
# validados, ou seja houve alguma mudança na situação dos dados no servidor.
# Utilize esta chamada apenas quando existe certeza que o resultado tem que SUCESSO
# ----------------------------------------------------------------------------------------------------------------------
def sapisrv_chamar_programa_sucesso_ok(programa, parametros, registrar_log=False):

    (sucesso, msg_erro, dados) = sapisrv_chamar_programa(
        programa, parametros, abortar_insucesso=True, registrar_log=registrar_log)
    if (not sucesso):
        erro_fatal("Resposta inesperada para ", programa, " => ", msg_erro)

    return dados


# Retorna o nome do ambiente de execução
# ----------------------------------------------------------------------------------------------------------------------
def obter_ambiente():
    return _obter_parini('nome_ambiente')


# ----------------------------------------------------------------------------------------------------------------------
# Funções de BAIXO Nível. Utilize o mínimo necessário, pois podem sofrer alterações sem aviso.
# As funções de baixo nível NÃO tem prefixo 'sapisrv'
# ----------------------------------------------------------------------------------------------------------------------


# Classes para geração de erro
# ---------------------------------------------
class SapiExceptionFalhaComunicacao(Exception):
    pass


class SapiExceptionProgramaDesautorizado(Exception):
    pass


class SapiExceptionAgenteDesautorizado(Exception):
    pass


class SapiExceptionGeral(Exception):
    pass





# Testa se cliente tem comunicação com servidor
# Retorna: Verdadeiro, Falso
# ----------------------------------------------------------------------
def testa_comunicacao_servidor_sapi(url_base):
    url = url_base + "/sapisrv_ping.php"
    print_log("Testando conexao com servidor SAPI em " + url)

    try:
        f = urllib.request.urlopen(url)
        resposta = f.read()
    except BaseException as e:
        print_log("Erro: ", str(e))
        return False

    # O resultado vem em 'bytes', exigindo uma conversão explícita para UTF8
    resposta = resposta.decode('utf-8')

    # Confere resposta
    if (resposta != "pong"):
        # Muito incomum...mostra na tela também
        print_tela_log("Servidor respondeu, em ", url, " porem com resposta inesperada: ", resposta)
        return False

    # Tudo bem
    print_log("Servidor respondeu")
    return True


# Utilizada por diversas rotinas, para garantir que a inicialização tenha sido efetuada com sucesso
# ----------------------------------------------------------------------------------------------------------------------
def assegura_inicializacao():
    if not Ginicializado:
        erro_fatal("Faltou invocar função sapisrv_inicializar. Revise seu código")
        sys.exit(1)

    # Tudo certo
    return


# Recupera valor do dicionário de ambiente
# ----------------------------------------------------------------------------------------------------------------------
def _obter_parini(campo):
    # Assegura que foi inicializado corretamente
    assegura_inicializacao()

    valor = Gparini.get(campo, None)

    if valor is None:
        erro_fatal("_obter_parini('" + str(campo) + "') => Parâmetro inválido. Revise código.")

    return str(valor)


# Processa resultado de uma chamada ao sapi_srv
# Se ocorrer algum erro, aborta
# ----------------------------------------------------------------------------------------------------------------------
def processar_resultado_ok(resultado, referencia=""):
    # O resultado vem em 'bytes',
    # exigindo uma conversão explícita para UTF8
    try:
        resultado = resultado.decode('utf-8')
    except BaseException as e:
        print_tela_log()
        print_tela_log("Falha na codificação UTF-8 da resposta de: ", referencia)
        print_tela_log("===== Pagina retornada =========")
        print_tela_log(resultado)
        print_tela_log("===== Fim da pagina =========")
        print_tela_log("Erro: ", str(e))
        print_tela_log("Verifique programa sapisrv")
        raise SapiExceptionGeral("Operação interrompida")

    # Processa pagina resultante em formato JSON
    try:

        # Carrega json.
        # Se houver algum erro de parsing, indicando que o servidor
        # não está legal, irá ser tratado no exception
        d = json.loads(resultado)

    except BaseException as e:
        print_tela_log()
        print_tela_log("Resposta invalida (não está no formato json) de: ", referencia)
        print_tela_log("===== Pagina retornada =========")
        print_tela_log(resultado)
        print_tela_log("===== Fim da pagina =========")
        print_tela_log("Erro: ", str(e))
        print_tela_log("Verifique programa sapisrv")
        raise SapiExceptionGeral("Operação interrompida")

    # Tudo certo
    return d


# =====================================================================================================================
# GET
# =====================================================================================================================

# Invoca Sapi server (sapisrv) utilizando GET
# ----------------------------------------------------------------------------------------------------------------------
def _sapisrv_chamar_programa_get(programa, parametros, registrar_log=False):
    # Monta URL
    parametros_formatados = urllib.parse.urlencode(parametros)
    url = _obter_parini('url_base') + programa + "?" + parametros_formatados

    # Registra em log
    if (registrar_log):
        print_log_dual(url)

    retorno = _sapisrv_get_sucesso(url)

    # Ajusta sucesso para booleano
    sucesso = False
    if (retorno["sucesso"] == "1"):
        sucesso = True

    # Outros dados
    msg_erro = retorno["msg_erro"]
    dados = retorno["dados"]

    # Retorna o resultado, decomposto nos seus elementos
    return (sucesso, msg_erro, dados)


# Chama sapisrv, esperando sucesso como resultado
# ----------------------------------------------------------------------
def _sapisrv_get_sucesso(url):
    # Chama servico
    d = sapisrv_get_ok(url)

    # Se não foi sucesso, aborta
    if (d["sucesso"] == "0"):
        print_tela_log("Erro inesperado reportado por: ", url)
        print_tela_log(d["msg_erro"])
        raise SapiExceptionGeral("Operação interrompida")

    # Retorna resultado
    return d


# Chama Sapi server (sapisrv) com get
# Explica erros e aborta
# ----------------------------------------------------------------------
def sapisrv_get_ok(url):
    # Invoca com GET
    try:
        f = urllib.request.urlopen(url)
        resultado = f.read()
    except BaseException as e:
        print_tela_log("Nao foi possivel conectar com:", url)
        print_tela_log("Erro: ", str(e))
        print_tela_log("Verifique configuracao de rede")
        # Gera exception para interromper execução de comando
        raise SapiExceptionGeral("Operação interrompida")

    referencia = "GET => " + url

    return processar_resultado_ok(resultado, referencia)


# Chama Sapi server (sapisrv) com get
# Se ocorrer algum erro, simplesmente deixa subir
# ----------------------------------------------------------------------
def _sapisrv_get_deprecated(url):
    # Substitui por mecanismo de repasse de exeção para o chamador

    # Chama url e le pagina resultante
    # conecta no servidor e envia URL (GET)
    f = urllib.request.urlopen(url)
    resultado = f.read()

    # O resultado vem em 'bytes', exigindo uma conversão explícita para UTF8
    resultado = resultado.decode('utf-8')

    # Carrega json.
    # Se houver algum erro de parsing, irá ser tratado no exception do chamador
    d = json.loads(resultado)

    # Tudo certo
    return d


# =====================================================================================================================
# POST
# =====================================================================================================================

# Invoca Sapi server (sapisrv) utilizando POST
# ----------------------------------------------------------------------
def _sapisrv_chamar_programa_post(programa, parametros, registrar_log=False):
    if (registrar_log):
        print_log_dual("Chamada POST para", programa)

    retorno = sapisrv_post_sucesso(programa, parametros)

    # Ajusta sucesso para booleano
    sucesso = False
    if (retorno["sucesso"] == "1"):
        sucesso = True

    # Outros dados
    msg_erro = retorno["msg_erro"]
    dados = retorno["dados"]

    # Registra resultado no log
    if (registrar_log):
        if sucesso:
            print_log_dual("Servidor respondeu com sucesso")
        else:
            print_log_dual("Servidor respondeu com falha: ", msg_erro)

    # Retorna o resultado, decomposto nos seus elementos
    return (sucesso, msg_erro, dados)


# Chama sapisrv via POST, esperando sucesso como resultado
# Se o retorno não for sucesso, aborta com erro fatal
# ----------------------------------------------------------------------
def sapisrv_post_sucesso(programa, parametros):
    # Chama servico
    d = sapisrv_post_ok(programa, parametros)

    # Se não foi sucesso, aborta
    if (d["sucesso"] == "0"):
        print_tela_log("Erro inesperado reportado por: ", programa, " via post")
        print_tela_log(d["msg_erro"])
        print("Parâmetros utilizados")
        raise SapiExceptionGeral("Operação interrompida")

    # Tudo certo
    return d


# Invoca Sapi server (sapisrv) com post
# Explica erros e aborta
# ----------------------------------------------------------------------
def sapisrv_post_ok(programa, parametros):
    try:
        resultado = _post(programa, parametros)
    except BaseException as e:
        print_tela_log("Falha na chamada de ", programa, " com POST")
        print_tela_log("Erro: ", str(e))
        print_tela_log("Verifique configuracao de rede")
        raise SapiExceptionGeral("Operação Interrompida")

    # Monta referência para exibição de erro
    referencia = "POST em " + programa
    # var_dump(resultado)
    # die('ponto619')

    return processar_resultado_ok(resultado, referencia)


# Invoca Sapi server (sapisrv) com post
# ----------------------------------------------------------------------
def sapisrv_post_deprecated(programa, parametros):
    # Substitui por retorno do exception para o chamador
    resultado = _post(programa, parametros)

    # Processa e devolve resultado, sem tratamento de erro
    resultado = resultado.decode('utf-8')
    d = json.loads(resultado)

    return d


# Efetua o post
# ----------------------------------------------------------------------
def _post(programa, parametros):
    # Formata parâmetros
    parametros_formatados = urllib.parse.urlencode(parametros)

    # Efetua conexão com servidor
    conn = http.client.HTTPConnection(_obter_parini('servidor_ip'), port=_obter_parini('servidor_porta'))

    # Parâmetros para POST
    headers = {"Content-type": "application/x-www-form-urlencoded",
               "Accept": "text/plain"}
    url_parcial = "/" + _obter_parini('servidor_sistema') + "/" + programa

    # Envia POST
    # conn.request("POST", "/setec3_dev/teste_post.php", parametrosFormatados, headers)
    conn.request("POST", url_parcial, parametros_formatados, headers)
    resultado = conn.getresponse()

    dados_resposta = resultado.read()

    return dados_resposta


# =====================================================================================================================
#
# =====================================================================================================================

# Tratamento para erro fatal
# ----------------------------------------------------------------------
def erro_fatal(*args):
    sys.stdout.write("Sapi Erro Fatal: ")
    print_ok(*args)
    print_ok("Para maiores informações, consulte o arquivo de log (sapi_log.txt)")
    sys.exit(1)


# Aborta programa
# ----------------------------------------------------------------------
def die(s):
    print(s)
    sys.exit(1)


# Dump "bonitinho" de uma variável
# ----------------------------------------------------------------------
def var_dump(x):
    print(type(x))
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(x)


# Limpa tela, linux e nt
# ----------------------------------------------------------------------
def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


# Valores dos bytes em hexa de um string
# ----------------------------------------------------------------------
def print_hex(s):
    r = ""
    for x in s:
        r = r + hex(ord(x)) + ":"
    print_ok(r)


# Substitui o convert_unicode no python3, que já é unicode nativo
# Converte todos os argumentos para string e concatena
# ----------------------------------------------------------------------
def concatena_args(*arg):
    s = ""
    for x in arg:
        # Se não for string, converte para string
        if not type(x) == str:
            x = str(x)
        # Concatena
        s = s + x

    return s


# Paleativo para resolver problema de utf-8 no Windows
# e esta confusão de unicode no python
# Recebe um conjunto de parâmetros string ou unicode
# Converte tudo para unicode e exibe
# Exemplo de chamada:
# print_ok(x, y, z)
# Atenção: Se tentar concatenar antes de chamar, pode dar erro de 
# na concatenação (exemplo: print_ok(x+y+z))
# Se isto acontecer, utilize o formato de multiplos argumentos (separados
# por virgulas)
# 
# Lógica para python 2 foi desativada.
# Mantendo chamadas ao wrapper da função print por precaução....
# para poder eventualmente compatibilizar um programa com python 2 e 3
# ----------------------------------------------------------------------
def print_ok(*arg):
    if (len(arg) == 0):
        print()
        return

    # Este código é para python 2
    # Como eu espero que tudo funcione em python 3, vamos desabilitá-lo
    # Se mais tarde for necessário algo em python2, terá que colocar
    # alguma esperteza aqui
    # print converte_unicode(*arg)

    # Python3, já tem suporte para utf-8...basta exibir
    print(*arg)


# Grava apenas em arquivo de log
# ----------------------------------------------------------------------
def _print_log_apenas(*arg):
    # Monta linha para gravação no log
    pid = os.getpid()
    hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Código para python2. Por enquanto desativado
    # linha="["+str(pid)+"] : "+hora+" : "+converte_unicode(*arg)

    linha = "[" + str(pid) + "] : " + hora + " : " + concatena_args(*arg)

    with codecs.open("sapi_log.txt", 'a', "utf-8") as sapi_log:
        sapi_log.write(linha + "\r\n")

    sapi_log.close()

    return linha


# Grava em arquivo de log
# ----------------------------------------------------------------------
def print_log(*arg):
    if (GlogDual):
        # Grava no arquivo de log e exibe na tela também
        print_log_dual(*arg)
    else:
        # Exibe apenas na tela
        _print_log_apenas(*arg)


# Grava no arquivo de log e exibe também na tela
# ----------------------------------------------------------------------
def print_log_dual(*arg):
    linha = _print_log_apenas(*arg)
    print(linha)


# Exibe mensagem recebida na tela
# e também grava no log
# ----------------------------------------------------------------------
def print_tela_log(*arg):
    print_ok(*arg)
    _print_log_apenas(*arg)


# Exibe mensagem recebida em destino variável,
# definido pelo primeiro parâmetro
# Exemplo: print_var('log tela', 'xxx') irá exibir na tela e gravar no log
# ----------------------------------------------------------------------
def print_var(print_destino, *arg):
    # imprime no log
    if 'log' in print_destino:
        print_log(*arg)
    # Exibe na tela
    if 'tela' in print_destino:
        print(*arg)


# Imprime se o primeiro argumento for verdadeiro
# ----------------------------------------------------------------------
def if_print_ok(exibir, *arg):
    # o primeiro campo tem que ser do tipo booleano
    # Um erro bastante comum é esquecer de passar este parâmetro
    # Logo, geramos um erro fatal aqui
    if type(exibir) != bool:
        print("Chamada inválida para if_print_ok, sem parâmetro de condição")
        print("Argumento: ", exibir, *arg)
        sys.exit()

    # O primeiro elemento deve ser um booleano
    # Se o primeiro parâmetro não for verdadeiro, não faz nada
    if (not exibir):
        return

    # Imprime, expurgando o primeiro elemento
    print(*arg)


# Converte para string para um formato hexa, para debug
# ----------------------------------------------------------------------
def string_to_hex(s):
    return ":".join("{:02x}".format(ord(c)) for c in s)


# Filtra apenas caracteres ascii de um string
# Os demais caracteres, substitui por '.'
# É útil quando não está conseguindo exibir um string na tela,
# em função da complexidade do esquema de encoding do python
# ----------------------------------------------------------------------
def filtra_apenas_ascii(texto):
    asc = ""
    for c in texto:
        # Se não for visível em ascii, troca para '.'
        if (ord(c) > 160):
            c = '.'
        asc = asc + c

    return asc


# Retorna verdadeiro se está rodando em Linux
# ----------------------------------------------------------------------
def esta_rodando_linux():
    if (os.name == 'posix'):
        # Linux
        return True

    if (os.name == 'nt'):
        # Windows
        return False

    # Algum outro sistema (talvez tenha que tratar os OSx se não vier
    # posix)
    # Por enquanto vamos abortar aqui, e ir refinando o código
    print_ok("Sistema operacional desconhecido : ", os.name)
    sys.exit(1)


# Verifica se usuário tem direito de root
# ----------------------------------------------------------------------
def tem_direito_root():
    if not esta_rodando_linux():
        return False

    if os.geteuid() != 0:
        return False

    # Ok, tudo certo
    return True


# Pergunta Sim/Não via via input() e retorna resposta
# - pergunta: String que será exibido para o usuário
# - default: (s ou n) resposta se usuário simplesmente digitar <Enter>. 
# O retorno é True para "sim" e False para não
def pergunta_sim_nao(pergunta, default="s"):
    validos = {"sim": True, "s": True,
               "não": False, "n": False}
    if default is None:
        prompt = " [s/n] "
    elif default == "s":
        prompt = " [S/n] "
    elif default == "n":
        prompt = " [s/N] "
    else:
        raise ValueError("Valor invalido para default: '%s'" % default)

    while True:
        sys.stdout.write(pergunta + prompt)
        escolha = input().lower()
        if default is not None and escolha == '':
            return validos[default]
        elif escolha in validos:
            return validos[escolha]
        else:
            sys.stdout.write("Responda com 's' ou 'n'\n")


# Funções agregadas na versão 0.5.3 (antes estavam em código separados)

# Separa pasta do nome do arquivo em um caminho
# Entrada:
#  Memorando_19317-16_Lava_Jato_RJ-12/item04Arrecadacao06/item04Arrecadacao06_imagem/item04Arrecadacao06.E01
# Saída:
#  - pasta: Memorando_19317-16_Lava_Jato_RJ-12/item04Arrecadacao06/item04Arrecadacao06_imagem
#  - nome_arquivo: item04Arrecadacao06.E01
# ----------------------------------------------------------------------
def decompoe_caminho(caminho):
    partes = caminho.split("/")

    nome_arquivo = partes.pop()
    pasta = "/".join(partes) + "/"

    return (pasta, nome_arquivo)


# Se pasta não existe, cria	
# =============================================================
def cria_pasta_se_nao_existe(pasta):
    # Se já existe, nada a fazer
    if os.path.exists(pasta):
        return

    # Cria pasta
    os.makedirs(pasta)

    # Confere se deu certo
    if os.path.exists(pasta):
        return

    # Algo inesperado aconteceu
    erro_fatal("Criação de pasta [", pasta, "] falhou")


# Determina tamanho da pasta
def tamanho_pasta(start_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size


# Converte Bytes para formato Humano
def converte_bytes_humano(size, precision=1):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', "PB", "EB", "ZB", "YB"]
    suffix_index = 0
    while size > 1024 and suffix_index < 8:
        suffix_index += 1  # increment the index of the suffix
        size /= 1024.0  # apply the division
    return "%.*f%s" % (precision, size, suffixes[suffix_index])


# Navega em uma pasta até o nível (level) de profundidade definido
def os_walklevel(some_dir, level=1):
    some_dir = some_dir.rstrip(os.path.sep)
    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root, dirs, files in os.walk(some_dir):
        yield root, dirs, files
        num_sep_this = root.count(os.path.sep)
        if num_sep + level <= num_sep_this:
            del dirs[:]


# Retorna True se existe storage montado no ponto_montagem
# =============================================================
def storage_montado(ponto_montagem):
    # Não existe ponto de montagem
    if not os.path.exists(ponto_montagem):
        return False

    # Verifica se storage está montando
    # Para ter certeza que o storage está montado, será verificado
    # se o arquivo storage_sapi_nao_excluir.txt
    # existe na pasta
    # Todo storage do sapi deve conter este arquivo na raiz
    arquivo_controle = ponto_montagem + 'storage_sapi_nao_excluir.txt'
    if not os.path.isfile(arquivo_controle):
        # Não existe arquivo de controle
        return False

    # Ok, tudo certo
    return True


# Verifica se storage já está montado.
# Se não estiver, monta	em Linux
# Retorna (True/False, mensagem_erro)
# =============================================================
def acesso_storage_linux(ponto_montagem, conf_storage):
    # Um storage do sapi sempre deve conter na raiz o arquivo abaixo
    arquivo_controle = ponto_montagem + 'storage_sapi_nao_excluir.txt'

    # Se pasta para ponto de montagem não existe, então cria
    if not os.path.exists(ponto_montagem):
        os.makedirs(ponto_montagem)

    # Confirma se pasta existe
    # Não deveria falhar em condições normais
    # Talvez falhe se estiver sem root
    if not os.path.exists(ponto_montagem):
        print_ok("Criação de pasta para ponto de montagem [", ponto_montagem, "] falhou")
        return False

    # Verifica se arquivo de controle existe no storage
    if os.path.isfile(arquivo_controle):
        # Tudo bem, storage montado e confirmado
        return True

    # Monta storage
    # O comando é algo como:
    # mount -t cifs //10.41.87.239/storage -o username=sapi,password=sapi /mnt/smb/gtpi_storage
    comando = (
        "mount -v -t cifs " +
        "//" + conf_storage["maquina_ip"] +
        "/" + conf_storage["pasta_share"] +
        " -o username=" + conf_storage["usuario"] +
        ",password=" + conf_storage["senha"] +
        " " + ponto_montagem
    )

    # print_ok(comando)
    os.system(comando)

    # Verifica se arquivo de controle existe no storage
    if os.path.isfile(arquivo_controle):
        # Tudo certo, montou
        return True
    else:
        print_ok(comando)
        print_ok("Após montagem de storage, não foi encontrado arquivo de controle[", arquivo_controle, "]")
        print_ok("Ou montagem do storage falhou, ou storage não possui o arquivo de controle.")
        print_ok("Se for este o caso, inclua na raiz o arquivo de controle com qualquer conteúdo.")
        return False


# Verifica se storage já está montado. Se não estiver, monta.
# Retorna:
# - Sucesso: Se montagem foi possível ou não
# - ponto_montagem: Caminho para montagem
# - mensagem_erro: Caso tenha ocorrido erro na montagem
# =============================================================
def acesso_storage_windows(conf_storage, utilizar_ip=False):
    # var_dump(conf_storage)
    # die('ponto586')

    # No caso do windows, vamos utilizar o nome netbios
    if utilizar_ip:
        maquina = conf_storage["maquina_ip"]
    else:
        maquina = conf_storage["maquina_netbios"]

    # Ponto de montagem implícito
    # Não vou mapear para uma letra aqui, pois pode dar conflito
    # com algo mapeado pelo usuário
    # Logo, o caminho do storage é o ponto de montagem
    # "\\" = "\", pois '\' é escape
    caminho_storage = (
        "\\" + "\\" + maquina +
        "\\" + conf_storage["pasta_share"]
    )
    ponto_montagem = caminho_storage + "\\"
    # print_log_dual(ponto_montagem)
    arquivo_controle = ponto_montagem + 'storage_sapi_nao_excluir.txt'

    # print_ok(arquivo_controle)
    # die('ponto531')
    # Se já está montado
    if os.path.exists(caminho_storage):
        # Confere se existe arquivo indicativo de storage bem montado
        # die('ponto603')
        if os.path.isfile(arquivo_controle):
            # Sucesso: Montagem do storage confirmada
            # die('ponto606')
            return True, ponto_montagem, ""
        else:
            # Falha
            # die('ponto610')
            print_ok("Storage está montado em " + caminho_storage)
            print_ok("Contudo o mesmo não contém arquivo [" + arquivo_controle + "]")
            print_ok("Isto pode indicar que o storage não foi montado com sucesso, ou que está corrompido")
            return False, ponto_montagem, "Storage sem arquivo de controle"

    # Ainda não está montado
    print_ok("- Montando storage em: " + caminho_storage)

    # Conecta no share do storage, utilizando net use.
    # Exemplo:
    # net use \\10.41.87.239\storage /user:sapi sapi
    # Para desmontar (para teste), utilizar:
    # net use \\10.41.87.239\storage /delete
    comando = (
        "net use " + caminho_storage +
        " /user:" + conf_storage["usuario"] +
        " " + conf_storage["senha"]
    )

    print_ok("Conectando com storage")
    print_ok(comando)
    subprocess.call(comando, shell=True)

    # Verifica se montou
    if not os.path.exists(caminho_storage):
        # Falha
        print_ok("Montagem de storage falhou [" + caminho_storage + "]")
        return False, ponto_montagem, "Falhou na montagem"

    # Confere se existe arquivo indicativo de storage bem montado
    if not os.path.isfile(arquivo_controle):
        # Falha
        print_ok("Storage foi montado em " + caminho_storage)
        print_ok("Contudo não foi localizado arquivo [" + arquivo_controle + "]")
        print_ok("Isto pode indicar que o storage não foi montado com sucesso, ou está corrompido")
        return False, ponto_montagem, "Storage não possui arquivo de controle"

    # Sucesso: Montado e confirmado ok
    return True, ponto_montagem, ""

# ---------------------------------------------------------------------------------------------------------------------
# Funções relacinadas com a interface em linha de comando (console)
# Possuem prefixo console_
# ---------------------------------------------------------------------------------------------------------------------

# Chama função geral, e intercepta CTR-C
# ----------------------------------------------------------------------------------------------------------------------
def console_executar_tratar_ctrc(funcao, *args):
    try:
        return(funcao( *args ))
    except KeyboardInterrupt:
        print()
        print("Operação interrompida pelo usuário")
        return False


# Chama função de menu e intercepta CTR-C, gerando comando de encerramento normal (*qq)
# ----------------------------------------------------------------------------------------------------------------------
def console_receber_comando(menu_comando):
    try:
        return _receber_comando(menu_comando)
    except KeyboardInterrupt:
        print("Para encerrar, utilize comando *qq")
        return (None, "")
        #return ("*qq", "")


# Recebe e confere a validade de um comando de usuário
# ----------------------------------------------------------------------------------------------------------------------
def _receber_comando(menu_comando):

    comandos = menu_comando['comandos']
    cmd_navegacao = menu_comando['cmd_navegacao']
    cmd_item = menu_comando['cmd_item']
    cmd_geral = menu_comando['cmd_geral']

    comando_ok = False
    comando_recebido = ""
    argumento_recebido = ""
    while not comando_ok:
        print()
        entrada = input("Comando (?=ajuda): ")
        entrada = entrada.lower().strip()
        lista_partes_comando = entrada.split(" ", 2)
        comando_recebido = ""
        if (len(lista_partes_comando) >= 1):
            comando_recebido = lista_partes_comando[0]
        argumento_recebido = ""
        if (len(lista_partes_comando) >= 2):
            argumento_recebido = lista_partes_comando[1]

        if comando_recebido in comandos:
            # Se está na lista de comandos, ok
            comando_ok = True
        elif comando_recebido.isdigit():
            # um número é um comando válido
            comando_ok = True
        elif (comando_recebido == "H" or comando_recebido == "?"):
            # Exibe ajuda para comando
            print()
            print("Navegacao:")
            print("----------")
            print('<ENTER> : Exibe lista de tarefas atuais (sem Refresh no servidor)')
            for key in cmd_navegacao:
                print(key.upper(), " : ", comandos[key])
            print()

            print("Processamento da tarefa corrente (marcada com =>):")
            print("--------------------------------------------------")
            for key in cmd_item:
                print(key.upper(), " : ", comandos[key])
            print()

            print("Comandos gerais:")
            print("----------------")
            for key in cmd_geral:
                print(key.upper(), " : ", comandos[key])
        elif (comando_recebido == ""):
            # print("Para ajuda, digitar comando 'h' ou '?'")
            return ("", "")
        else:
            if (comando_recebido != ""):
                print("Comando (" + comando_recebido + ") inválido")
                print("Para ajuda, digitar comando 'h' ou '?'")

    return (comando_recebido, argumento_recebido)



# Sanitiza strings em UTF8, substituindo caracteres não suportados pela codepage da console do Windows por '?'
# Normalmente a codepage é a cp850 (Western Latin)
# Retorna a string sanitizada e a quantidade de elementos que forma recodificados
def console_sanitiza_utf8(dado):
    #
    codepage = sys.stdout.encoding

    # String => ajusta, trocando caracteres não suportados por '?'
    if isinstance(dado, str):
        # Isto aqui é um truque sujo, para resolver o problema de exibir caracteres UTF8 em console do Windows
        # com configuração cp850
        saida = dado.encode(codepage, 'replace').decode(codepage)
        # Verifica se a recodificação introduziu alguma diferença
        qtd = 0
        if saida != dado:
            qtd = 1
        return (saida, qtd)

    # Dicionário,
    if isinstance(dado, dict):
        saida = dict()
        qtd = 0
        for k in dado:
            (saida[k], q) = console_sanitiza_utf8(dado[k])
            qtd += q
        return (saida, qtd)

    # Lista
    if isinstance(dado, list):
        saida = list()
        qtd = 0
        for v in dado:
            (novo_valor, q) = console_sanitiza_utf8(v)
            saida.append(q)
            qtd += q
        return (saida, qtd)

    # Qualquer outro tipo de dado (numérico por exemplo), retorna o próprio valor
    # Todo: Será que tem algum outro tipo de dado que precisa tratamento!?...esperar dar erro
    saida = dado
    return (saida, 0)


# Faz dump formatado de um objeto qualquer na console
# --------------------------------------------------------------------------------
def console_dump_formatado(d, largura_tela=129):

    # Sanitiza, para exibição na console
    (d_sanitizado, qtd_alteracoes) = console_sanitiza_utf8(d)

    # Exibe formatado
    pp = pprint.PrettyPrinter(indent=4, width=largura_tela)
    pp.pprint(d_sanitizado)

    if qtd_alteracoes > 0:
        print()
        print("#Aviso: Para viabilizar a exibição acima na console, foram efetuadas", qtd_alteracoes,
              "substituições de caracteres especiais por '?'")

    return


# ---------------------------------------------------------------------------------------------------------------------
# Classe para tratamento de janelas gráficas
# ---------------------------------------------------------------------------------------------------------------------
class JanelaTk(tkinter.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.pack()

    def selecionar_arquivo(self, filetypes=None):

        if filetypes is None:
            filetypes = [('All files', '*.*'),
                          ('ODT files', '*.odt'),
                          ('CSV files', '*.csv')]

        self.file_name = tkinter.filedialog.askopenfilename(filetypes=filetypes)

        # self.file_name = tkinter.filedialog.askopenfilename(filetypes=([('All files', '*.*'),
        #                                                                 ('ODT files', '*.odt'),
        #                                                                 ('CSV files', '*.csv')]))
        return self.file_name

    def selecionar_pasta(self):
        self.directory = tkinter.filedialog.askdirectory()
        return self.directory


def tk_get_clipboard():
    try:
        root = tkinter.Tk()
        root.withdraw()
        clip = root.clipboard_get()
        root.destroy()
    except BaseException as e:
        print("Nao foi possivel recuperado dados do clipboard: ", e)
        clip = ""

    return clip





# *********************************************************************************************************************
# *********************************************************************************************************************
#                  FINAL DO SAPI_LIB
# *********************************************************************************************************************
# *********************************************************************************************************************
