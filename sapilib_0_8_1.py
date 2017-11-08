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
#   0.7.2 - Tratamento para execução em background.
#
# *********************************************************************************************************************
# *********************************************************************************************************************
#                  INICIO DO SAPI_LIB
# *********************************************************************************************************************
# *********************************************************************************************************************

# Módulos utilizados
import codecs
import copy
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
import time
import traceback
from tkinter import filedialog
import ssl
import shutil
import psutil
from optparse import OptionParser
import webbrowser
import tempfile

# Desativa a verificação de certificado no SSL
ssl._create_default_https_context = ssl._create_unverified_context


# ---------- Constantes (na realidade variáveis Globais) ------------
Gversao_sapilib = "0.8.1a"

# Valores de codigo_situacao_status (para atualizar status de tarefas)
# --------------------------------------------------------------------
GManterSituacaoAtual = 0
GAguardandoPCF = 1
GSemPastaNaoIniciado = 1
GAguardandoProcessamento = 5
GFilaCriacaoPasta = 7
GAbortou = 8
GFilaExclusao = 9
GDespachadoParaAgente = 20
GPastaDestinoCriada = 30
GEmExclusao = 35
GEmAndamento = 40
GTableauExecutando = 50
GIpedExecutando = 60
GIpedFinalizado = 62
GIpedHashCalculado = 65
GIpedMulticaseAjustado = 68
GFinalizadoComSucesso = 95
# Intervalos de status
# Intervalo de status que uma tarefa está executando
# Isto aqui pode dar problema, se forem criadas situações na base do SETEC3 fora deste intervalo
Gexecutando_intervalo_ini=20
Gexecutando_intervalo_fim=70

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
    'servidor_sistema': 'setec3_dev',
    'url_base_s3': 'http://10.41.84.5/setec3_dev/',
    'url_base_siscrim': 'https://desenvolvimento.ditec.pf.gov.br/sistemas/criminalistica/'
}
# --- Produção ---
Gconf_ambiente['prod'] = {
    'nome_ambiente': 'PRODUCAO',
    'servidor_protocolo': 'https',
    'ips': ['10.41.84.5', '10.41.84.5'],
    'servidor_porta': 443,
    'servidor_sistema': 'setec3',
    'url_base_s3': 'https://setecpr.dpf.gov.br/setec3/',
    'url_base_siscrim': 'https://ditec.pf.gov.br/sistemas/criminalistica/'
}

# Definido durante inicializacao
# --------------------------------
Ginicializado = False
Gparametros_usuario_ja_processado = False
Gparini = dict()  # Parâmetros de inicialização

# Controle de mensagens/log
GlogDual = False

# Tempo de espera de resposta do servidor http (SETEC3)
# Tempo de espera padrão
Ghttp_timeout_padrao=60
# Tempo de espera corrente
Ghttp_timeout_corrente=copy.copy(Ghttp_timeout_padrao)

# Variáveis globais alteradas durante a execução do programa
# Serão reapassada para processos filhos
# -------------------------------------------------------
# Storages nos quais foi feita conexão para cópia de dados
Gdic_storage=dict()
Gdrive_mapeado=dict()

# Multiprocessamento
# -------------------------------
Gpfilhos = dict()  # Processos filhos

# Storage, verificacação
Garquivo_controle='storage_sapi_nao_excluir.txt'


# Estrutura do storage
# --------------------
# Todos os storages tem que ter a mesma estrutura
# Caso a raiz seja diferente, dever executar com o parâmetro --raiz_storage
# A estrutura do servidor é fixa
# E:\sistema
# E:\tableau
# E:\Memorandoxxxx
# E:\Memorandoyyy
# As variáveis abaixo ajustam o caminho para chegar em diversas pastas
# Default para storage
Gdefault_raiz_storage = "E:\\"

# Configuração de Tela
# Todo: transferir para o sapicli
#-------------------------------------
Glargura_tela = 129


# Aquisição de dados
# ------------------------------------
# Percentual máximo de erros de leitura considerado aceitável. Acima disso gerará aviso
GlimitePercentualErroLeitura = 1

# ================================================================================
# Robocopy
# Resultado do Robocopy
# ================================================================================
'''
Fonte: https://ss64.com/nt/robocopy-exit.html
exit code      Significado
================================================================================
0×00   0       No errors occurred, and no copying was done.
               The source and destination directory trees are completely synchronized.

0×01   1       One or more files were copied successfully (that is, new files have arrived).

0×02   2       Some Extra files or directories were detected. No files were copied
               Examine the output log for details.

0×03   3       (2+1) Some files were copied. Additional files were present. No failure was encountered.

0×04   4       Some Mismatched files or directories were detected.
               Examine the output log. Housekeeping might be required.

0×05   5       (4+1) Some files were copied. Some files were mismatched. No failure was encountered.

0×06   6       (4+2) Additional files and mismatched files exist. No files were copied and no failures were encountered.
               This means that the files already exist in the destination directory

0×07   7       (4+1+2) Files were copied, a file mismatch was present, and additional files were present.

0×08   8       Some files or directories could not be copied
               (copy errors occurred and the retry limit was exceeded).
               Check these errors further.

0×10  16       Serious error. Robocopy did not copy any files.
               Either a usage error or an error due to insufficient access privileges
               on the source or destination directories.
'''

Grobocopy_texto_return_code = dict()
Grobocopy_texto_return_code[0] = "Robocopy finalizado com sucesso. Nenhum arquivo foi copiado (mas está sincronizado)."
Grobocopy_texto_return_code[1] = "Robocopy finalizado com sucesso. Arquivos foram copiados."
Grobocopy_texto_return_code[2] = "Some Extra files or directories were detected. No files were copied. Examine the output log for details."
Grobocopy_texto_return_code[3] = "(2+1) Some files were copied. Additional files were present. No failure was encountered."
Grobocopy_texto_return_code[4] = "Some Mismatched files or directories were detected. Examine the output log. Housekeeping might be required."
Grobocopy_texto_return_code[5] = "(4+1) Some files were copied. Some files were mismatched. No failure was encountered."
Grobocopy_texto_return_code[6] = "(4+2) Additional files and mismatched files exist. No files were copied and no failures were encountered. This means that the files already exist in the destination directory."
Grobocopy_texto_return_code[7] = "(4+2+1) Files were copied, a file mismatch was present, and additional files were present."
Grobocopy_texto_return_code[8] = "Some files or directories could not be copied (copy errors occurred and the retry limit was exceeded)."
Grobocopy_texto_return_code[16] = "Serious error. Robocopy did not copy any files. Either a usage error or an error due to insufficient access privileges on the source or destination directories."


# =====================================================================================================================
# Funções de ALTO NÍVEL relacionadas com acesso ao servidor (sapisrv_*)
#
# Todas as funções de alto nível possuem prefixo 'sapisrv'
#
# Utilize preferencialmente estas funções, pois possuem uma probabilidade menor de alteração na interface (parâmetros).
# Caso novos parâmetros sejam incluídos, serão opcionais.
# =====================================================================================================================

# ----------------------------------------------------------------------------------------------------------------------
# Multiprocessamento
# ----------------------------------------------------------------------------------------------------------------------
def registra_processo_filho(ix, proc):
    global Gpfilhos

    # Armazena processo na lista processos filhos
    Gpfilhos[ix] = proc



# ----------------------------------------------------------------------------------------------------------------------
# Parâmetros de configuração
# ----------------------------------------------------------------------------------------------------------------------
def set_parini(chave, valor):
    global Gparini
    Gparini[chave] = valor
    # Retorna o próprio valor, para ser utilizado na sequencia
    return valor

def get_parini(chave, default=None):
    global Gparini

    valor=Gparini.get(chave,None)
    if valor is None:
        valor=default

    return valor

# Recupera valor do dicionário de ambiente, neste caso um valor obrigatório
# ----------------------------------------------------------------------------------------------------------------------
def _obter_parini_obrigatorio(campo):
    # Assegura que foi inicializado corretamente
    assegura_inicializacao()

    valor = Gparini.get(campo, None)

    if valor is None:
        erro_fatal("_obter_parini('" + str(campo) + "') => Parâmetro inválido. Revise código.")

    return str(valor)


# ----------------------------------------------------------------------------------------------------------------------
# Invocando o browser
# ----------------------------------------------------------------------------------------------------------------------
def abrir_browser_setec3_sapi():
    # Monta url
    url = urllib.parse.urljoin(get_parini('url_base_s3'),"sapi_pcf.php")
    webbrowser.open(url)
    print("- Aberto no browser default a página sapi do usuário")
    debug("Aberto URL", url)


def abrir_browser_setec3_exame(codigo_solicitacao_exame_siscrim):
    # Monta url
    url = urllib.parse.urljoin(get_parini('url_base_s3'),"sapi_exame.php?codigo="+str(codigo_solicitacao_exame_siscrim))
    webbrowser.open(url)
    print("- Aberto no browser default a página de exame sapi da solicitação de exame corrente.")
    debug("Aberto URL",url)

def abrir_browser_siscrim(pagina_parametros, descricao_pagina=None):
    #pagina_parametros="controle_documento.php?action=elaborar&objeto_pai=33316600&categoria=2"
    url = urllib.parse.urljoin(get_parini('url_base_siscrim'),pagina_parametros)
    webbrowser.open(url)
    if descricao_pagina is not None:
        print("- Foi aberto no browser padrão: ", descricao_pagina)
    debug("Invocado URL no browser padrão:", url)

def abrir_browser_siscrim_documento(codigo_documento):
    # Monta url
    url = urllib.parse.urljoin(get_parini('url_base_siscrim'),"documento.php?acao=exibir&codigo="+str(codigo_documento))
    webbrowser.open(url)
    print("- Aberto no browser default página de consulta ao documento indicado")
    debug("Aberto URL", url)

def abrir_browser_siscrim_modelo_usuario(codigo_documento):
    # Monta url
    url = urllib.parse.urljoin(get_parini('url_base_siscrim'),"modelo_usuario.php?acao=selecionar&codigo_documento="+str(codigo_documento))
    webbrowser.open(url)
    print("- Aberto no browser default página de geração de modelo do usuário para documento indicado")
    debug("Aberto URL", url)



# ----------------------------------------------------------------------------------------------------------------------
# Modos de trabalho
# ----------------------------------------------------------------------------------------------------------------------
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

def ligar_modo_debug():
    set_parini('debug', True)
    print_log("Modo debug foi ligado")

def desligar_modo_debug():
    set_parini('debug', False)
    print_log("Modo debug foi desligado")


# Se estiver em modo debug, registra no log
def debug(*arg):
    if modo_debug():
        print_log("DEBUG:", *arg)

# ----------------------------------------------------------------------------------------------------------------------
# Funções relacionadas com arquivos
# ----------------------------------------------------------------------------------------------------------------------
# Recupera a data de modificação de um arquivo
def obter_arquivo_data_modificacao(filename):
    t = os.path.getmtime(filename)
    return datetime.datetime.fromtimestamp(t)


# ----------------------------------------------------------------------------------------------------------------------
# Comunicação entre processos
# ----------------------------------------------------------------------------------------------------------------------
# Diferentement do fork, um subprocesso do python não herda nenhum conteúdo de variáveis no instante de criação
# do novo processo. O novo processo nasce limpo, como se fosse um programa que iniciou a execução
# Logo, para pode passar alguns dados de estado da sapilib para o processo filho, é necessário fazer isto explicitamente

# Fornece dados que serão passados para processo filho
# -----------------------------------------------------
def obter_dados_para_processo_filho():

    # Monta um estrutura com dados que serão repassados para o processo filho
    # Desta forma, pai e filhos compartilham o estado inicial

    r = dict()
    r['Gdic_storage']   =Gdic_storage
    r['Gparini']        =Gparini

    return r

# Restaura dados globais no processo filho
# -----------------------------------------------------
def restaura_dados_no_processo_filho(r):
    global Gdic_storage
    global Gparini

    Gdic_storage    =r['Gdic_storage']
    Gparini         =r['Gparini']
    return




# ----------------------------------------------------------------------------------------------------------------------
# Dados para deployment
# ----------------------------------------------------------------------------------------------------------------------
def obter_info_deployment():

    r = dict()
    r["storage_deployment"]=get_parini("storage_deployment")
    r["pasta_deployment_origem"]=get_parini("pasta_deployment_origem")

    return r


# ----------------------------------------------------------------------------------------------------------------------
# Gerais
# ----------------------------------------------------------------------------------------------------------------------
# Faz um pausa por alguns segundos
# Dependendo de parâmetro, ignora a pausa
def dormir(tempo, rotulo=None):
    texto="Dormindo por " + str(tempo) + " segundos"
    if rotulo is not None:
        texto = rotulo + ": " + texto
    print_log(texto)
    time.sleep(tempo)

# ----------------------------------------------------------------------------------------------------------------------
# Parâmetros de configuração da comunicação http
# ---------------------------------------------------------------------------
def set_http_timeout(timeout):
    global Ghttp_timeout_corrente
    Ghttp_timeout_corrente = timeout
    debug("Timeout http modificado para: ", Ghttp_timeout_corrente)

def reset_http_timeout():
    global Ghttp_timeout_corrente
    Ghttp_timeout_corrente = Ghttp_timeout_padrao
    debug("Timeout http restaurado para padrão: ", Ghttp_timeout_corrente)

