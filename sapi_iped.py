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
# ======================================================================================================================
# TODO:
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
    import hashlib
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
Gprograma = "sapi_iped"
Gversao = "1.0"

# Controle de tempos/pausas
GtempoEntreAtualizacoesStatus = 180
GdormirSemServico = 10 #60
GmodoInstantaneo=False
#GmodoInstantaneo = True



# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi.py, para evitar dependência
from sapilib_0_6 import *


# **********************************************************************
# PRODUCAO 
# **********************************************************************



# ======================================================================
# Funções auxiliares
# ======================================================================

# Faz um pausa por alguns segundos
# Dependendo de parâmetro, ignora a pausa
def dormir(tempo):
    if (not GmodoInstantaneo):
        print_log_dual("Dormindo por ", tempo, " segundos")
        time.sleep(tempo)
    else:
        print_log_dual("Sem pausa...modo instantâneo em demonstração")

# Inicialização do agente
# Procedimento de inicialização
# Durante estes procedimento será determinado se comunicação a com servidor está ok,
# se este programa está habilitado para operar com o servidor, etc
# Existe um mecanismo para determinar automaticamente se será atulizado o servidor de desenvolvimento ou produção
# (ver documentação da função). Caso prefira definir manualmente, adicione ambiente='desenv' (ou 'prod')
# O nome do agente também é determinado por default através do hostname.
# ---------------------------------------------------------------------------------------------------------------------
def inicializar():

    # Fica em loop até obter alguma conclusão sobre a inicialização,
    # pois o servidor pode momentaneamente não estar disponível (problema de rede por exemplo)
    while True:

        try:
            sapisrv_inicializar(Gprograma, Gversao)  # Outros parâmetros: nome_agente='xxxx', ambiente='desenv'

            # Tudo certo
            print_log_dual("Inicialização efetuada")
            break

        except SapiExceptionFalhaComunicacao as e:
            # Aborta
            print_log_dual("Falhou comunicação com servidor durante inicialização (Rede ok?)", e)
            dormir(GdormirSemServico)
            print_log_dual("Tentando inicialização novamente")
            continue

        except SapiExceptionProgramaDesautorizado as e:
            # Aborta
            print_log_dual("Programa/versão não foi autorizado pelo servidor: ", e)
            # Neste caso, tem que encerrar o programa, para se auto-atualizar, ou algo similar
            sys.exit(1)

        except SapiExceptionAgenteDesautorizado as e:
            # Aborta
            print_log_dual("Agente (máquina) desautorizado: ", e)
            print_log_dual("Se esta é uma nova máquina, efetue o registro da mesma no sistema")
            sys.exit(1)

        except BaseException as e:
            # Alguma outra coisa...não deveria ocorrer, mas se ocorrer é melhor abortar aqui
            print_log_dual("Erro inesperado e fatal na inicialização: " + str(e))
            print("Para mais detalhes consulte o arquivo de log (sapi_log.txt)")
            sys.exit(1)


# Monta lista de tipos de IPED que serão executados
# Verifica se a instalação para cada tipo está ok
def montar_lista_tipos_iped():
    lista=list()

    # IPED básico
    iped=dict()
    iped["tipo"]='iped-basico';
    iped["pasta_programa"]='C:\\iped_3_11';
    lista.append(iped)

    # IPED com OCR
    iped=dict()
    iped["tipo"]='iped-ocr';
    iped["pasta_programa"]='C:\\iped_ocr_3_11';
    lista.append(iped)


    return lista

