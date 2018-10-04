# -*- coding: utf-8 -*-
# ===== PYTHON 3 ======
#
# =======================================================================
# SAPI - Sistema de Apoio a Procedimentos de Informática
# 
# Componente: sapi_demo_agente
# Objetivo: Agente de demonstração, para servir como
#           base para implementação de agentes (IPED, IEF, etc)
# 
# Funcionalidades:
#  - Simula qualquer agente, recebendo como parâmetro o tipo
#    de tarefa a ser executada.
#  - Conexão com o servidor SAPI para obter tarefa a ser executada.
#  - Atualiza status
#  - Simula sucesso e insucesso
#
#
# Histórico:
#  - v0.1 : Inicial
#  - v0.3 : Convertido para python3
#  - v0.4 : Inserido opção para seleção de dispositivo (uso no Tableau)
#           - Alterada função sapisrv_obter_iniciar_tarefa
#           - Conversão para durante desenvolvimento utilizar import sapi
#  - v0.5: Atualização de dados relevantes (json)
#  - V0.6: Utiliza sapilib_0_6 que tem melhorias de tolerância falha
# =======================================================================

# ======================================================================
# Verifica se está utilizando versão correta do Python
# ======================================================================
from __future__ import print_function

import platform
import sys

# Testa se está rodando a versão correta do python
if sys.version_info <= (3, 0):
    erro = "Versao do intepretador python (" + str(platform.python_version()) + ") incorreta.\n"
    sys.stdout.write(erro)
    sys.stdout.write("Este programa requer Python 3 (preferencialmente Python 3.5.2).\n")
    sys.exit(1)

# ======================================================================
# Módulos necessários
# ======================================================================
import socket
import time
import random
import hashlib

# =======================================================================
# GLOBAIS
# =======================================================================
Gversao = "0.5"

Gdesenvolvimento = True  # Ambiente de desenvolvimento
# Gdesenvolvimento=False #Ambiente de producao

# Base de dados (globais)
GdadosGerais = {}  # Dicionário com dados gerais
Gstorages = []  # Lista de tarefas

# Diversos sem persistência
Gnome_agente = "Não definido"

# Controle de tempos/pausas
GtempoEntreAtualizacoesStatus = 180
GdormirSemServico = 15
# GmodoInstantaneo=False
GmodoInstantaneo = True

# Log
GregistrarLogURL = True

# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi.py, para evitar dependência
from sapilib_0_5_4 import *


# **********************************************************************
# PRODUCAO 
# **********************************************************************




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
    param = {}
    param['tipo'] = tipo
    param['execucao_nome_agente'] = Gnome_agente
    if (storage is not None):
        param['storage'] = storage
    if (dispositivo is not None):
        param['dispositivo'] = dispositivo

    # Invoca sapi_srv
    (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
        "sapisrv_obter_iniciar_tarefa.php", param)

    # Talvez seja um erro intermitente.
    # Agente tem que ser tolerante a erros, e ficar tentando sempre.
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
def atualizar_status_tarefa(codigo_tarefa, codigo_situacao_tarefa, status, dados_relevantes=None):
    # Parâmetros
    param = {'codigo_tarefa': codigo_tarefa,
             'codigo_situacao_tarefa': codigo_situacao_tarefa,
             'status': status,
             'execucao_nome_agente': Gnome_agente
             }
    if (dados_relevantes != None):
        dados_relevantes_json = json.dumps(dados_relevantes, sort_keys=True)
        param['dados_relevantes_json'] = dados_relevantes_json

    # Invoca sapi_srv
    (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
        "sapisrv_atualizar_tarefa.php", param, registrar_log=GregistrarLogURL)

    # Registra em log
    if (sucesso):
        print_log_dual("Atualizado status no servidor: ", status)
    else:
        # Se der erro, registra no log e prossegue (tolerância a falhas)
        print_log_dual("Não foi possível atualizar status no servidor", msg_erro)

    return sucesso


# Separa pasta do nome do arquivo em um caminho
# Entrada:
#  Memorando_19317-16_Lava_Jato_RJ-12/item04Arrecadacao06/item04Arrecadacao06_imagem/item04Arrecadacao06.E01
# Saída:
#  - pasta: Memorando_19317-16_Lava_Jato_RJ-12/item04Arrecadacao06/item04Arrecadacao06_imagem
#  - nome_arquivo: item04Arrecadacao06.E01
# ----------------------------------------------------------------------
def decompoeCaminho(caminho):
    partes = caminho.split("/")

    nome_arquivo = partes.pop()
    pasta = "/".join(partes)

    return (pasta, nome_arquivo)


# Faz um pausa por alguns segundos
# Dependendo de parâmetro, ignora a pausa 
def dormir(tempo):
    if (not GmodoInstantaneo):
        time.sleep(tempo)
    else:
        print_log_dual("Sem pausa...modo instantâneo em demonstração")