# Processa parâmetros de chamada
def sapi_processar_parametros_usuario():

    # Atualiza estas globais
    global Gparametros_usuario_ja_processado

    # Só processa os parâmetros do usuário uma vez
    if Gparametros_usuario_ja_processado:
        return

    parser = OptionParser()

    if parser:
        parser.add_option("--debug",
                          action="store_true", dest="debug", help="Informações adicionais para debug")
        parser.add_option("--background",
                          action="store_true", dest="background", help="Mensagens serão gravadas apenas em log")
        parser.add_option("--dual",
                          action="store_true", dest="dual", help="Mensagens de log são exibidas também na tela")
        parser.add_option("--logfile",
                          action="store", dest="logfile", help="Arquivo para registro de log")
        parser.add_option("--logdir",
                          action="store", dest="logdir", help="Pasta onde será criado o arquivo de log. Pasta deve existir.")
        parser.add_option("--raiz_storage",
                          action="store", dest="raiz_storage", help="Pasta de raiz do storage (default E:/)")

        (options, args) = parser.parse_args()
        # print(options)
        set_parini('background',False)

        if options.background:
            set_parini('background', True)

        if options.dual:
            set_parini('dual', True)
            ligar_log_dual()


        if options.logdir:
            set_parini('logdir',options.logdir)

        if options.logfile:
            set_parini('logfile', options.logfile)

        if options.raiz_storage:
            set_parini('raiz_storage', options.raiz_storage)
        else:
            # Default
            set_parini('raiz_storage', Gdefault_raiz_storage)

        # Feedback dos parâmetros selecionados
        if options.background:
            print_log(
                "--background: Entrando em modo background. Saída normal será armazenada apenas em log. Erros fatais poderão ser exibidos na saída padrão.")

        if options.debug:
            ligar_modo_debug()

    Gparametros_usuario_ja_processado = True


# Baixa programa do servidor e substitui na pasta de execução
# Se obtiver sucesso, retorna o caminho para o programa atualizado
# Caso contrário, retorna False
def atualizar_programa(nome_programa):

    print_log("Efetuando atualização do programa ",nome_programa)
    #
    # Adiciona .py no nome do programa
    nome_programa = nome_programa + ".py"

    # Baixa arquivo do programa
    try:
        param = {'arquivo': nome_programa}

        (sucesso, msg_erro, conteudo_arquivo)=sapisrv_chamar_programa(
            programa="sapisrv_download.php",
            parametros=param,
            abortar_insucesso=False,
            registrar_log=True
        )

        if not sucesso:
            print_log("Falha no download do arquivo arquivo: ", msg_erro)
            return False

    except BaseException as e:
        print_log_dual("[226] Download de arquivo falhou: ", e)
        return False

    # Pasta em que será feita a atualização
    pasta_destino=get_parini('pasta_execucao')
    #Apenas para teste, para não sobrepor o programa na pasta de desenvolvimento
    if ambiente_desenvolvimento():
        # No ambiente de desenvovlimento, não faz a atualização na pasta de execução, pois isto poderia sobrepor o programa
        # em desenvolvimento
        print_log("Trocando para pasta de execução sapi_dev, pois está no ambiente de desenvolvimento")
        pasta_destino="c:\\sapi_dev"

    # Grava conteúdo do arquivo na pasta de destino
    caminho_programa_tmp=os.path.join(pasta_destino,"tmp_"+nome_programa)


    # Grava o arquivo recuperado
    try:
        # Assegura que arquivo tmp não existe
        if os.path.isfile(caminho_programa_tmp):
            os.remove(caminho_programa_tmp)
            if os.path.isfile(caminho_programa_tmp):
                print_log_dual("Não foi possível excluir arquivo tmp:",caminho_programa_tmp)
                return False

        # Grava o conteúdo baixado em tmp
        with codecs.open(caminho_programa_tmp, 'w', "utf-8") as novo_arquivo:
            novo_arquivo.write(conteudo_arquivo)

        print_log("Arquivo temporário gravado com sucesso em ",caminho_programa_tmp)

    except BaseException as e:
        print_log_dual("[256] Não foi possível atualizar o arquivo no sistema operacional: ", e)
        return False


    # Move o atual para old
    # e renomeia o tmp para torná-lo o programa atual
    caminho_programa_atual=os.path.join(pasta_destino, nome_programa)
    caminho_programa_old=os.path.join(pasta_destino, "old_"+nome_programa)
    try:
        # Exlclui arquivo old
        if os.path.isfile(caminho_programa_old):
            os.remove(caminho_programa_old)
            if os.path.isfile(caminho_programa_old):
                print_log_dual("Não foi possível excluir arquivo old:",caminho_programa_old)
                return False

        # Renomeia programa atual para old
        if os.path.isfile(caminho_programa_atual):
            os.rename(caminho_programa_atual, caminho_programa_old)

        # Renomeia o arquivo tmp para atual
        os.rename(caminho_programa_tmp, caminho_programa_atual)

    except BaseException as e:
        print_log_dual("[281] Não foi efetuar ajustes finais de nome: ", e)
        return False

    # Sucesso
    print_log("Arquivo atualizado (renomeado) com sucesso para: ", caminho_programa_atual)
    return caminho_programa_atual

# Função de inicialização para utilização do sapisrv:
# - nome_programa (obrigatório) : Nome do programa em execução
# - versao_programa (obrigatório): Versão do programa em execução
# - nome_agente : Default: hostname
# - ambiente : 'desenv' ou 'prod'
#              Default: 'desenv' se houver arquivo 'desenvolvimento_nao_excluir.txt' na pasta. Caso contrário, 'prod'
# ----------------------------------------------------------------------------------------------------------------------
def _sapisrv_inicializar_internal(nome_programa, versao, nome_agente=None, ambiente=None, auto_atualizar=False,
                                  nome_arquivo_log=None, label_processo=None):

    # Atualiza estas globais
    global Ginicializado

    # Se já foi inicializado, despreza, pois só pode haver uma inicialização por execução
    # Desabilitado: Deixa inicializar sempre, pois programas de execução continua
    # como o sapi_iped necessitam verificar se houve alguma mudança de versão para se atualizarem
    #if Ginicializado:
    #    return

    # Processa parâmetros do usuário, caso isto ainda não tenha sido feito
    sapi_processar_parametros_usuario()

    debug('_sapisrv_inicializar_internal parâmetros => ',
          'nome_programa:', nome_programa,
          'versao:', versao,
          'nome_agente:', nome_agente,
          'ambiente:', ambiente,
          'auto_atualizar:', auto_atualizar,
          'nome_arquivo_log:', nome_arquivo_log,
          'label_processo:', label_processo
          )

    # Nome do programa
    if nome_programa is None:
        # obrigatório
        erro_fatal("Nome do programa não informado")
    set_parini('programa', nome_programa)

    # Vesão do programa
    if versao is None:
        # Obrigatório
        erro_fatal("Versão não informada")
    set_parini('programa_versao', versao)

    # Nome do Agente
    if nome_agente is None:
        # Default
        nome_agente = socket.gethostbyaddr(socket.gethostname())[0]
    # Sanitiza
    nome_agente=nome_agente.replace(".dpfsrpr","")
    set_parini('nome_agente', nome_agente)

    # Nome do arquivo de log
    if nome_arquivo_log is not None:
        renomear_arquivo_log_default(nome_arquivo_log)

    # Label do processo será utilizado para rotular as linhas de log
    if label_processo is not None:
        set_parini('label_log', label_processo)

    # Pasta de execução do programa
    pasta_execucao=os.path.abspath(os.path.dirname(sys.argv[0]))
    set_parini('pasta_execucao', pasta_execucao)

    # Ambiente
    if ambiente is None:
        # Verifica se na pasta que está sendo executado existe arquivo desenvolvimento_nao_excluir.txt
        # Se existir, aceita isto como um sinalizador que está rodando em ambiente de desenvolvimento
        arquivo_desenvolvimento = os.path.join(pasta_execucao,'desenvolvimento_nao_excluir.txt')
        if os.path.isfile(arquivo_desenvolvimento):
            print_log("Detectado existência de arquivo que indica que está em ambiente de desenvolvimento")
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
            set_parini('ambiente', ambiente)
            set_parini('nome_ambiente', amb['nome_ambiente'])
            # Servidor
            set_parini('servidor_protocolo', amb['servidor_protocolo'])
            set_parini('servidor_ip', ip)
            set_parini('servidor_porta', amb['servidor_porta'])
            set_parini('servidor_sistema', amb['servidor_sistema'])
            set_parini('url_base', url_base)
            set_parini('url_base_s3', amb['url_base_s3'])
            set_parini('url_base_siscrim', amb['url_base_siscrim'])
            # Como token, por equanto será utilizado um valor fixo
            set_parini('servidor_token', 'token_fixo_v0_7')
            # ok
            break

    if not conectou:
        # Gera execeção, para deixar chamador decidir o que fazer
        raise SapiExceptionFalhaComunicacao("Nenhum servidor respondeu.")

    # Inicializado
    Ginicializado = True


    debug("Inicializado SAPILIB Agente=", _obter_parini_obrigatorio('nome_agente'),
              " Ambiente=", _obter_parini_obrigatorio('nome_ambiente'),
              " Servidor=", _obter_parini_obrigatorio('servidor_ip'),
              " arquivo_log=", obter_nome_arquivo_log())

    # Verifica se versão do programa está habilitada a rodar, através de chamada ao servidor
    # simulação de erros:
    # raise SapiExceptionAgenteDesautorizado("Máquina com ip 10.41.58.58 não autorizada para executar tal programa")
    # raise SapiExceptionProgramaDesautorizado("Este programa xxxx na versão kkkk não está autorizado")

    try:
        (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
            programa="sapisrv_solicitar_acesso.php",
            parametros = {}
        )
    except BaseException as e:
        print_log("Erro na verificação na obtenção de acesso ao servidor: " + str(e))
        raise SapiExceptionProgramaDesautorizado('Não foi possível concluir solicitação de acesso')

    # Chamada respondida com falha
    if not sucesso:
        print_log_dual("sapisrv_solicitar_acesso.php: ", msg_erro)
        raise SapiExceptionProgramaDesautorizado('Não foi possível concluir solicitação de acesso')

    # Armazena servidor de deployment
    set_parini("storage_deployment", resultado.get('storage_deployment', None))
    set_parini("pasta_deployment_origem", resultado.get('pasta_deployment_origem', None))

    # Trata acesso negado
    if (resultado['acesso_concedido']==0):
        print_log(resultado['explicacao'])
        tipo_erro=resultado['tipo_erro']
        if tipo_erro=='VersaoDesatualizada':
            if auto_atualizar:
                caminho_programa_atualizado=atualizar_programa(nome_programa)
                if caminho_programa_atualizado:
                    # Tudo certo. Chamador reconhecerá a exceção e tomará medidas adequadas (avisar usuário que deverá reinicializar)
                    raise SapiExceptionProgramaFoiAtualizado(caminho_programa_atualizado)
                else:
                    # Atualização falhou....Não tem o que fazer agora
                    raise SapiExceptionVersaoDesatualizada(resultado['explicacao'] + ". Auto atualização FALHOU. Baixe manualmente a versão atualizada do SETEC3 ou tente novamente mais tarde.")
            else:
                raise SapiExceptionVersaoDesatualizada(resultado['explicacao'] + ". Baixe versão atualizada do SETEC3.")
        elif tipo_erro == 'ProgramaDesautorizado':
            raise SapiExceptionProgramaDesautorizado(resultado['explicacao'])
        elif tipo_erro=='AgenteDesautorizado':
            raise SapiExceptionAgenteDesautorizado(resultado['explicacao'])
        erro_fatal('Resposta inesperada de servidor')

    return


# Função de inicialização para utilização do sapisrv
# Se ocorrer algum erro, ABORTA
# ----------------------------------------------------------------------------------------------------------------------
def sapisrv_inicializar_ok(*args, **kwargs):

    try:
        sapisrv_inicializar(*args, **kwargs)

    except SapiExceptionVersaoDesatualizada:
        print_tela_log("- Efetue atualização do programa e execute novamente")
        os._exit(1)

    except SapiExceptionProgramaFoiAtualizado as e:
        if modo_background():
            print_log("Programa foi atualizado para nova versão em: ",e)
        else:
            # Modo iterativo, mostra mensagem
            print_tela_log("- Programa foi atualizado para nova versão em: ",e)
            print_tela_log("- Finalizando agora. Invoque programa novamente para executar a nova versão.")
            pausa()
        # Encerra
        os._exit(1)

    except SapiExceptionProgramaDesautorizado:
        if modo_background():
            print_log("Programa não autorizado. Consulte a configuração")
        else:
            # Modo iterativo, mostra mensagem
            print_tela_log("- Programa não autorizado. Consulte a configuração")
            pausa()
        # Encerra
        os._exit(1)


    except SapiExceptionFalhaComunicacao as e:
        os._exit(1)

    except SapiExceptionAgenteDesautorizado as e:
        os._exit(1)


    except SystemExit as e:
        # Se programa solicitou encerramento através de system.Exit, simplesmente encerra
        print_log("Programa solicitou encerramento (SystemExit): " + str(e))
        os._exit(1)

    except BaseException as e:
        # Qualquer outra coisa
        trc_string=traceback.format_exc()
        print_log("[314]: Exceção abaixo sem tratamento específico. Avaliar se deve ser tratada ou se é realmente um erro de programação")
        print_log(trc_string)
        print("[700] Erro inesperado. Para mais detalhes, consulte arquivo de log: ",obter_nome_arquivo_log())
        os._exit(1)


# Função de inicialização para utilização do sapisrv
# ----------------------------------------------------------------------------------------------------------------------
def sapisrv_inicializar(*args, **kwargs):

    # Simulando exceção, para testar o tratamento na rotina superior
    #5/0
    #raise SapiExceptionFalhaComunicacao("Apenas teste")

    try:
        _sapisrv_inicializar_internal(*args, **kwargs)

    except SapiExceptionFalhaComunicacao as e:
        # Exibe erro e passa para cima
        print_tela_log("- [383] Falha na comunicação: ", e)
        print_tela_log("- Verifique a conexão com o servidor SETEC3 (sugestão: Tente acessar com um browser a partir desta máquina)")
        raise SapiExceptionFalhaComunicacao

    except SapiExceptionVersaoDesatualizada as e:
        print_tela_log("- [360]: " + str(e))
        raise SapiExceptionVersaoDesatualizada

    except SapiExceptionAgenteDesautorizado as e:
        # Exibe erro e passa para cima
        print_log("[369]: Agente (máquina) desautorizado: ", e)
        #print("Assegure-se de estar utilizando uma máquina homologada")
        raise SapiExceptionAgenteDesautorizado

    debug("sapilib iniciada")