# Fica em loop de execução de tarefa
# Encerra apenas se houver algum erro que impeça o prosseguimento
def executar_uma_tarefa(lista_ipeds):

    # Todo: Fazer loop para os diversos tipos de IPED aqui
    for i in lista_ipeds:
        #var_dump(i)
        #die('ponto162')
        tipo_iped=i["tipo"]
        pasta_programa=i["pasta_programa"]

        # Requisita uma tarefa
        # Existem vários parâmetros opcionais (storage, tamanhos), ver funçao.
        print_log_dual("Solicitando tarefa ao servidor para ", tipo_iped)
        # Todo: Pegar o hostname da máquina e utilizar como storage...isto faz com que o sapi_iped só atue no storage aonde estiver instalado
        # Todo: Depois isto tem que se tornar configurável
        (disponivel, tarefa) = sapisrv_obter_iniciar_tarefa(tipo_iped)

        if disponivel:
            # Se já encontrou um tarefa, interrompe
            break;

    # Para a versão 2.0, será implementado também um mecanismo de retomada, utilizado pelo agente para retomar
    # tarefas interrompidas (por falta de energia por exemplo)
    # Logo, aqui será necessário verificar se a tarefa já estava em andamento, e tomara as medidas necessárias
    # (continuar, ou reinicar se for o caso)

    # Se não tem nenhuma tarefa disponível, não tem o que fazer
    if not disponivel:
        print_log_dual("Servidor informou que não existe tarefa para processamento para este programa")
        return

    # Ok, temos trabalho a fazer
    # ------------------------------------------------------------------

    # O sistema retorna um conjunto bastante amplo de dados
    # Os mais relevantes estão aqui
    codigo_tarefa = tarefa["codigo_tarefa"]  # Identificador único da tarefa
    caminho_origem = tarefa["caminho_origem"]
    caminho_destino = tarefa["caminho_destino"]

    print_log_dual("Processando tarefa: ", codigo_tarefa)

    # Para ver o conjunto completo, descomentar a linha abaixo
    var_dump(tarefa)
    die('ponto200')

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
    # (Utilizar  multiprocessing, ver sapi_cellebrite)
    # O programa secundário iria invocar o programa externo que
    # executa a tarefa, e o programa principal se
    # encarregaria de controlar a execução
    print_log_dual("Invocando programa ", tipo_iped, " e aguardando resultado")
    # pid = os.fork()
    # if pid == 0:
    # 	print_log_dual("invocado programa: "+comando)
    # 	# Executa o programa externo e fica esperando o resultado
    # 	os.system(comando) # Se mata o pai, morre também...melhorar isto
    # 	print_log_dual("Programa externo encerrou")
    # 	sys.exit()
    #
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
            sapisrv_atualizar_status_tarefa(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=codigo_situacao_tarefa,
                status=texto_status
            )
            # Uma pequena pausa, e continua para a próxima simulação de andamento
            # Cada simulação deve demorar entre 90 e 100 segundos
            dormir(100 - r)
            continue

        # Simula sucesso, 90% de probabilidade no demo
        if (r >= 90):

            # Para armazenamento de dados para laudo
            dados_relevantes = dict()

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

                h = dict()
                h["sapiHashDescricao"] = "Hash do arquivo listaArquivos.csv (gerado por " + arg_tipo + ")"
                h["sapiHashValor"] = valor_hash
                h["sapiHashAlgoritmo"] = "MD5"
                lista_hash = [h]

                # Simula versão do software
                softwareVersao = "SoftwareX 4.15"
                if ("iped" in arg_tipo):
                    softwareVersao = "IPED 3.11"
                elif ("ief" in arg_tipo):
                    softwareVersao = "IEF 6.45"

                # O campo sapiSoftwareVersao deve sempre ser informado
                # Os demais, irão variar de acordo com o software executado
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
            while not sapisrv_atualizar_status_tarefa(codigo_tarefa=codigo_tarefa,
                                                      codigo_situacao_tarefa=codigo_situacao_tarefa,
                                                      status=texto_status,
                                                      dados_relevantes=dados_relevantes
                                                      ):
                print_log_dual("Falhou atualização de status de sucesso. Tentando novamente")
                dormir(60)  # Tenta novamente em 1 minuto

            terminou = True  # Abandona loop de verificação de situação
            print_log_dual("Dormindo após concluir...para dar chance a outros de pegar tarefas...apenas teste")
            dormir(30)  # Uma pausa apenas para teste..poder consultar sem nenhum agente trabalhando
            continue

            # Fim do while



# ======================================================================
# Rotina Principal 
# ======================================================================

if __name__ == '__main__':

    # testes gerais
    # die('ponto2061')

    # Cabeçalho inicial do programa
    # ------------------------------------------------------------------------------------------------------------------
    print()
    cls()
    print(Gprograma, "Versão", Gversao)
    print()

    # Inicialização do programa
    # -----------------------------------------------------------------------------------------------------------------
    print_log_dual('Iniciando ', Gprograma , ' - ', Gversao)
    inicializar()

    # Monta lista de tipos de IPED
    # ------------------------------------------------------------------------------------------------------------------
    lista_ipeds=montar_lista_tipos_iped()

    # Loop de execução de tarefas.
    # ------------------------------------------------------------------------------------------------------------------
    # Por enquanto, fica em loop eterno
    # Para a versão 2.0, haverá um mecanismo de cancelamento, através da negação do servidor em dar continuidade ou
    # iniciar tarefas para um determinado agente / programa
    while (True):
        executar_uma_tarefa(lista_ipeds)
        # Pausa entre execuções de tarefa
        dormir(GdormirSemServico)

    # Finalização do programa
    # -----------------------------------------------------------------------------------------------------------------
    print_ok()
    print_log_dual("FIM SAPI - ",Gprograma," (Versao " + Gversao + ")")