# ======================================================================
# Código para teste
# ======================================================================



'''
# Teste json
url=GconfUrlBaseSapi + "sapisrv_teste_json_ansi.php"
f = urllib.urlopen(url)
print f.read()
d=json.loads(f.read())
#print djson["a"]
Gpp.pprint(d)
print d["endereco"]["numero"]
die('ponto97')
'''

# ======================================================================
# Rotina Principal 
# ======================================================================

# Iniciando
# ----------------------------------------------------------------------
print_ok()
print_ok("SAPI - Demo Agente (Versao " + Gversao + ")")
print_ok("=========================================")
print_ok()
print_log_dual('Iniciando sapi_demo_agente - ', Gversao)

exemplo = (
    "python sapi_demo_agente.py imagem table%\n" +
    "Parâmetro 1: Tipo de procedimento\n"
    "Parâmetro 2 (opcional): Dispositivo em que o procedimento será aplicado. É possível informar uma expressão para ser aplicado com comando like no sql (ex: Table%)")

# Recupera parâmetros de entrada
# Isto é aqui apenas para simular.
# Em agentes reais, cada um já deve saber quais procedimentos é capas
# de executar
if (len(sys.argv)) < 2:
    print_log_dual("Informe o tipo de procedimento a ser simulado no formato abaixo:\n" + exemplo)
    sys.exit()

arg_tipo = sys.argv[1]
arg_dispositivo = None
if (len(sys.argv) >= 3):
    arg_dispositivo = sys.argv[2]

# Testa comunicação com servidor SAPI
# -----------------------------------
# Em desenvolvimento não executa, para ganhar tempo
if not Gdesenvolvimento:
    assegura_comunicacao_servidor_sapi()

# Define nome do agente, que será repassado ao servidor sapi
Gnome_agente = socket.gethostbyaddr(socket.gethostname())[0]