# Reporta ao servidor um erro ocorrido no cliente
# Parâmetros:
#   programa: Nome do programa
#   ip (opcional): IP da máquina
def _sapisrv_reportar_erro_cliente(erro):
    # Lista de parâmetros
    param = dict()
    param['erro'] = erro

    # Invoca sapi_srv
    (sucesso, msg_erro, configuracao) = sapisrv_chamar_programa(
        programa="sapisrv_reportar_erro_cliente.php",
        parametros=param,
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


# Registra mensagem de erro do cliente
def sapisrv_reportar_erro(*arg):
    linha = concatena_args(*arg)
    try:
        # Registra no log (local)
        print_log("ERRO: ", linha)

        # Reportanto ao servidor, para registrar no log do servidor
        _sapisrv_reportar_erro_cliente(linha)
        print_log("Erro reportado ao servidor")

    except Exception as e:
        # Se não conseguiu reportar ao servidor, deixa para lá
        # Afinal, já são dois erros seguidos (pode ser que tenha perdido a rede)
        print_log("Não foi possível reportar o erro ao servidor: ", str(e))


# Registra mensagem de erro do cliente relacionado com uma tarefa
def sapisrv_reportar_erro_tarefa(codigo_tarefa, texto_erro):

    linha="[[tarefa:" + codigo_tarefa+ "]] " + texto_erro
    sapisrv_reportar_erro(linha)
    # Registra diretamente na situação da tarefa
    sapisrv_atualizar_status_tarefa_informativo(
        codigo_tarefa=codigo_tarefa,
        texto_status="ERRO: " + texto_erro
    )


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
        programa="sapisrv_obter_configuracao_cliente.php",
        parametros=param,
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
        tamanho_maximo=None
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
            programa="sapisrv_obter_iniciar_tarefa.php",
            parametros=param,
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

    # # Isto aqui estava embaixo da função sapisrv_obter_iniciar_tarefa
    # # Ou seja, estava duplicado, uma função dentro da outra
    # # Removi....
    # # Depois de testar o sapi_iped com esta versão, sumir com este código abaixo
    #
    # # Obtem e inicia (atômico) uma tarefa de um certo tipo (iped-ocr, ief, etc)
    # # Parâmetros opcionais:
    # #  storage: Quando o agente tem conexão limitada (apenas um storage)
    # #  tamanho_minimo e tamanho_maximo (em bytes): Util para selecionar
    # #    tarefas grandes ou pequenas, o que possivelmente irá corresponder
    # #    ao esforço computacional.
    # def sapisrv_obter_iniciar_tarefa(
    #         tipo,
    #         storage=None,
    #         dispositivo=None,
    #         tamanho_minimo=None,
    #         tamanho_maximo=None
    # ):
    #     # Lista de parâmetros
    #     param = dict()
    #     param['tipo'] = tipo
    #     if (storage is not None):
    #         param['storage'] = storage
    #     if (dispositivo is not None):
    #         param['dispositivo'] = dispositivo
    #     if (tamanho_minimo is not None):
    #         param['tamanho_minimo'] = tamanho_minimo
    #     if (tamanho_maximo is not None):
    #         param['tamanho_maximo'] = tamanho_maximo
    #
    #     # Invoca sapi_srv
    #     try:
    #         (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
    #             programa="sapisrv_obter_iniciar_tarefa.php",
    #             parametros=param,
    #             abortar_insucesso=False,
    #             registrar_log=True
    #         )
    #     except BaseException as e:
    #         print_log("Exception na chamada do sapisrv_obter_iniciar_tarefa.php: ", e)
    #         print_log("Presumindo erro intermitente. Continuando para tentar novamente mais tarde")
    #         return (False, None)
    #
    #     # Chamada respondida com falha
    #     # Talvez seja um erro intermitente.
    #     # Agente tem que ser tolerante a erros, e ficar tentando sempre.
    #     # Logo, iremos registrar no log e devolver ao chamador como uma simples "Ausência" de tarefas
    #     if not sucesso:
    #         print_log_dual("Erro na chamada do sapisrv_obter_iniciar_tarefa", msg_erro)
    #         # Não tem tarefa disponível para processamento
    #         return (False, None)
    #
    #     # Chamada respondida com sucesso
    #     # Servidor pode retornar dois valores possíveis:
    #     #  disponivel=0: Não tem tarefa
    #     #  disponivel=1: Tem tarefa para processamento
    #     if resultado["disponivel"] == 0:
    #         # Não tem nenhuma tarefa disponível
    #         return (False, None)
    #     else:
    #         # Retornou uma tarefa para processamento
    #         return (True, resultado["tarefa"])

# Obtem uma tarefa para excluir
# Parâmetros opcionais:
#  storage: Quando o agente tem conexão limitada (apenas um storage)
def sapisrv_obter_excluir_tarefa(
        tipo,
        storage=None
):
    # Lista de parâmetros
    param = dict()
    param['tipo'] = tipo
    if (storage is not None):
        param['storage'] = storage

    # Invoca sapi_srv
    try:
        (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
            programa="sapisrv_obter_excluir_tarefa.php",
            parametros=param,
            abortar_insucesso=False,
            registrar_log=True
        )
    except BaseException as e:
        print_log("Exception na chamada do sapisrv_obter_excluir_tarefa.php: ", e)
        print_log("Presumindo erro intermitente. Continuando para tentar novamente mais tarde")
        return (False, None)

    # Chamada respondida com falha
    # Talvez seja um erro intermitente.
    # Agente tem que ser tolerante a erros, e ficar tentando sempre.
    # Logo, iremos registrar no log e devolver ao chamador como uma simples "Ausência" de tarefas
    if not sucesso:
        print_log("Erro na chamada do sapisrv_obter_iniciar_tarefa", msg_erro)
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
            print_log("[993] Recuperação de dados atualizados do SETEC da tarefa", codigo_tarefa, "FALHOU: ",
                      msg_erro)
            return None

    except BaseException as e:
        print_log("[998] Recuperação de dados atualizados do SETEC da tarefa", codigo_tarefa, "FALHOU: ",
                  str(e))
        return None

    return tarefa


# Atualiza status da tarefa do sapisrv
# ----------------------------------------------------------------------------------------------------------------------
def _sapisrv_atualizar_status_tarefa(codigo_tarefa,
                                     codigo_situacao_tarefa,
                                     status,
                                     dados_relevantes=None,
                                     tamanho_destino_bytes=None,
                                     registrar_log=True):
    # Parâmetros
    param = {'codigo_tarefa': codigo_tarefa,
             'codigo_situacao_tarefa': codigo_situacao_tarefa,
             'status': ajusta_texto_saida(status) #Efetua ajustes ip=>netbios
             }
    if tamanho_destino_bytes is not None:
        param['tamanho_destino_bytes']=tamanho_destino_bytes

    metodo_invocar = 'get'
    if dados_relevantes is not None:
        dados_relevantes_json = json.dumps(dados_relevantes, sort_keys=True)
        param['dados_relevantes_json'] = dados_relevantes_json
        # Se tem atualização de dados_relevantes, invoca via post, pois url pode estourar no get
        metodo_invocar = 'post'

    # Invoca sapi_srv
    (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
        programa="sapisrv_atualizar_tarefa.php",
        parametros=param,
        registrar_log=False,
        metodo=metodo_invocar
    )

    # Registra em log
    if sucesso:
        texto_codigo_situacao=status
        if int(codigo_situacao_tarefa)>0:
            texto_codigo_situacao=str(codigo_situacao_tarefa) + "-" +status
        print_log("Tarefa ", codigo_tarefa, ": atualizado status: ", texto_codigo_situacao)
    else:
        # Se der erro, registra no log e prossegue (tolerância a falhas)
        print_log("Tarefa ", codigo_tarefa, ": Não foi possível atualizar status no SETEC3: ", msg_erro)

    # Retorna se teve ou não sucesso, e caso negativo a mensagem de erro
    return (sucesso, msg_erro)


# Atualiza status da tarefa em execução
# Caso ocorra algum erro, ignora atualização, afinal este status é apenas informativo
# Retorna:
#  - True: Se foi possível atualizar o status
#  - False: Se não atualizou o status
def sapisrv_atualizar_status_tarefa_informativo(
        codigo_tarefa,
        texto_status,
        tamanho_destino_bytes = None):

    try:

        # Verifica se a tarefa continua em andamento
        # Pode ter sido por exemplo abortada
        # ---------------------------------------------
        # Recupera dados atuais da tarefa do servidor,
        (sucesso, msg_erro, tarefa) = sapisrv_chamar_programa(
            "sapisrv_consultar_tarefa.php",
            {'codigo_tarefa': codigo_tarefa}
        )

        # Alguma coisa está impedindo tarefa de ser encontrada
        if (not sucesso):
            debug("A consulta da tarefa falhou")
            # Ignora atualização, pois o registro do status em andamento é apenas informativo
            return False

        # Se não está mais em andamento, não irá atualizar status
        codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
        if (    codigo_situacao_tarefa>=Gexecutando_intervalo_ini
            and codigo_situacao_tarefa<=Gexecutando_intervalo_fim):
            debug("Atualização de status será efetuada, pois tarefa ainda está em execução")
        else:
            # Não está em execução
            debug("Atualização de status não é possível, pois tarefa não está mais em execução")
            # Ignora atualização
            return False

        # Atualiza status informado
        (ok, msg_erro) = _sapisrv_atualizar_status_tarefa(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=GManterSituacaoAtual,
            status=texto_status,
            tamanho_destino_bytes=tamanho_destino_bytes
        )

        # Se ocorrer algum erro, ignora (registrando no log)
        # Afinal, o status em andamento é apenas informativo
        if not ok:
            debug("Não foi possível atualizar o status: ", msg_erro)
            return False

    except BaseException as e:
        print_log("Ignorando atualização de status devido a erro:", str(e))
        return False

    # Tudo certo, atualizou o status
    return True


# Troca situação da tarefa
# Este é uma operação crítica, que tem que ser realizada no momento correto
# Se ocorrer um erro, repassa para o chamador decidir
def sapisrv_troca_situacao_tarefa_obrigatorio(
        codigo_tarefa,
        codigo_situacao_tarefa,
        texto_status,
        dados_relevantes=None,
        tamanho_destino_bytes = None):

    # Se ocorrer alguma exceção aqui, simplesmente será repassada para o chamador,
    # que deverá tratar adequadamente
    (ok, msg_erro) = _sapisrv_atualizar_status_tarefa(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=codigo_situacao_tarefa,
        status=texto_status,
        dados_relevantes=dados_relevantes,
        tamanho_destino_bytes=tamanho_destino_bytes
    )

    # Se ocorrer algum erro, gera um exceção
    if not ok:
        raise SapiExceptionFalhaTrocaSituacaoTarefa(msg_erro)

    return



# Troca a situação da tarefa no servidor
# Se ocorrer um erro, fica em loop ETERNO até conseguir efetuar a operação
# Se for problema transiente, mais cedo ou mais tarde será resolvido
# Caso contrário, algum humano irá intervir e cancelar o programa
def sapisrv_troca_situacao_tarefa_loop(
        codigo_tarefa,
        codigo_situacao_tarefa,
        texto_status,
        dados_relevantes=None,
        tamanho_destino_bytes = None):
    while True:

        try:
            print_log("Trocando situação da tarefa",codigo_tarefa,"para",codigo_situacao_tarefa)
            # Registra situação
            sapisrv_troca_situacao_tarefa_obrigatorio(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=codigo_situacao_tarefa,
                texto_status=texto_status,
                dados_relevantes=dados_relevantes,
                tamanho_destino_bytes=tamanho_destino_bytes
            )

            # Se chegou aqui, é porque conseguiu atualizar a situação
            # Finaliza loop e função com sucesso
            print_log("Nova situação atualizada no SETEC3")
            return True

        except Exception as e:
            # Atualização de situação falhou
            print_log("Falhou atualização de situação para tarefa", codigo_tarefa, ":",e)

        # Pausa para evitar sobrecarregar o servidor
        dormir=60
        print_log("Tentando novamente em ",dormir, "segundos")
        time.sleep(dormir)


# Exclui tarefa
# Se ocorrer um erro, repassa para o chamador decidir
def sapisrv_excluir_tarefa(codigo_tarefa):

    # Parâmetros
    param = {'codigo_tarefa': codigo_tarefa
             }

    # Invoca sapi_srv
    (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
        programa="sapisrv_excluir_tarefa.php",
        parametros=param
    )

    # Se der erro, registra no log e gera exceção, para ser tratado pelo chamador
    if not sucesso:
        print_log("Tarefa ", codigo_tarefa, ": Não foi possível excluir no SETEC3: ", msg_erro)
        raise SapiExceptionGeral(msg_erro)

    # Tudo certo
    print_log("Tarefa ", codigo_tarefa, " excluída com sucesso")

    return True



# Exclui tarefa no servidor
# Se ocorrer um erro, fica em loop ETERNO até conseguir efetuar a operação
# Se for problema transiente, mais cedo ou mais tarde será resolvido
# Caso contrário, algum humano irá intervir e cancelar o programa
def sapisrv_excluir_tarefa_loop(codigo_tarefa):

    while True:

        try:
            print_log("Excluindo tarefa ", codigo_tarefa, " no SETEC3")
            # Registra situação
            sapisrv_excluir_tarefa(codigo_tarefa=codigo_tarefa)

            # Se chegou aqui, é porque conseguiu excluir
            # Finaliza loop e função com sucesso
            print_log("Tarefa excluída no SETEC3")
            return True

        except Exception as e:
            # Atualização de situação falhou
            print_log("Exclusão no SETEC3 dae tarefa", codigo_tarefa, "falhou:",e)

        # Pausa para evitar sobrecarregar o servidor
        dormir=60
        print_log("Tentando novamente em ",dormir, "segundos")
        time.sleep(dormir)


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
        programa="sapisrv_armazenar_texto.php",
        parametros=param,
        registrar_log=registrar_log,
        metodo=metodo_invocar
    )

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
    parametros['execucao_nome_agente'] = _obter_parini_obrigatorio('nome_agente')
    parametros['execucao_programa'] = _obter_parini_obrigatorio('programa')
    parametros['execucao_programa_versao'] = _obter_parini_obrigatorio('programa_versao')
    parametros['token'] = _obter_parini_obrigatorio('servidor_token')

    try:
        if metodo == 'get':
            return _sapisrv_chamar_programa_get(programa=programa, parametros=parametros, registrar_log=registrar_log)
        elif metodo == 'post':
            return _sapisrv_chamar_programa_post(programa=programa, parametros=parametros, registrar_log=registrar_log)
        else:
            erro_fatal("sapisrv_chamar_programa: Método inválido: ", metodo)
    except BaseException as e:
        if abortar_insucesso:
            # As mensagens explicativas do erro já foram impressas
            erro_fatal("sapisrv_chamar_programa: Abortando após erro (abortar_insucesso=True)")
        else:
            debug("sapisrv_chamar_programa: Repassando exception para chamador")
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



# Aborta tarefa.
# Retorna False sempre, para repassar para cima
def sapisrv_abortar_tarefa(codigo_tarefa, texto_status):

    erro="Abortando [[tarefa:" + codigo_tarefa+ "]] em função de ERRO: " + texto_status

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


# Atualiza arquivo de texto no servidor
# Fica em loop até conseguir
def sapisrv_armazenar_texto_tarefa(codigo_tarefa, titulo, conteudo):
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




# Retorna o nome do ambiente de execução
# ----------------------------------------------------------------------------------------------------------------------
def obter_ambiente():
    return _obter_parini_obrigatorio('nome_ambiente')


def ambiente_desenvolvimento():
    if obter_ambiente()=='DESENVOLVIMENTO':
        return True
    return False

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

class SapiExceptionVersaoDesatualizada(Exception):
    pass

class SapiExceptionProgramaFoiAtualizado(Exception):
    pass

class SapiExceptionAgenteDesautorizado(Exception):
    pass

class SapiExceptionFalhaTrocaSituacaoTarefa(Exception):
    pass

class SapiExceptionGeral(Exception):
    pass





# Testa se cliente tem comunicação com servidor
# Retorna: Verdadeiro, Falso
# ----------------------------------------------------------------------
def testa_comunicacao_servidor_sapi(url_base):
    url = url_base + "sapisrv_ping.php"
    debug("Testando conexao com servidor SAPI em " + url)

    try:
        f = urllib.request.urlopen(url, timeout=Ghttp_timeout_corrente)
        resposta = f.read()
    except BaseException as e:
        print_log("Erro: ", str(e))
        return False

    # O resultado vem em 'bytes', exigindo uma conversão explícita para UTF8
    resposta = resposta.decode('utf-8')

    # Confere resposta
    if (resposta != "pong"):
        # Muito incomum...mostra na tela também
        print_tela_log("- Servidor respondeu, em ", url, " porem com resposta inesperada: ", resposta)
        return False

    # Tudo bem
    debug("Servidor respondeu")
    return True


# Utilizada por diversas rotinas, para garantir que a inicialização tenha sido efetuada com sucesso
# ----------------------------------------------------------------------------------------------------------------------
def assegura_inicializacao():
    if not Ginicializado:
        erro_fatal("[1075]: Faltou invocar função sapisrv_inicializar. Revise seu código")
        os._exit(1)

    # Tudo certo
    return




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
        print_tela_log("- Falha na codificação UTF-8 da resposta de: ", referencia)
        print_tela_log("===== Pagina retornada =========")
        print_tela_log(resultado)
        print_tela_log("===== Fim da pagina =========")
        print_tela_log("- Erro: ", str(e))
        print_tela_log("- Verifique programa sapisrv")
        raise SapiExceptionGeral("Operação interrompida")

    # Processa pagina resultante em formato JSON
    try:

        # Carrega json.
        # Se houver algum erro de parsing, indicando que o servidor
        # não está legal, irá ser tratado no exception
        d = json.loads(resultado)

    except BaseException as e:
        print_tela_log()
        print_tela_log("- Resposta invalida (não está no formato json) de: ", referencia)
        print_tela_log("===== Pagina retornada =========")
        print_tela_log(resultado)
        print_tela_log("===== Fim da pagina =========")
        print_tela_log("- Erro: ", str(e))
        print_tela_log("- Verifique programa sapisrv (desenvolvedor)")
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
    url = _obter_parini_obrigatorio('url_base') + programa + "?" + parametros_formatados

    # Registra em log
    if modo_debug() or registrar_log:
        # Registra apenas no log
        debug(url)


    #retorno = _sapisrv_get_sucesso(url) # Isto aqui estava errado...chamando sucesso, mas tratando erro...sem sentido
    start_time = time.time()
    retorno = sapisrv_get_ok(url)
    elapsed_time = time.time() - start_time

    if modo_debug() or registrar_log:
        # Registra apenas no log
        debug("Tempo de resposta: ",elapsed_time)


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
        print_tela_log("- Erro inesperado reportado por: ", url)
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
        f = urllib.request.urlopen(url, timeout=Ghttp_timeout_corrente)
        resultado = f.read()

    except BaseException as e:
        print_tela_log("- Não foi recebido resposta em tempo hábil para GET em URL:", url)
        print_tela_log("- Exceção:",type(e).__name__, " - ",str(e))
        print_tela_log("- Verifique rede")
        # Gera exception para interromper execução de comando
        raise SapiExceptionGeral(str(e))

    referencia = "GET => " + url

    return processar_resultado_ok(resultado, referencia)



# =====================================================================================================================
# POST
# =====================================================================================================================

# Invoca Sapi server (sapisrv) utilizando POST
# ----------------------------------------------------------------------
def _sapisrv_chamar_programa_post(programa, parametros, registrar_log=False):
    if (registrar_log or modo_debug()):
        print_log("Chamada POST para", programa)

    retorno = sapisrv_post_sucesso(programa, parametros)

    # Ajusta sucesso para booleano
    sucesso = False
    if (retorno["sucesso"] == "1"):
        sucesso = True

    # Outros dados
    msg_erro = retorno["msg_erro"]
    dados = retorno["dados"]

    # Registra resultado no log
    if (registrar_log or modo_debug()):
        if sucesso:
            print_log("Servidor respondeu com sucesso")
        else:
            print_log("Servidor respondeu com falha: ", msg_erro)

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
        print_tela_log("- Erro inesperado reportado por: ", programa, " via post")
        print_tela_log(d["msg_erro"])
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
        print_tela_log("- Falha na chamada de ", programa, " com POST")
        print_tela_log("- Erro: ", str(e))
        print_tela_log("- Verifique rede")
        raise SapiExceptionGeral("Operação Interrompida")

    # Monta referência para exibição de erro
    referencia = "POST em " + programa

    return processar_resultado_ok(resultado, referencia)



# Efetua o post
# ----------------------------------------------------------------------
def _post(programa, parametros):
    # Formata parâmetros
    parametros_formatados = urllib.parse.urlencode(parametros)

    # Efetua conexão com servidor
    protocolo=_obter_parini_obrigatorio('servidor_protocolo')
    if protocolo=='https':
        # HTTPS
        conn = http.client.HTTPSConnection(
            _obter_parini_obrigatorio('servidor_ip'),
            port=_obter_parini_obrigatorio('servidor_porta'),
            timeout=Ghttp_timeout_corrente)
    else:
        # HTTP simples
        conn = http.client.HTTPConnection(
            _obter_parini_obrigatorio('servidor_ip'),
            port=_obter_parini_obrigatorio('servidor_porta'),
            timeout = Ghttp_timeout_corrente)

    # Parâmetros para POST
    headers = {"Content-type": "application/x-www-form-urlencoded",
               "Accept": "text/plain"}
    url_parcial = "/" + _obter_parini_obrigatorio('servidor_sistema') + "/" + programa

    # Envia POST
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
    sys.stdout.write("- Sapi Erro Fatal: ")
    print(*args)
    print("=================================================================")
    print("Segue pilha para orientação. Atenção: NÃO se trata de exception")
    print("=================================================================")
    traceback.print_stack()
    print("=================================================================")
    #trc_string = traceback.format_exc()
    #print(trc_string)
    os._exit(1)


# Aborta programa
# ----------------------------------------------------------------------
def die(s):
    print(s)
    os._exit(1)


# Dump "bonitinho" de uma variável
# ----------------------------------------------------------------------
def var_dump(x):
    print(type(x))
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(x)

# Recupera um valor string de um dicionario.
# Se não existir ou não possuir valor definido, retorna string nulo
# ----------------------------------------------------------------------
def obter_dict_string_ok(dict, chave):
    valor=dict.get(chave, None)
    if valor is None:
        return ""
    return str(valor)


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
    print(r)

# Utilizado para formatar impressões na tela como formulário, com uma largura fixa
# campo1    : xxxx
# Campo 25  : yyyyy
def print_formulario(label="", largura_label=0, valor="", truncar=False):

    global Gprint_formulario_ultima_largura_label

    # Converte tudo para string
    label=str(label)
    valor=str(valor)

    if largura_label==0:
        # Se não foi definido a largura
        if Gprint_formulario_ultima_largura_label is not None:
            # Pega a última largura, se houver
            largura_label=Gprint_formulario_ultima_largura_label
        else:
            # Caso contrário, considera a largura máxima para não truncar o campo
            largura_label=len(label)
    else:
        Gprint_formulario_ultima_largura_label=largura_label

    # Trunca campo, se ultrapassar tamanho máximo
    if truncar:
        if len(label)>largura_label:
            label=label[0:largura_label-3]+"..."

    largura_valor=Glargura_tela-largura_label-2

    separador=": "
    if label=="":
        separador=""

    string_formatacao = "%-" + str(largura_label)+ "s" + \
                        "%2s" + \
                        "%-" + str(largura_valor)+ "s"

    print(string_formatacao % (label,separador,valor))


# Substitui o convert_unicode no python3, que já é unicode nativo
# Converte todos os argumentos para string e concatena
# ----------------------------------------------------------------------
def concatena_args(*arg):
    s = ""
    for x in arg:
        # Se não for string, converte para string
        if not type(x) == str:
            x = str(x)
        # Concatena, separando com um espaço apenas
        s = s + x.strip() + " "

    # Remove espaços adicionais no início e fim
    s=s.strip()

    return s

# Sintaxe mais óbvia
def texto(*arg):
    return concatena_args(*arg)

# Retorna verdadeiro se está em modo background
# Neste modo, não exibe a saída regular na console (stdout)
# Apenas em situações críticas (programa abortado) o resultado sairá na console (stdout ou stderr)
def modo_background():
    background=get_parini('background', False)
    return background

def modo_debug():
    debug=get_parini('debug', False)
    return debug




def obter_timestamp(remover_milisegundo=True):
    ts = str(datetime.datetime.now())
    if remover_milisegundo:
        # Remove milisegundo
        ts, mili=ts.split('.')
    # Troca separadores incomuns que podem confundir SO por '-'
    ts=ts.replace('.','_')
    ts=ts.replace(' ','_')
    ts=ts.replace(':','-')

    return ts


# ----------------------------------------------------------------------------------------------------------------------
# Funções relacionadas com log
# ----------------------------------------------------------------------------------------------------------------------

# Determina nome/caminho para arquivo de log
# baseado em parâmetros de inicialização
def _montar_nome_arquivo_log():

    # Usuário forneceu parâmetro com o caminho completo para o arquivo de log
    logfile=get_parini('logfile')
    if logfile is not None:
        return logfile

    # Default para nome de arquivo de log
    # log_XXXXX_AAAA-MM-DD_HH-MM-SS_ssssss.txt, onde:
    # xxxx: Nome do programa
    # ssssss: Milisegundos
    programa=get_parini(chave='programa',default='sapi')
    nome_arquivo_default="log_" + programa + "_" + obter_timestamp(remover_milisegundo=False) + ".txt"

    # Usuário forneceu a pasta onde deve ser criado o arquivo de log
    logdir=get_parini('logdir')
    if logdir is not None:
        # Verifica se pasta existe
        if not os.path.isdir(logdir):
            erro_fatal("--logdir ",logdir," : Pasta inexistente. Crie primeiro a pasta")
        # Será criado arquivo com nome padrão na pasta indicada
        logfile=os.path.join(logdir, nome_arquivo_default)
        return logfile

    # Usuário não especificou pasta de log e nem caminho para o arquivo
    # Desta forma, o log será gravado na pasta default, com nome default
    return nome_arquivo_default


# Nome do arquivo de log
# resestar=True: Remonta o nome do arquivo de log, com os parâmetros vigentes
# ----------------------------------------------------------------------------
def obter_nome_arquivo_log():

    if get_parini('log') is not None:
        return get_parini('log')

    # Monta caminho para arquivo de logo
    logfile = _montar_nome_arquivo_log()

    # Guarda nome do arquivo de log
    set_parini('log', logfile)

    return logfile