# Por enquanto, fica em loop eterno
# Para a versão 2.0, é interessante pensar um mecanismo para cancelar
# o agente (Talvez um watchdog/fork, que fique recebendo comandos do servidor)
# Este watchdog também serviria para reiniciar o programa, caso 
# este acabe caindo por algum outro motivo
while (True):

    # Requisita uma tarefa
    # Existem vários parâmetros opcionais (storage, tamanhos), ver funçao.
    print_log_dual("Solicitando tarefa ao servidor")
    (disponivel, tarefa) = sapisrv_obter_iniciar_tarefa(arg_tipo, dispositivo=arg_dispositivo)

    # Se não tem nenhuma tarefa disponível, dorme um pouco
    if not disponivel:
        print_log_dual("Servidor informou que não existe tarefa para processamento. Dormindo (", GdormirSemServico,
                       " segundos)")
        dormir(GdormirSemServico)
        continue

    # Ok, temos trabalho a fazer
    # ------------------------------------------------------------------

    # O sistema retorna um conjunto bastante amplo de dados
    # Os mais relevantes estão aqui
    codigo_tarefa = tarefa["codigo_tarefa"]  # Identificador único da tarefa
    caminho_origem = tarefa["caminho_origem"]
    caminho_destino = tarefa["caminho_destino"]

    print_log_dual("Processando tarefa: ", codigo_tarefa)

    # Para ver o conjunto completo, descomentar a linha abaixo
    # var_dump(tarefa)

    # Montar storage
    # ------------------------------------------------------------------
    # Teria que montar o storage (caso a montagem seja dinâmica)
    # Os dados do storage estão em tarefa["dados_storage"]

    # Conferir se pasta/arquivo de origem está ok
    # ------------------------------------------------------------------
    # O caminho de origem pode indicar um arquivo (.E01) ou uma pasta
    # Neste ponto, seria importante verificar se esta origem está ok
    # Ou seja, se existe o arquivo ou pasta de origem
    print_log_dual("Caminho de origem (", caminho_origem, "): localizado")

    # Criar pasta de destino
    # ------------------------------------------------------------------
    # Teria que criar a pasta de destino, caso ainda não exista
    # Se a pasta de destino já existe...opa, pode ter algo errado.
    # Neste cenário, teria que conferir se a pasta não tem nada
    # de útil (indicando alguma concorrência....ou processo abortado)
    print_log_dual("Caminho de destino (", caminho_destino, "): Criado")

    # Fork para executar e esperar resposta
    # ------------------------------------------------------------------
    # Em um agente de verdade, aqui teria que fazer um fork
    # O programa secundário iria invocar o programa externo que
    # executa a tarefa, e o programa principal se
    # encarregaria de controlar a execução
    print_log_dual("Invocando programa ", arg_tipo, " e aguardando resultado")
    # pid = os.fork()
    # if pid == 0:
    #	print_log_dual("invocado programa: "+comando)
    #	# Executa o programa externo e fica esperando o resultado
    #	os.system(comando) # Se mata o pai, morre também...melhorar isto
    #	print_log_dual("Programa externo encerrou")
    #	sys.exit()



    # Programa principal controla a execução
    # ------------------------------------------------------------------
    # Vamos simular o acompanhamento da execução
    # É importante escolher algum critério que forneça um indicativo de
    # progresso relevante.
    # Na pior das hipóteses, utilizar o tamanho da pasta de destino
    # Aqui existiria uma loop, finalizado apenas se houve sucesso ou
    # insucesso
    random.seed()
    terminou = False
    rant = 0
    while not terminou:

        # Simula andamento/sucesso/insucesso, através de um randômico
        # para tornar o demo mais realista
        r = random.randint(1, 100)
        if (r < rant):
            # Tem que avançar
            continue
        # print r
        rant = r

        # Está em andamento, atualiza status
        # É importante que a atualização do status não seja muito intensa
        # pois isto pode sobrecarregar o servidor
        # Um intervalo de 3 minutos parece ser uma boa idéia
        # para as modificações de andamento
        # Se for finalizado (sucesso ou insucesso), pode atualizar imediatamente
        if (r <= 89):
            texto_status = str(r) + "% de progresso"
            codigo_situacao_tarefa = GEmAndamento
            atualizar_status_tarefa(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=codigo_situacao_tarefa,
                status=texto_status
            )
            # Uma pequena pausa, e continua para a próxima simulação de andamento
            # Cada simulação deve demorar entre 90 e 100 segundos
            dormir(100 - r)
            continue;

        # Simula sucesso, 90% de probabilidade no demo
        if (r >= 90):

            # Simulação de sucesso, 90% de probabilidade no demo (90 a 99)
            if (r <= 99):
                texto_status = "Finalizado com sucesso"
                codigo_situacao_tarefa = GFinalizadoComSucesso

                # Simulação de hash
                # A idéia é que cada agente calcule o hash relativo
                # aos dados da tarefa processada.
                # No laudo será exibido o conjunto completo de todos os hashes
                # de todas as tarefas
                # Uma vez que tanto o cálculo dos hashes como a geração do laudo
                # são automatizados, não existe desvantagem (exceto algum volume
                # de dados a mais no laudo) em disponibilizar vários hashes.
                # E existe uma vantagem potencial, pois quanto maior for a diversidade
                # de hashes, maior a probabilidade de que algum hash possa ajudar
                # a resolver alguma dúvida sobre integridade que venha a surgir no futuro
                texto_random = 'texto_randomico' + str(random.randint(1, 1000))
                valor_hash = hashlib.md5(texto_random.encode('utf-8')).hexdigest()

                h = {}
                h["sapiHashDescricao"] = "Hash do arquivo listaArquivos.csv (gerado por " + arg_tipo + ")"
                h["sapiHashValor"] = valor_hash
                h["sapiHashAlgoritmo"] = "MD5"
                lista_hash = [h]

                # Simula versão do software
                softwareVersao = "SoftawareX 4.15"
                if ("iped" in arg_tipo):
                    softwareVersao = "IPED 3.11"
                elif ("ief" in arg_tipo):
                    softwareVersao = "IEF 6.45"

                # O campo sapiSoftwareVersao deve sempre ser informado
                # Os demais, irão variar de acordo com o software executado
                dados_relevantes = {}
                # Existe a possibilidade de armazenar outros dados,
                # que não sejam para laudo, mas no momento não temos
                # utilidade para este recurso
                # Logo, a única entrada no dicionário de dados relevantes
                # será 'laudo'
                dados_relevantes['laudo'] = {
                    'sapiSoftwareVersao': softwareVersao,
                    'sapiItensProcessados': '204572',
                    'sapiItensComErro': '0',
                    'sapiHashes': lista_hash
                }

            else:  # (r==100), Simula falha, 10% de probabilidade
                texto_status = "Falhou - abortou (simulado)"
                codigo_situacao_tarefa = GAbortou

            # Se a atualização falhar, fica tentando até conseguir
            # Se for problema transiente, vai resolver
            # Caso contrário, algum humano irá mais cedo ou mais tarde intervir
            while not atualizar_status_tarefa(codigo_tarefa=codigo_tarefa,
                                              codigo_situacao_tarefa=codigo_situacao_tarefa,
                                              status=texto_status,
                                              dados_relevantes=dados_relevantes
                                              ):
                print_log_dual("Falhou atualização de status de sucesso. Tentando novamente")
                dormir(60)  # Tenta novamente em 1 minuto

            terminou = True  # Abandona loop de verificação de situação
            print_log_dual("Dormindo após concluir...para dar chance a outros de pegar tarefas...apenas teste")
            dormir(30)  # Uma pausa apenas para teste..poder consultar sem nenhum agente trabalhando
            continue;


            # Fim do while

# Finaliza
print_ok()
print_ok("FIM SAPI - Demo Agente (Versao " + Gversao + ")")
print_ok()