# Força a mudança para um nome de arquivo de log
# ----------------------------------------------------------------------
def renomear_arquivo_log_default(nome_novo):

    # Se o usuário especificou um arquivo de log específico na linha de comando,
    # ignora operação de renomear, pois a vontade final é do usuário
    if (get_parini('logfile') is not None):
        debug("Arquivo de log não foi renomeado, pois usuário definiu parâmetro logfile")
        return False

    try:
        # recupera nome atual
        nome_atual=get_parini('log')

        if (nome_atual==nome_novo):
            debug("renomear_arquivo_log_default: Nome de arquivo de log igual ao atual, logo nada a fazer. ")
            return

        # Troca nome de log para nome_novo
        set_parini('log', nome_novo)

        # Se não tem nome atual, nada a fazer, pois arquivo de log ainda não tinha sido criado
        if nome_atual is None:
            return False

        # Se o arquivo atual ainda não existe, não tem nada a fazer, pelo mesmo motivo
        if not os.path.isfile(nome_atual):
            return True

        # Ok, arquivo atual existe
        debug("nome nome de arquivo de log atual", nome_atual)

        # Verifica se o arquivo novo existe
        novo_existe=os.path.isfile(nome_novo)

        # Se o arquivo novo ainda não existe, simplesmente renomeia o atual para o novo
        if not novo_existe:
            os.rename(nome_atual, nome_novo)
            debug("Arquivo de log renomeado de",nome_atual, "para", nome_novo)
            return True

        # Se o arquivo existe, temos que ler o conteúdo do arquivo atual,
        # transferir para o final do novo arquivo
        # e por último excluir o arquivo antigo
        with codecs.open(nome_novo, 'a', "utf-8") as arquivo_novo:
            with codecs.open(nome_atual, 'r', "utf-8") as arquivo_atual:
                for linha in arquivo_atual:
                    arquivo_novo.write(linha)

        debug("Conteúdo do arquivo", nome_atual, "transferido para", nome_novo)

        # Exclui arquivo atual
        os.remove(nome_atual)
        debug("Arquivo", nome_atual, "excluído")

    except BaseException as e:
        print_log("Erro durante ajuste do nome do arquivo de log para",nome_novo, "erro: ",e)


# Definir label que será utilizando no arquivo de log
# ----------------------------------------------------------------------
def definir_label_log(label_log):

    set_parini('label_log', label_log)
    debug("label_log alterado para ", label_log)


# Efetua ajustes no texto, para ficar adequado a log e registro de status
def ajusta_texto_saida(s):

    # IP para nome netbios
    for caminho_storage in Gdic_storage:
        nome_storage=Gdic_storage[caminho_storage]
        sant=s[:]
        s=s.replace(caminho_storage, nome_storage)
        # Troca completa de caminho com ip por caminho com nome netbios
        s=s.replace(caminho_storage.strip("\\"), nome_storage.strip("\\"))

        # No dicionário tem entrada por IP e correspondente netbios
        # '\\\\10.41.87.235\\storage': '\\\\gtpi-sto-03\\storage'}
        # Nem sempre o caminho vem certo, da forma como está acima
        # Logo, tem que tratar também os casos em que vem o IP junto
        # com outras coisas
        # Isola IP
        ip=caminho_storage
        ip=ip.replace("\\storage","")
        ip=ip.replace("\\","")
        ip=ip.replace("/","")
        # Isola nome netbios
        netbios=nome_storage
        netbios=netbios.replace("\\storage","")
        netbios=netbios.replace("\\","")
        netbios=netbios.replace("/","")
        # Substitui ip por nome netbios
        s=s.replace(ip, netbios)

        # Troca ip por nome netbios
        if (s!=sant and modo_debug()):
            # Insere marcador que houve alteração
            s=s + " *A*"

    return s

def print_tela(*arg):

    linha = concatena_args(*arg)
    linha=ajusta_texto_saida(linha)

    print(linha)


# Grava apenas em arquivo de log
# ----------------------------------------------------------------------
def _print_log_apenas(*arg):
    # Monta linha para gravação no log
    pid = os.getpid()
    hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Código para python2. Por enquanto desativado
    # linha="["+str(pid)+"] : "+hora+" : "+converte_unicode(*arg)

    # Adiciona rotulo geral log, utilizado para separar atividades por tarefa, por exemplo
    rotulo_log=''
    label_log=get_parini('label_log')
    if label_log is not None:
        rotulo_log="["+label_log+ "] "

    linha = concatena_args(*arg)

    # Remove quebra de linhas
    linha = linha.replace("\r", "")
    linha = linha.replace("\n", "")

    # Se começar ou terminar por "-" ou " " ou qualquer combinação destes, remove, pois no log o texto é direto
    # Isto serve para que mensagens que são para tela, que tem formato "- xxxx", fiquem no log apenas como "xxxx"
    linha=linha.strip(" ")
    linha=linha.strip("-")
    linha=linha.strip(" ")

    # Adiciona sufixo
    linha = "[" + str(pid) + "] : " + hora + " : " + rotulo_log + linha

    # Efetua ajustes na linha, para simplificar a leitura (ex: IP para netbios)
    linha=ajusta_texto_saida(linha)

    arquivo_log=obter_nome_arquivo_log()

    with codecs.open(arquivo_log, 'a', "utf-8") as sapi_log:
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
    if not modo_background():
        print(linha)


# Exibe mensagem recebida na tela
# e também grava no log
# ----------------------------------------------------------------------
def print_tela_log(*arg):
    if not modo_background():
        # Exibe na tela
        print_tela(*arg)

    # Grava no log
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
def if_print(exibir, *arg):
    # o primeiro campo tem que ser do tipo booleano
    # Um erro bastante comum é esquecer de passar este parâmetro
    # Logo, geramos um erro fatal aqui
    if type(exibir) != bool:
        print("Chamada inválida para if_print_ok, sem parâmetro de condição")
        print("Argumento: ", exibir, *arg)
        os._exit(1)

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


# ===================================================================================================
# "Desenhos" para direcionar a atençã
# ===================================================================================================
def print_atencao():
    # Na tela sai legal...aqui está distorcido, provavelmente em função da largura dos caracteres
    # teria que ter uma fonte com largura fixa
    print("┌─────────────────┐")
    print("│  A T E N Ç Ã O  │")
    print("└─────────────────┘")

def print_erro():
    # Na tela sai legal...aqui está distorcido, provavelmente em função da largura dos caracteres
    # teria que ter uma fonte com largura fixa
    print("┌───────────┐")
    print("│  E R R O  │")
    print("└───────────┘")



# unicode box drawing characteres
'''
┌ ┐
└ ┘
─
│
┴
├ ┤
┬
╷
'┼'
'''

def print_falha_comunicacao():
    print_erro()
    print("- Consulte o log para entender melhor o problema(*LG)")
    print("- Se você suspeita de falha de comunicação (rede), ")
    print("  tente acessar o SETEC3 utilizando um browser computador para conferira se a conexão está ok")



# ===================================================================================================


# ===================================================================================================
# Testes de sistema operacional
# ===================================================================================================

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
    print("Sistema operacional desconhecido : ", os.name)
    os._exit(1)


# Verifica se usuário tem direito de root
# ----------------------------------------------------------------------
def tem_direito_root():
    if not esta_rodando_linux():
        return False

    if os.geteuid() != 0:
        return False

    # Ok, tudo certo
    return True

def espera_enter(texto=None):
    if texto is None:
        texto="Digite <ENTER> para prosseguir"
    try:
        input(texto)
        return True
    except KeyboardInterrupt:
        # Ignorar CTR-C
        return False



# Pergunta Sim/Não via via input() e retorna resposta
# - pergunta: String que será exibido para o usuário
# - default: (s ou n) resposta se usuário simplesmente digitar <Enter>. 
# O retorno é True para "sim" e False para não
def pergunta_sim_nao(pergunta, default="s"):
    validos = {"sim": True,
               "s": True,
               "não": False,
               "nao": False,
               "n": False}
    if default is None:
        prompt = " [s/n] "
    else:
        default = default.lower()
        prompt = " [S/n] "
        if default == "n":
            prompt = " [s/N] "

    while True:
        sys.stdout.write(pergunta + prompt)
        escolha = input().lower()
        if default is not None and escolha == '':
            return validos[default]
        elif escolha in validos:
            return validos[escolha]
        else:
            sys.stdout.write("Responda com 's' ou 'n'\n")

def pausa(mensagem=None):
    if mensagem is None:
        mensagem="Pressione <ENTER> para prosseguir..."
    try:
        programPause = input(mensagem)
    except KeyboardInterrupt:
        print("- Operação interrompida pelo usuário com <CTR>-<C>")
        return False


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


# -----------------------------------------------------------------------------------
# Determina características de uma pasta
# -----------------------------------------------------------------------------------
# Características de pasta via python (Lento)
def obter_caracteristicas_pasta_python(start_path):
    total_size = 0
    qtd=0
    qtd_pastas=0
    for dirpath, dirnames, filenames in os.walk(start_path):
        qtd_pastas += 1
        for f in filenames:
            fp = montar_caminho_longo(dirpath, f)
            total_size += os.path.getsize(fp)
            qtd=qtd+1
            #print("qtd arquivos: ", qtd)

    # Dicionários de retorno
    ret=dict()
    ret["quantidade_arquivos"]=qtd
    ret["quantidade_pastas"]=qtd_pastas
    ret["tamanho_total"]=total_size

    return ret


# Características de pasta
def obter_caracteristicas_pasta_python_ok(start_path):
    try:
        carac = obter_caracteristicas_pasta_python(start_path)
    except OSError as e:
        print_log("[2197] obter_caracteristicas_pasta_ok falhou para pasta",start_path," erro: ",str(e))
        return None
    except BaseException as e:
        print_log("[2200] obter_caracteristicas_pasta_ok falhou para pasta",start_path," erro: ",str(e))
        return None

    # Tudo certo
    return carac


# Retorna tamanho da pasta calculada através do Robocopy, e se ocorrer erro retorna None
def obter_caracteristicas_pasta_via_robocopy_ok(caminho_origem):

    try:
        return (obter_caracteristicas_pasta_via_robocopy(caminho_origem))
    except Exception as e:
        erro = texto("Execução de robocopy falhou para determinação de tamanho falhou:", str(e))
        print_log(erro)
        return None

# Retorna características da pasta utilizando robocopy
# Atenção:
# ESTA ROTINA NÃO DEVE SER UTILIZADA EM CONJUNTO COM UMA OPERAÇÃO
# DE CÓPIA VIA ROBOCOPY
# POIS OS DOIS ROBOCOPYS ENTRARÃO EM CONFLITO, E FICARÁ TUDO MUITO LENTO
def obter_caracteristicas_pasta_via_robocopy(pasta):

    # Monta comando robocopy para determinar o tamanho da pasta
    # ---------------------------------------------------------
    # Será gerado um comando como este:
    #comando_teste='robocopy /l /nfl /ndl /bytes /e "I:/desenvolvimento/sapi/dados_para_testes/relatorios_cellebrite/00_pequeno_XML_danificado"  "I:/desenvolvimento/sapi/dados_para_testes/relatorios_cellebrite/00_pequeno_XML_danificado"
    # A pasta tem que ser repetida (origem e destino)

    # Remove notação de caminho longo: \\UNC\\...
    pasta=remove_unc(pasta)
    # Adiciona aspas para atender sintaxe
    comando_caminho_origem='"' + pasta + '"'

    # Confere se pasta existe
    if not os.path.exists(pasta):
        raise Exception(texto('[3862] Pasta não encontrada: ',
                    pasta))

    # Cria um arquivo temporario para armazenar a versão sintética do arquivo XML
    arquivo_temporario = tempfile.NamedTemporaryFile(delete=False)
    caminho_log_temporario = arquivo_temporario.name
    arquivo_temporario.close()

    # Para depurar, mono-usuário, é melhor deixar em um arquivo fixo
    caminho_log_temporario = "debug_obter_caracteristicas_pasta_via_robocopy.txt"

    # Parâmetros para efetuar calculo do tamanho (o mais importante é o /l)
    # /l     : Specifies that files are to be listed only (and not copied, deleted, or time stamped).
    # /e     : Copies subdirectories. Note that this option includes empty directories.
    # /bytes : Prints sizes, as bytes.
    # /nfl   : Specifies that file names are not to be logged.
    # /ndl   : Specifies that directory names are not to be logged.
    # /R:0 /W:0: Evita que o robocopy fique esperando por arquivos que estão em processo de copia
    opcoes_robocopy="/l /e /bytes /nfl /ndl /R:0 /W:0"
    saida = ">"+caminho_log_temporario + " 2>&1 "
    comando=' '.join(['robocopy',
                      opcoes_robocopy,
                      comando_caminho_origem,
                      comando_caminho_origem,
                      saida])

    #if modo_debug():
    #    print_log(comando)
    print_log(comando)

    # Executa Robocopy
    debug("Executando comando robocopy para calculo de tamanho")
    debug("Arquivo temporário de log:", caminho_log_temporario)

    # Executa robocopy
    try:
        print_log("Invocando comando robocopy para determinar características da pasta")
        debug(comando)
        subprocess.check_output(comando, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
        # Ok, tudo certo
        print_log("Comando robocopy de verificação de tamanho finalizado sem erro")
    except subprocess.CalledProcessError as execucao:
        # Quando o robocopy finaliza com sucesso (ou seja, copiou arquivos)
        # retorna um exit code de 1
        return_code=execucao.returncode
        texto_return_code = Grobocopy_texto_return_code.get(return_code, None)
        if texto_return_code is not None:
            texto_resultado = texto(
                "Verificação de pasta via robocopy finalizado com",
                "exit code",
                return_code,
                ":",
                texto_return_code)
        print_log(texto_resultado)
        # Para erros sérios (>8), gera exceção
        if (return_code>8):
            raise Exception("Erro sério no robocopy", texto_resultado)

    debug("Comando Robocopy para calculo de tamanho foi finalizado")

    #print_sanitizado(resultado)
    #die('ponto3924')

    # Procurar por linha que contem tamanho
    tamanho_total = None
    quantidade_arquivos = None
    quantidade_pastas = None
    achou_total=False
    with open(caminho_log_temporario, "r") as fentrada:
        for linha in fentrada:
            #print_sanitizado(linha)

            # Procura linha de cabeçalho do total, para evitar falsos positivos
            # Total   Copiada  IgnoradaIncompatibilidade     FALHA    Extras
            if "Total" in linha:
                achou_total=True

            # Se não achou total, não adianta nem prosseguir
            if not achou_total:
                continue


            # A linha de tamanho tem o seguinte formato
            #     Bytes: 174597050         0 174597050         0         0         0
            # print_sanitizado(linha)
            if "Bytes:" in linha:
                tamanho_total=robocopy_log_parse_total(linha)
                # Manipula linha para simular erro
                # linha = "Bytes: xxx"

            if "Arquivos:" in linha or "Files:" in linha:
                quantidade_arquivos = robocopy_log_parse_total(linha)

            # Diretórios
            if "rios:" in linha or "Folders:" in linha:
                quantidade_pastas = robocopy_log_parse_total(linha)

    # Parse falhou
    if tamanho_total is None:
        raise Exception('[2445] Não foi reconhecido tamanho da pasta')

    if quantidade_arquivos is None:
        raise Exception('[2448] Não foi reconhecida a quantidade de arquivos')

    if quantidade_pastas is None:
        raise Exception('[2448] Não foi reconhecida a quantidade de pastas')

    # Elimina arquivo temporário, pois não é mais necessário
    if modo_debug():
        debug("Arquivo de log temporario mantido em", caminho_log_temporario)
    else:
        # Excluir arquivo que não é mais necessário
        os.unlink(caminho_log_temporario)

    # Dicionário de retorno
    ret = dict()
    ret["quantidade_arquivos"] = quantidade_arquivos
    ret["quantidade_pastas"] = quantidade_pastas
    ret["tamanho_total"] = tamanho_total
    return ret


# Parse de uma linha de total do robocopy
def robocopy_log_parse_total(linha):

    try:
        partes = linha.split(':')
        # var_dump(partes)
        if len(partes) < 2:
            raise Exception('[2465] Não localizado separador ":"')
        parte_tamanho = str(partes[1]).strip()
        # 174597050         0 174597050         0         0         0
        # var_dump(parte_tamanho)
        partes = parte_tamanho.split(' ')
        # 174597050
        total = str(partes[0])
        total = total.strip()
        if not total.isdigit():
            raise Exception(texto('[2474] Parse no campo de total falhou: ', total))

        # Tudo certo
        return int(total)

    except Exception as e:
        erro = texto("Linha de mal formada <<", linha, ">> erro: ", str(e))
        raise Exception(erro)

#
def obter_caracteristicas_pasta(pasta):
    return obter_caracteristicas_pasta_python(pasta)

# Retorna dicionário com chaves:
#  quantidade_arquivos: Total de arquivos
#  quantidade_pastas: Total de pasta
#  tamanho_total: Tamanho em bytes
def obter_caracteristicas_pasta_ok(pasta):
    return obter_caracteristicas_pasta_python_ok(pasta)

# Retorna apenas o tamanho da pasta
def obter_tamanho_pasta_ok(path):
    carac = obter_caracteristicas_pasta_ok(path)
    if carac is None:
        return 0

    tamanho = carac.get("tamanho_total", 0)
    return tamanho

# Converte Bytes para formato Humano
def converte_bytes_humano(size, precision=1, utilizar_base_mil=False):
    # Converte para numérico, caso tenha recebido string
    try:
        size=int(round(size))
    except:
        return "? bytes"

    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', "PB", "EB", "ZB", "YB"]
    suffix_index = 0
    base = 1024.0
    if utilizar_base_mil:
        base=1000
    while size > base and suffix_index < 8:
        suffix_index += 1  # increment the index of the suffix
        size /= base  # apply the division
    return "%.*f%s" % (precision, size, suffixes[suffix_index])

# ===================================================================================
# Cópia via Robocopy
# ===================================================================================

# Copiar pasta via robocopy
# Retorna:
#  - sucesso: True/False
#  - explicacao: Tanto para sucesso como para erro
def copiar_pasta_via_robocopy(pasta_origem, pasta_destino, caminho_log):

    # Executa comando de disparo do robocopy
    try:
        print_log("Executando comando robocopy")
        print_log("pasta_origem: ", pasta_origem)
        print_log("pasta_destino: ", pasta_destino)
        print_log("Log de execução será gravado em", caminho_log)
        (sucesso, explicacao) = _copiar_pasta_via_robocopy(pasta_origem, pasta_destino, caminho_log)
        return (sucesso, explicacao)
    except Exception as e:
        trc_string=traceback.format_exc()
        erro = texto("Execução de robocopy falhou :", str(e), trc_string)
        return (False, erro)


def _copiar_pasta_via_robocopy(pasta_origem, pasta_destino, caminho_log):
    # Para teste
    #caminho_origem='I:/desenvolvimento/sapi/dados_para_testes/relatorios_cellebrite/00_pequeno_XML_danificado'
    #caminho_destino='\\\\10.41.87.235\\storage\\Memorando_5917-17_XXX_YYY\\item1a\\item1a_extracao'

    # Verifica se pasta de origem existe
    if not os.path.exists(pasta_origem):
        raise Exception("Pasta de origem não existe:", pasta_origem)

    # Se pasta de destino não existe, cria
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)

    # Monta comando
    # -------------
    # Ajusta caminho de destino
    # Troca prefixo para caminho longo
    # \\\\?\\UNC\\" => \\
    pasta_destino=pasta_destino.replace("\\\\?\\UNC\\", "\\\\")
    # Adiciona aspas nos caminhos para atender sintaxa do robocopy
    comando_caminho_origem='"' + pasta_origem + '"'
    comando_caminho_destino='"' + pasta_destino + '"'
    # Demais parâmetros
    '''
    Fonte: https://technet.microsoft.com/en-us/library/cc733145(v=ws.11).aspx
    /MT[:N]  Creates multi-threaded copies with N threads.
             N must be an integer between 1 and 128. The default value for N is 8.

    /mir     Mirrors a directory tree (equivalent to /e plus /purge).
    /v       Produces verbose output, and shows all skipped files.
    /np      Specifies that the progress of the copying operation
             (the number of files or directories copied so far) will not be displayed.
    /bytes   Exibe tamanhos em bytes.
    /NJH     Especifica que não há nenhum cabeçalho no log.
    /r:<N>   Specifies the number of retries on failed copies. The default value of N is 1,000,000 (one million retries).
    /w:<N>   Specifies the wait time between retries, in seconds. The default value of N is 30 (wait time 30 seconds).

    '''
    # Opções gerais
    opcoes_robocopy="/MT /mir /v /np /bytes /NJH /r:120 /w:60 "
    # Arquivo de log
    opcoes_robocopy+=" /log:" + caminho_log

    # Redirecionamento de saída padrão e saída de erros
    arquivo_saida_padrao = "saida_"+caminho_log
    saida = ">"+ arquivo_saida_padrao + " 2>&1 "

    comando=' '.join(['robocopy',
                      comando_caminho_origem,
                      comando_caminho_destino,
                      opcoes_robocopy,
                      saida])

    # Para comparar a formação do documento
    # O comando_teste abaixo tem a sintaxe correta
    #comando_teste='robocopy "I:/desenvolvimento/sapi/dados_para_testes/relatorios_cellebrite/00_pequeno_XML_danificado" "\\\\10.41.87.235\storage\Memorando_5917-17_XXX_YYY\item1a\item1a_extracao" /MT /mir /v /np >sapi_robocopy.log 2>&1'
    #var_dump(comando)
    #var_dump(comando_teste)
    #die('ponto2794')

    # Simula um erro
    #comando_erro='robocopy "I:/desenvolvimento/sapi/dados_para_testes/relatorios_cellebrite/00_pequeno_XML_danificado" "\\10.41.87.235\storage\Memorando_5917-17_XXX_YYY\item1a\item1a_extracao" /MT /mir /v /np >sapi_robocopy.log 2>&1'
    #comando=comando_erro

    #comando = comando_teste
    # Executa robocopy
    try:
        print_log("Invocando comando robocopy")
        print_log("Saída padrão e saída de erros no arquivo: ", arquivo_saida_padrao)
        print_log("Log do robocopy armazenado no arquivo: ", caminho_log)
        print_log(comando)
        subprocess.check_output(comando, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
        # Ok, tudo certo
        print_log("Comando robocopy finalizado")
        # Tudo certo?? Incomum?? O normal seria sair com exit code=1
        texto_resultado=texto(
            "Robocopy finalizado, mas nenhum arquivo foi copiado:",
            "exit code 0 - The source and destination directory trees are completely synchronized.",
            "Este exit code também pode significar que o robocopy foi simplesmente killed")
        return (True, texto_resultado)
    except subprocess.CalledProcessError as execucao:
        # Quando o robocopy finaliza com sucesso (ou seja, copiou arquivos)
        # retorna um exit code = 1
        # Mas também retorna outros exit code, alguns significando erros
        return_code=execucao.returncode

        #var_dump(return_code)
        #die('ponto2952')
        # Simula falha para teste
        # return_code=17

        # Verifica qual resultado do comando
        if (return_code==1):
            # Este é o exit_code quando o robocopy finalizou com sucesso
            # E COPIOU ARQUIVOS (o exit_code 0 é quando não copiou arquivos)
            texto_resultado="Cópia via Robocopy finalizada OK"
            return (True, texto_resultado)
        else:
            texto_return_code=Grobocopy_texto_return_code.get(return_code, None)
            if texto_return_code is not None:
                texto_resultado=texto(
                    "Cópia via Robocopy finalizada com exit code",
                    return_code,
                    ":",
                    texto_return_code)
            else:
                texto_resultado=texto(
                    "Cópia via Robocopy finalizada com resultado desconhecido:",
                    return_code,
                    "Consulte o log da cópia do Robocopy para maiores informações")
            # Alguns destes "erros" podem ser somente anomalias
            # Terá que analisar na prática
            # Por enquanto, vamos considerar como erro apenas algo maior que 8
            sucesso=True
            if return_code>8:
                sucesso=False
        return (sucesso, texto_resultado)


# ===================================================================================
# Ajuste de caminho
# ===================================================================================

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


# Fonte: https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247(v=vs.85).aspx
# The "\\?\" prefix can also be used with paths constructed according to
# the universal naming convention (UNC).
# To specify such a path using UNC, use the "\\?\UNC\" prefix.
# For example, "\\?\UNC\server\share",
# where "server" is the name of the computer and "share" is the name of the shared folder.
# These prefixes are not used as part of the path itself.
# They indicate that the path should be passed to the system with minimal modification,
# which means that you cannot use forward slashes to represent path separators,
# or a period to represent the current directory,
# or double dots to represent the parent directory.
# Because you cannot use the "\\?\" prefix with a relative path,
# relative paths are always limited to a total of MAX_PATH characters.

# Ajusta caminho de destino para copia, adicionando prefixo para path longo
def ajustar_para_path_longo(path):

    # Se no caminho contem o drive (ex: Z:Memorando_1880_17...), não faz sentido ajustar para caminho longo
    if ":" in path:
        return path

    # Se no caminho não contém \\ não faz sentido ajustar (ex: ..\pasta1)
    if ('\\\\' not in path):
        return path

    # O separador não pode ser /, tem que ser \
    # Como \ é escape, tem que dobrar \\.
    path = path.replace('/', os.sep).replace('\\', os.sep)
    # Se for UNC, colocar a representação explícita
    if ('\\\\' in path) and ('UNC\\' not in path):
        path=path.replace('\\\\','UNC\\')
    # Adiciona notação para caminho longo \\?\
    if '\\\\?\\' not in path:
        path = '\\\\?\\' + path
    return path


def sanitiza_parte_caminho(parte_caminho):
    # Remove alguns caracteres que não são muito desejáveis no path
    parte_caminho = parte_caminho.replace("/", "_")
    parte_caminho = parte_caminho.replace(" ", "_")
    return parte_caminho


def montar_caminho(*arg):
    caminho=os.path.join(*arg)

    return caminho

def montar_caminho_longo(*arg):
    caminho=montar_caminho(*arg)

    # Efetua ajuste para path longo
    caminho=ajustar_para_path_longo(caminho)

    return caminho

def remove_unc(caminho):
    # Remove notação UNC (para caminho longo)
    caminho=caminho.replace("\\\\?\\UNC\\", "\\\\")
    return caminho


# Efetua uma cópia do diretorio de origem para o diretório de destino,
# mesclando
# Ou seja, se o diretorio de destino já existe, os novos arquivos/pastas do diretório de origem
# serão adicionados no diretório de destino
def adiciona_diretorio(src, dst):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            adiciona_diretorio(s, d)
        else:
            shutil.copy2(s, d)


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
    arquivo_controle = os.path.join(ponto_montagem, Garquivo_controle)
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
    arquivo_controle = os.path.join(ponto_montagem, Garquivo_controle)

    # Se pasta para ponto de montagem não existe, então cria
    if not os.path.exists(ponto_montagem):
        os.makedirs(ponto_montagem)

    # Confirma se pasta existe
    # Não deveria falhar em condições normais
    # Talvez falhe se estiver sem root
    if not os.path.exists(ponto_montagem):
        print_tela_log("- Criação de pasta para ponto de montagem [", ponto_montagem, "] falhou")
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

    # print(comando)
    os.system(comando)

    # Verifica se arquivo de controle existe no storage
    if os.path.isfile(arquivo_controle):
        # Tudo certo, montou
        return True
    else:
        # print_tela_log(comando)
        print_tela_log("- Após montagem de storage, não foi encontrado arquivo de controle[", arquivo_controle, "]")
        print_tela_log("- Ou montagem do storage falhou, ou storage não possui o arquivo de controle.")
        print_tela_log("- Se for este o caso, inclua na raiz o arquivo de controle com qualquer conteúdo.")
        return False


#
def obter_caminho_storage(conf_storage, utilizar_ip=True):

    nome_maquina_storage=conf_storage["maquina_netbios"]
    ip_storage=conf_storage["maquina_ip"]

    if utilizar_ip:
        maquina = ip_storage
    else:
        maquina = nome_maquina_storage

    # "\\" = "\", pois '\' é escape
    caminho_storage = (
        "\\" + "\\" + maquina +
        "\\" + conf_storage["pasta_share"]
    )

    return caminho_storage

def procurar_mapeamento_letra(caminho_storage):

    global Gdrive_mapeado

    # Envia comando net use para obter lista de conexão,
    # faz parse e localiza letra mapeada
    # Exemplo:
    # net use
    # Status       Local     Remoto                    Rede
    # -------------------------------------------------------------------------------
    # OK           T:        \\gtpi-sto-02\storage     Microsoft Windows Network
    # OK           W:        \\10.41.84.104\Departamento\setec
    #                                                 Microsoft Windows Network
    # Se caminho_storage==\\gtpi-sto-02\storage, devolve letra T:
    caminho_arquivo_resultado = os.path.join(get_parini('pasta_execucao'), "net_use_consulta.txt")
    comando = "net use"

    # Redireciona resultado para arquivo, para pode examinar o erro
    comando = comando + " >" + caminho_arquivo_resultado + " 2>&1 "

    subprocess.call(comando, shell=True)

    # Verifica se arquivo de resultado foi criado
    if not os.path.exists(caminho_arquivo_resultado):
        print_log("[2305] Comando net use falhou: Arquivo de resultado", caminho_arquivo_resultado, "não encontrado")
        return None

    # Procura por uma letra mapeada
    letra_com_caminho=None
    with open(caminho_arquivo_resultado, mode='r') as file:
        for linha in file:
            # Remove elementos sem utilidade
            linha=linha.replace("Microsoft Windows Network","")
            # Procura por uma linha que indique que o mapamento está ok
            # OK           R:        \\gtpi-sto-01\storage           Microsoft Windows Network
            termos=linha.split()
            if len(termos)==0:
                continue
            if (termos[0]!='OK'):
                # Se não está conectado, despreza a linha de informação de mapeamento
                continue
            if len(termos)<3:
                # Provavelmente é uma linha que não tem unidade, como por exemplo:
                # OK                     \\10.41.87.113\deployment_desenv
                continue
            #print(console_sanitiza_utf8_ok(linha))
            #var_dump(termos)

            letra=termos[1]
            caminho=termos[2]
            if caminho_storage in caminho:
                arquivo_controle = os.path.join(letra, Garquivo_controle)
                if os.path.isfile(arquivo_controle):
                    # Armazena na lista de mapeamentos com drive
                    Gdrive_mapeado[caminho_storage]=letra
                    # Ok, encontrou uma letra mapeada corretamente
                    return letra
                else:
                    print_log("Letra",letra, "está mapeada para", caminho_storage," mas não contém arquivo de controle", Garquivo_controle )

    # Não achou
    print_log("Nenhuma drive (letra) mapeada para", caminho_storage)
    return None


# Desisti desta abordagem, pois não é correta...
# O IPED (interface) tem que funcionar sem precisar de mapeamento de rede
# Efetua storage, e associa uma letra
def acesso_storage_windows_com_letra_drive(conf_storage, utilizar_ip=True, tipo_conexao='consulta'):


    # Verifica se já tem storage mapeado para a letra
    caminho_storage=obter_caminho_storage(conf_storage, utilizar_ip=utilizar_ip)

    # Procurar por caminho no storage
    letra=procurar_mapeamento_letra(caminho_storage)
    #print("Letra=", letra)
    # Se já está mapeado, retorna
    if letra is not None:
        return (True, letra, "")


    # Obter usuario/senha para conexao
    (usuario, senha)=obter_usuario_senha_conexao_storage(conf_storage, tipo_conexao)

    # Montagem do storage
    # --------------------
    resultado_montagem=montar_storage_windows(
        caminho_storage,
        usuario=usuario,
        senha=senha,
        com_letra_drive=True
    )


    # Confere se mapamento foi efetuado com sucesso
    letra = procurar_mapeamento_letra(caminho_storage)
    # Mapeou (sem erro), mas não conseguiu localizar a letra???
    if letra is None:
        return (False, None, "Não foi possível mapear letra para storage: " + resultado_montagem)

    return (True, letra, "")


# Efetua montagem de pasta compartilhada
# caminho : \\10.41.87.239\storage
# usuario: usuário para o qual a pasta foi compartilhada
# senha: Senha para acesso
# Letra para drive, podendo ser:
# '' => Se não é para utilizar letra no mapeamento  (com_letra_drive=False)
# *  => Windows utilizará alguma letra disponível (com_letra_drive=True e letra_drive=None)
# X: => Letra informada no parâmetro (com_letra_drive=True e  letra_drive contém letra selecionada)
def montar_storage_windows(caminho_storage, usuario, senha, com_letra_drive=False, letra_drive=None):

    #print(com_letra_drive)
    #print(letra_drive)
    #print('ponto2389')

    # Definição da letra de drive
    definicao_letra=''
    if com_letra_drive:
        if letra_drive is not None:
            definicao_letra=' ' + letra_drive + ' '
        else:
            definicao_letra = ' * '

    # Conecta no share do storage, utilizando net use.
    # Exemplo:
    # net use \\10.41.87.239\storage /user:sapi sapi
    # Para desmontar (para teste), utilizar:
    # net use \\10.41.87.239\storage /delete
    caminho_arquivo_resultado = os.path.join(get_parini('pasta_execucao'), "net_use_resultado.txt")
    comando = (
        "net use " + definicao_letra + " " + caminho_storage +
        " /user:" + usuario +
        " " + senha
    )
    #print_log('ponto2422: ', comando)

    # Teste de comando, para gerar erro2
    # comando="net use \\\\10.41.87.239\\xxx"
    # debug("Comando net use dummy, apenas para gerar erro: ", comando)

    # Redireciona resultado para arquivo, para pode examinar o erro
    comando = comando + " >" + caminho_arquivo_resultado + " 2>&1 "

    # debug("Conectando com storage")
    # debug(comando)

    if not modo_background():
        print("- Efetuando conexão com storage de destino. Aguarde...")

    subprocess.call(comando, shell=True)

    # Processa arquivo de resultado
    with open(caminho_arquivo_resultado, 'r') as f:
        resultado_montagem = f.read()

    # Simplifica o resultado
    resultado_montagem = resultado_montagem.replace('\r', '')
    resultado_montagem = resultado_montagem.replace('\n', '')
    resultado_montagem = resultado_montagem.replace('  ', '')
    resultado_montagem = resultado_montagem.strip()

    return resultado_montagem


# Recupera usuário e senha para conexão no storage
def obter_usuario_senha_conexao_storage(conf_storage, tipo_conexao='consulta'):

    if tipo_conexao=='atualizacao':
        # Conta e usuário para conexão de atualização
        usuario = conf_storage["usuario"]
        senha = conf_storage["senha"]
    elif tipo_conexao=='consulta':
        usuario = conf_storage["usuario_consulta"]
        senha = conf_storage["senha_consulta"]
    else:
        erro_fatal('[2451] obter_usuario_senha_conexao: tipo_conexao inválido: ', tipo_conexao)

    return usuario, senha

# Verifica se storage já está montado. Se não estiver, monta.
# Retorna:
# - Sucesso: Se montagem foi possível ou não
# - ponto_montagem: Caminho para montagem
# - mensagem_erro: Caso tenha ocorrido erro na montagem
# ========================================================================================================
def acesso_storage_windows(conf_storage, utilizar_ip=True, com_letra_drive=False, tipo_conexao='consulta'):

    global dic_storage
    #print('ponto2471')

    caminho_storage=obter_caminho_storage(conf_storage, utilizar_ip=utilizar_ip)
    caminho_storage_netbios=obter_caminho_storage(conf_storage, utilizar_ip=False)

    # Ponto de montagem implícito
    # Não será mapeado para nenhuma letra, pois pode dar conflito
    ponto_montagem = caminho_storage + "\\"
    #print(caminho_storage)

    debug("Verificando acesso ao storage: ",caminho_storage_netbios)
    arquivo_controle = os.path.join(ponto_montagem, Garquivo_controle)

    # Verifica se storage já está montado
    # -----------------------------------
    montar=True
    if os.path.exists(caminho_storage):
        debug("Storage já estava montado em", caminho_storage_netbios)
        montar=False

    # Obter usuario/senha para conexao
    (usuario, senha)=obter_usuario_senha_conexao_storage(conf_storage, tipo_conexao)

    # Montagem do storage
    # --------------------
    #print('ponto2497 : ', montar)
    if montar:
        resultado_montagem=montar_storage_windows(
            caminho_storage,
            usuario=usuario,
            senha=senha,
            com_letra_drive=False
        )

    # Verifica se montou corretamente
    # -------------------------------
    if not os.path.exists(caminho_storage):
        # Falha
        print_log("Não conseguiu montar storage: ",caminho_storage_netbios)
        # Le comando de resultado e joga no log, para registrar o problema
        msg_log="Erro na conexão com storage: "+resultado_montagem
        print_log(msg_log)
        return False, ponto_montagem, msg_log

    # Confere integridade do storage
    # ------------------------------
    if os.path.isfile(arquivo_controle):
        # Registra que está montado, para posteriormente desmontar
        Gdic_storage[caminho_storage]=caminho_storage_netbios
        debug("Acesso ao storage confirmado através do acesso ao arquivo: ", arquivo_controle)
        return True, ponto_montagem, ""
    else:
        # Falha
        print_log("Storage está montado em", caminho_storage_netbios)
        print_log("Contudo, NÃO foi localizado o arquivo:", arquivo_controle)
        print_log("Isto pode indicar que o storage não foi montado com sucesso ou que está corrompido")
        return False, ponto_montagem, "Storage sem arquivo de controle"

    # Não deveria chegar neste ponto
    return False, ponto_montagem, "[1658] Erro inesperado Comunique desenvolvedor"



def  desconectar_todos_storages():

    for caminho_storage in Gdic_storage:

        nome_storage=Gdic_storage[caminho_storage]

        # Desconect share
        # net use \\gtpi-sto-01\storage /del /Y
        # /Y => Não pede confirmação se houver algum arquivo aberto...fecha mesmo
        comando = (
            "net use " + caminho_storage + " /del /Y 1>nul 2>nul"
        )

        #debug("Desconectando do storage")
        #debug(comando)
        subprocess.call(comando, shell=True)

        # Verifica se montou
        if not os.path.exists(caminho_storage):
            # Ok, conseguiu desconectar
            debug("Desconectado do storage ", nome_storage)
        else:
            # Registra em log que não foi possível, mas não tem mais o que fazer,
            # pois já está saindo do programa
            debug("Não foi possível desconectar do storage ", nome_storage)


# ===================================================================================================================
# Conexão interativa com storage
#
# Estas funções abaixo devem ser utilizadas apenas por programas interativos (sapi_cellebrite, sapi_laudo, etc)
# O correto seria jogar estas funções para uma outra biblioteca, junto com menu e outras funções interativas
#
# ===================================================================================================================

# Efetua conexão no ponto de montagem, dando tratamento em caso de problemas
def conectar_ponto_montagem_storage_ok(dados_storage,
                                       utilizar_ip=True,
                                       com_letra_drive=False,
                                       tipo_conexao='consulta'):

    nome_storage = dados_storage['maquina_netbios']
    print("- Verificando conexão com storage",nome_storage,": Aguarde...")

    if com_letra_drive:
        (sucesso, ponto_montagem, erro) = acesso_storage_windows_com_letra_drive(
                dados_storage,
                utilizar_ip=utilizar_ip,
                tipo_conexao=tipo_conexao
        )
    else:
        (sucesso, ponto_montagem, erro) = acesso_storage_windows(
            dados_storage,
            utilizar_ip=utilizar_ip,
            tipo_conexao=tipo_conexao
        )

    if not sucesso:
        print("- Acesso ao storage " + nome_storage + " falhou")
        print(erro)
        print("- Verifique se servidor de storage está ativo e acessível (rede)")
        print("- Sugestão: Conecte no servidor via VNC com a conta consulta")
        return None

    # Ok, tudo certo
    print_tela("- Acesso ao storage confirmado em", ponto_montagem)
    return ponto_montagem

# Efetua conexão no storage mapeando para um letra (drive)
# A inexistência de uma letra limita o funcionamento de alguns programas (exemplo: bat)
# Logo, sempre que fazemos conexão para consulta mapeamos para um letra (drive)
def conectar_storage_consulta_ok(dados_storage):

    #print('ponto2007')
    ponto_montagem = conectar_ponto_montagem_storage_ok(
        dados_storage=dados_storage,
        utilizar_ip=False,
        com_letra_drive=True,
        tipo_conexao='consulta'
    )

    return ponto_montagem


def conectar_storage_atualizacao_ok(dados_storage):

    ponto_montagem = conectar_ponto_montagem_storage_ok(
        dados_storage=dados_storage,
        utilizar_ip=True,
        tipo_conexao='atualizacao'
    )

    return ponto_montagem



# =======================================================================================================
# Movimentação de pastas no storage
# =======================================================================================================

#
def mover_pasta_storage(pasta_origem, pasta_destino):

    # Pasta de origem tem que existir
    if not os.path.exists(pasta_origem):
        raise Exception("[3307] Pasta de origem não localizada: ", pasta_origem)

    # Pasta de destino não pode existir
    if os.path.exists(pasta_destino):
        raise Exception("[3310] Pasta de origem não localizada: ", pasta_origem)

    # Verifica se a pasta pai existe, e se não existir cria
    pasta_destino=pasta_destino.replace("\\","/")
    partes=pasta_destino.split("/")
    pasta_pai='/'.join(partes[:-1])
    if not os.path.exists(pasta_pai):
        os.makedirs(pasta_pai)
        print_log("Criada pasta pai para movimentação:", pasta_pai)

    print_log("Movendo pasta ", pasta_origem, "para", pasta_destino)
    os.rename(pasta_origem, pasta_destino)
    print_log("Movido com sucesso")


# =======================================================================================================
# LIXEIRA
# =======================================================================================================

# Esta rotina deve ser utiliza por programas rodando no servidor
# Para programas rodando no cliente, utilizar mover_lixeira_UNC
def mover_lixeira(pasta_mover):

    print_log("Movendo para lixeira/servidor: ", pasta_mover)

    data_hora = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    # Obtém o caminho absoluto. Por exemplo:
    # ../Memorando_1880-17_CF_PR-26/item01Arrecadacao01a/item01Arrecadacao01a_imagem
    # E:/storage/Memorando_1880-17_CF_PR-26/item01Arrecadacao01a/item01Arrecadacao01a_imagem
    caminho_absoluto=os.path.abspath(pasta_mover)
    # Remove drive
    caminho_absoluto=caminho_absoluto[3:]

    #var_dump(caminho_absoluto)
    #die('ponto2876')


    raiz_storage = get_parini('raiz_storage')
    pasta_lixeira = montar_caminho(raiz_storage,
                                   "lixeira",
                                   data_hora,
                                   caminho_absoluto)

    #var_dump(pasta_lixeira)
    #die('ponto2907')


    #os.path.abspath(pasta)
    #var_dump(pasta_lixeira)
    #die('ponto2876')

    # Criar a pasta pai
    partes=pasta_lixeira.split('\\')
    pasta_pai='/'.join(partes[:-1])
    if not os.path.exists(pasta_pai):
        os.makedirs(pasta_pai)

    #var_dump(pasta_pai)
    #die('ponto2892')

    os.rename(pasta_mover, pasta_lixeira)
    print_log("Movido com sucesso para lixeira em: ", pasta_lixeira)

    return (True, pasta_lixeira)


def mover_lixeira_UNC(pasta_mover):

    erro="[3321] Erro indeterminado"
    try:
        return _mover_lixeira_UNC(pasta_mover)
    except OSError as error:
        print_log("Mover para lixeira falhou: ", str(error))
        erro=str(error)
        # Tratamento especial para erros mais comuns
        if error.errno==13:
            # Erro Windows para Acesso Negado
            erro="Acesso negado: Normalmente isto ocorre quando a pasta está aberta no explorer ou algum arquivo da pasta está em uso"
    except BaseException as e:
        erro=traceback.format_exc()

    # Ocorreu um erro
    return (False, None, erro)


def _mover_lixeira_UNC(pasta_mover):

    print_log("Movendo para lixeira via SMB: ", pasta_mover)

    # Verifica se pasta de origem existe
    if not os.path.exists(pasta_mover):
        erro=texto("Pasta de origem não existe", pasta_mover)
        return (False, None, erro)

    # Prepara pasta de destino
    data_hora = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    if "storage" not in pasta_mover:
        erro="Não foi encontrado string 'storage' no caminho"
        return (False, None, erro)

    componente_lixeira = "\\lixeira\\"+data_hora+"\\"
    pasta_lixeira = str(pasta_mover).replace("storage\\", "storage" + componente_lixeira)

    # Criar a pasta pai na lixeira
    partes=pasta_lixeira.split('\\')
    pasta_pai='/'.join(partes[:-1])
    if not os.path.exists(pasta_pai):
        os.makedirs(pasta_pai)

    # Move, através de rename
    os.rename(pasta_mover, pasta_lixeira)
    print_log("Movido com sucesso para lixeira em: ", pasta_lixeira)

    # Tudo certo
    return (True, componente_lixeira, None)

# =======================================================================================================
# Controle de execução concorrente
# =======================================================================================================

# Controle de concorrência
# para garantir que existe apenas uma instância de um progrma rodando (por exemplo: sapi_iped)
def procura_pid_python(pid_prog):

    # Verifica se processo ainda está rodando
    print_log("Procurando por pid [", pid_prog, "] que esteja rodando python")
    a = os.popen("tasklist").readlines()
    for x in a:
        nome_processo = x[0:28]
        pid = x[28:34]
        pid = pid.strip()
        if not pid.isdigit():
            # Se não é número, despreza
            continue

        # Se números de processo coincidem,
        # e trata-se de um programa python (para garantir que o pid não foi reutiliza por alguma outra coisa)
        # Isto aqui não é um teste perfeito, mas considerando o cenário de execução, deve funcionar sem problemas
        if (int(pid) == int(pid_prog)):
            print_log("pid alvo localizado: ", pid, " - ", nome_processo)
            if ("python" in nome_processo):
                # ok, encontrado e rodando python
                print_log("Ok, processo rodando python")
                return True
            else:
                print_log(
                    "Processo NÃO está rodando python. Provavelmente foi reutilizado pelo SO.")
                return False


    # Não achou
    print_log("Neste PID não está rodando python")
    return False

# Se encontrar, retorna verdadeiro
def existe_outra_instancia_rodando(caminho_arquivo_pid):

    # Verifica se já está rodando
    if os.path.isfile(caminho_arquivo_pid):
        # Recupera pid armazenado no arquivo
        f = open(caminho_arquivo_pid, "r")
        pid_prog = f.readline().strip()
        f.close()
        if not pid_prog.isdigit():
            # Isto não deveria acontecer.
            # Neste caso, vamos ignorar, pois se abortar, não vai rodar nunca
            print_log("AVISO: PID armazenado em [", caminho_arquivo_pid, "] armazenado não contém número: [", pid_prog, "]")
        else:
            if procura_pid_python(pid_prog):
                print_log("Este programa já está rodando, no processo [", pid_prog, "]")
                return True
            else:
                print_log("Tudo bem. Não existe outra instância rodando. Pode prosseguir")

    # Não está rodando
    # Grava pid em arquivo, para teste de simultaneidade
    # ------------------------------------------------------------------------
    f = open(caminho_arquivo_pid, "w")
    f.write(str(os.getpid()))
    f.close()

    #
    return False


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
        print("- Operação interrompida pelo usuário com <CTR>-<C>")
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


def exibe_menu_comandos(menu, comandos):
    formato_saida = "%10s : %s"
    for key in menu:
        print(formato_saida % (key.upper(), comandos[key]))
    print()


# Recebe e confere a validade de um comando de usuário
# ----------------------------------------------------------------------------------------------------------------------
def _receber_comando(menu_comando):

    comandos = menu_comando['comandos']
    cmd_exibicao = menu_comando.get('cmd_exibicao',[])
    cmd_navegacao = menu_comando['cmd_navegacao']
    cmd_item = menu_comando['cmd_item']
    cmd_geral = menu_comando['cmd_geral']
    cmd_diagnostico = menu_comando['cmd_diagnostico']

    # Adiciona alguns comandos fixos, que valem para qualquer programa
    if '<ENTER>' not in cmd_exibicao:
        comandos['<ENTER>']='Exibir lista de tarefas atuais (sem Refresh no servidor)'
        cmd_exibicao.append('<ENTER>')
    if 'nn' not in cmd_navegacao:
        comandos['nn'] = 'Posicionar no elemento com Sq=nn da lista (Exemplo: 5, posiciona no quinto elemento)'
        cmd_navegacao.append('nn')

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
            cls()
            print("Lista de comandos disponíveis:")
            print("==============================")
            # Comandos de exibição
            if len(cmd_exibicao)>0:
                print()
                print("Comandos de exibição da situação:")
                print("----------------------------------")
                exibe_menu_comandos(cmd_exibicao, comandos)

            # Exibe ajuda para comando
            print("Comandos de Navegação:")
            print("----------------------")
            exibe_menu_comandos(cmd_navegacao, comandos)

            print("Processamento da tarefa corrente (marcada com =>):")
            print("--------------------------------------------------")
            exibe_menu_comandos(cmd_item, comandos)

            print("Diagnóstico de problemas:")
            print("-------------------------")
            exibe_menu_comandos(cmd_diagnostico, comandos)

            print("Comandos gerais:")
            print("----------------")
            exibe_menu_comandos(cmd_geral, comandos)

        elif (comando_recebido == ""):
            # print("Para ajuda, digitar comando 'h' ou '?'")
            return ("", "")
        else:
            if (comando_recebido != ""):
                print("Comando (" + comando_recebido + ") inválido")
                print("Para obter ajuda, digitar comando 'h' ou '?'")

    return (comando_recebido, argumento_recebido)


# ====================================================================================================================
# Sanitização para UTF8
# ====================================================================================================================

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

# Sanitiza strings em UTF8, substituindo caracteres não suportados pela codepage da console do Windows por '?'
# Normalmente a codepage é a cp850 (Western Latin)
# Retorna o que dá, ignorando os erroa
def console_sanitiza_utf8_ok(dado):
    (texto, qtd_alteracoes) = console_sanitiza_utf8(dado)
    # Ignora se teve ou não alterações
    return texto

def print_sanitizado(dado):
    (texto, qtd_alteracoes) = console_sanitiza_utf8(dado)
    print(texto)
    if qtd_alteracoes>0:
        print(qtd_alteracoes, "para sanitizacao de uft8")

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

def var_dump_console(d):
    console_dump_formatado(d)


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

    def selecionar_pasta(self, titulo=None):
        if titulo is None:
            titulo="Selecionar pasta"
        dir_opt = {}
        dir_opt['title'] = titulo
        self.directory = tkinter.filedialog.askdirectory(**dir_opt)
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



# -----------------------------------------------------------------------------------
# Armazenamento de dados em arquivo sapi.info
# -----------------------------------------------------------------------------------

# Guarda variavel com valor no arquivo sapi.info da pasta indicada
# Se variável já existir, adiciona, caso contrário, atualiza
# Retorna True/False
# ----------------------------------------------------------------------
def sapi_info_set(pasta_sapi_info, variavel, valor):

    # Le situaçao atual, se existir
    sapi_info = sapi_info_carregar(pasta_sapi_info)
    if sapi_info is None:
        # Se não conseguir carregar, inicializa variável para armazenamento
        sapi_info=dict()

    # Atualiza variável
    sapi_info[variavel]=valor

    # Grava
    return sapi_info_gravar(pasta_sapi_info, sapi_info)

# Recupera valor da variável de sapi.info da pasta indicada
# Se não existir, retorna None
# ----------------------------------------------------------------------
def sapi_info_get(pasta_sapi_info, variavel):

    # Le situaçao atual, se existir
    sapi_info = sapi_info_carregar(pasta_sapi_info)
    if sapi_info is None:
        return None

    valor = sapi_info.get(variavel, None)
    return valor


# Grava sapi.info na pasta indicada com o conteúdo fornecido (sapi_info)
# Retorna True/False
def sapi_info_gravar(pasta_sapi_info, sapi_info):

    # Monta caminho completo para arquivo
    caminho_sapi_info=montar_caminho(pasta_sapi_info,'sapi.info')

    try:
        # Grava em sapi_info
        arq = open(caminho_sapi_info, "w")
        json.dump(sapi_info, arq, indent=4)
        arq.close()
    except BaseException as e:
        texto_erro = texto("Gravação de arquivo sapi_info",
                           caminho_sapi_info,
                           "falhou, erro: ",
                           str(e)
                           )
        print_log(texto_erro)
        return False

    # Tudo certo
    return True



# Carrega dados (json) do arquivo sapi.info
# ----------------------------------------------------------------------
def sapi_info_carregar(caminho_sapi_info):

    if "sapi.info" not in caminho_sapi_info:
        caminho_sapi_info = montar_caminho(caminho_sapi_info, 'sapi.info')

    # Não tem arquivo de estado
    if (not os.path.isfile(caminho_sapi_info)):
        return None

    # Le dados do arquivo e fecha
    try:
        arq = open(caminho_sapi_info, "r")
        sapi_info = json.load(arq)
        arq.close()
    except BaseException as e:
        texto_erro=texto("Leitura de arquivo sapi_info",
                         caminho_sapi_info,
                         "falhou, erro: ",
                         str(e)
                         )
        print_log(texto_erro)
        return None

    # Tudo certo
    return sapi_info

# -----------------------------------------------------------------------------------
# TABLEAU (TD3)
# -----------------------------------------------------------------------------------

# Faz parse no arquivo de log do Tableau e extrai informações relevantes para laudo
# Recebe o arquivo de log, e o item correspondente
# Retorna:
#  Sucesso: True/False
#  mensagem de erro: string
#  dados_relevantes: dict
def tableau_parse_arquivo_log(caminho_arquivo_log, item):
    try:
        return exec_tableau_parse_arquivo_log(caminho_arquivo_log, item)

    except Exception as e:
        erro = "Parse de log do Tableau falhou: " + str(e)
        trc_string=traceback.format_exc()
        print_log(trc_string)
        return (False, erro, {})

def exec_tableau_parse_arquivo_log(caminho_arquivo_log, item):

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
    bloco_reconhecido=dict()
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
                    bloco_reconhecido[id_bloco]=True
                    break

            # Tem que ter um bloco para efetuar a busca de tags
            if id_bloco is None:
                continue

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

    # Verifica se possui linha identificador do TD3
    # -----------------------------Start of TD3 Log Entry-----------------------------
    achou_start = bloco_reconhecido.get('start', False)
    if not achou_start:
        erro = "Bloco start do TD3 não foi reconhecido"
        return (False, erro, {})

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
        #'destination:share_name': 'sapiStorageDestino',

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

    dcomp['sapiTipoComponente'] = 'armazenamento'
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


# ===================================================================================
# Tempo
# ===================================================================================
# Converte segundo para formato humano, para previsão de conclusão de tarefa
def converte_segundos_humano(sec):
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    # Se só tem segundo
    if sec<60:
        return ('%s seg') % (s)

    # Menor que uma hora, mostra apenas os minutos
    if (sec<3600):
        return ('%s min') % (m)

    formato = r'%d h %02d min'

    # Zero dias
    if d == 0:
        return formato % (h, m)

    # Mais de um dia
    return ('%d dia %d h') % (d, h)


# ===================================================================================
# Exclusão de processos
# ===================================================================================

# Exclui os filhos de um processo e o próprio processo selecionado
def kill_processo_completo(pid):
    print_log("Excluindo processo", pid, "e todos os seus descendentes")
    kill_pai_e_filhos(pid, including_parent=True)


# Exclui os filhos de um processo e o próprio processo selecionado
def kill_pai_e_filhos(pid, including_parent=True):
    print_log("Excluindo recursivamente árvore de processos iniciando com pai:", pid)
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    for child in children:
        print_log("Eliminando processo ", child.pid, "[", child.name(),"]")
        child.kill()
    gone, still_alive = psutil.wait_procs(children, timeout=15)
    if including_parent:
        print_log("Eliminando processo (pai)", parent.pid, "[", parent.name(),"]")
        parent.kill()
        parent.wait(5)


# *********************************************************************************************************************
# *********************************************************************************************************************
#                  FINAL DO SAPILIB
# *********************************************************************************************************************
# *********************************************************************************************************************
