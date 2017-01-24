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
Gprograma = "sapi_iped.py"
Gversao = "1.0"

# Controle de tempos/pausas
GtempoEntreAtualizacoesStatus = 180
GdormirSemServico = 10 #60
GmodoInstantaneo=False
#GmodoInstantaneo = True

#
Gconfiguracao = dict()


# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi.py, para evitar dependência
from sapilib_0_7 import *

# **********************************************************************
# PRODUCAO 
# **********************************************************************


# ======================================================================
# Funções auxiliares
# ======================================================================

# Faz um pausa por alguns segundos
# Dependendo de parâmetro, ignora a pausa
def dormir(tempo):
    print_log_dual("Dormindo por ", tempo, " segundos")
    if (not GmodoInstantaneo):
        time.sleep(tempo)
    else:
        print_log_dual("Sem pausa...deve ser usado apenas para debug...modo instantâneo (ver GmodoInstantaneo)")

# Inicialização do agente
# Procedimento de inicialização
# Durante estes procedimento será determinado se comunicação a com servidor está ok,
# se este programa está habilitado para operar com o servidor, etc
# Existe um mecanismo para determinar automaticamente se será atulizado o servidor de desenvolvimento ou produção
# (ver documentação da função). Caso prefira definir manualmente, adicione ambiente='desenv' (ou 'prod')
# O nome do agente também é determinado por default através do hostname.
# ---------------------------------------------------------------------------------------------------------------------
def inicializar():

    global Gconfiguracao

    # Fica em loop até obter alguma conclusão sobre a inicialização,
    # pois o servidor pode momentaneamente não estar disponível (problema de rede por exemplo)
    while True:

        try:
            print_log_dual("Efetuando inicialização")
            sapisrv_inicializar(Gprograma, Gversao)  # Outros parâmetros: nome_agente='xxxx', ambiente='desenv'
            print_log_dual("Inicialização efetuada")

            # Obtendo arquivo de configuração
            print_log_dual("Obtendo configuração")
            Gconfiguracao=sapisrv_obter_configuracao_cliente(Gprograma)
            print_log_dual("Configuração obtida")
            print_log_dual(Gconfiguracao)

            # Tudo certo
            break

        except BaseException as e:
            # Não importa a falha...irá ficar tentanto eternamente
            print_log_dual("Falhou durante procedimento iniciais: ", e)
            dormir(GdormirSemServico)
            print_log_dual("Tentando inicialização novamente")


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


# Tenta obter uma tarefa com tipo contido em lista_tipo, para o storage (se for indicado)
def solicita_tarefas(lista_tipos, storage=None):

    for i in lista_tipos:
        # Tipo de tarefa
        tipo=i["tipo"]

        # Registra em log
        log="Solicitando tarefa com tipo=[" + tipo + "]"
        if storage is not None:
            log += " para storage =[" + storage + "]"
        else:
            log += " para qualquer storage"
        print_log_dual(log)

        # Requisita tarefa
        (disponivel, tarefa) = sapisrv_obter_iniciar_tarefa(tipo, storage=storage)
        if disponivel:
            print_log("Ok, tarefa retornada")
            return tarefa

    print_log("Nenhuma tarefa retornada")
    return None



# Atualiza status no servidor
# fica em loop até conseguir
def atualizar_status_servidor_loop(codigo_tarefa, codigo_situacao_tarefa, texto_status, dados_relevantes=None):

    # Se a atualização falhar, fica tentando até conseguir
    # Se for problema transiente, vai resolver
    # Caso contrário, algum humano irá mais cedo ou mais tarde intervir
    while not sapisrv_atualizar_status_tarefa(codigo_tarefa=codigo_tarefa,
                                              codigo_situacao_tarefa=codigo_situacao_tarefa,
                                              status=texto_status,
                                              dados_relevantes=dados_relevantes
                                              ):
        print_log_dual("Falhou atualização de status para tarefa [",codigo_tarefa,"]. Tentando novamente")
        dormir(60)  # Tenta novamente em 1 minuto

    #Ok, conseguiu atualizar
    print_log("Tarefa [",codigo_tarefa,"]: Situação atualizada para [",codigo_situacao_tarefa,"] com texto [",texto_status,"]")

# Devolve ao servidor uma tarefa
def devolver(codigo_tarefa, texto_status):

    # Registra em log
    print_log_dual("Devolvendo tarefa [",codigo_tarefa,"] para servidor: ",texto_status)

    # Atualiza status no servidor
    codigo_situacao_tarefa = GAguardandoProcessamento
    atualizar_status_servidor_loop(codigo_tarefa, codigo_situacao_tarefa, texto_status)

    # Ok
    print_log_dual("Tarefa devolvida")


# Aborta tarefa
def abortar(codigo_tarefa, texto_status):

    # Registra em log
    print_log_dual("Abortando execução da tarefa [",codigo_tarefa,"]: ",texto_status)

    # Atualiza status no servidor
    codigo_situacao_tarefa = GAbortou
    atualizar_status_servidor_loop(codigo_tarefa, codigo_situacao_tarefa, texto_status)


    # Ok
    print_log_dual("Execução da tarefa abortada")


# Tratamento para erro no cliente
def reportar_erro(erro):
    try:
        # Registra no log (local)
        print_log_dual("ERRO: ",erro)

        # Reportanto ao servidor, para registrar no log do servidor
        sapisrv_reportar_erro_cliente(erro)
        print_log_dual("Erro reportado ao servidor")

    except BaseException as e:
        # Se não conseguiu reportar ao servidor, deixa para lá
        # Afinal, já são dois erros seguidos (pode ser que tenha perdido a rede)
        print_log_dual("Não foi possível reportar o erro ao servidor: ", e)


# Fica em loop de execução de tarefa
# Encerra apenas se houver algum erro que impeça o prosseguimento
def executar_uma_tarefa(lista_ipeds):

    # Solicita tarefa, dependendo da configuração de storage do agente
    outros_storages = True
    tarefa = None
    if Gconfiguracao["storage_unico"]!="":
        print_log_dual("Este agente trabalha apenas com storage=",Gconfiguracao["storage_unico"])
        tarefa=solicita_tarefas(lista_ipeds, Gconfiguracao["storage_unico"])
        outros_storages=False
    elif Gconfiguracao["storage_preferencial"]!="":
        print_log_dual("Este agente trabalha com storage preferencial=",Gconfiguracao["storage_preferencial"])
        tarefa=solicita_tarefas(lista_ipeds, Gconfiguracao["storage_preferencial"])
        outros_storages=True
    else:
        print_log_dual("Este agente trabalha com qualquer storage")
        outros_storages=True

    if outros_storages:
        # Solicita tarefa para qualquer storage
        tarefa=solicita_tarefas(lista_ipeds)

    # Para a versão 2.0, será implementado também um mecanismo de retomada, utilizado pelo agente para retomar
    # tarefas interrompidas (por falta de energia por exemplo)
    # Logo, aqui será necessário verificar se a tarefa já estava em andamento, e tomara as medidas necessárias
    # (continuar, ou reinicar se for o caso)

    # Se não tem nenhuma tarefa disponível, não tem o que fazer
    if tarefa is None:
        print_log_dual("Nenhuma tarefa fornecida. Nada a fazer.")
        return

    # Ok, temos trabalho a fazer
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]  # Identificador único da tarefa
    # Verifica se é uma retomada de tarefa, ou seja,
    # uma tarefa que foi iniciada mas que não foi concluída
    retomada=False
    if tarefa["executando"]=='t':
        retomada=True

    # Indicativo de início
    if retomada:
        print_log_dual("Retomando tarefa interrompida: ", codigo_tarefa)
    else:
        print_log_dual("Iniciando tarefa: ", codigo_tarefa)

    # Para ver o conjunto completo, descomentar a linha abaixo
    # var_dump(Gconfiguracao)
    #var_dump(tarefa)

    # Teste de devolução
    #texto_status="teste de devolução"
    #devolver(codigo_tarefa, texto_status)


    # Teste abortar
    #texto_status="teste de abotar"
    #abortar(codigo_tarefa, texto_status)

    die('ponto298')

    # Montar storage
    # ------------------------------------------------------------------
    # Confirma que tem acesso ao storage escolhido
    (sucesso, ponto_montagem, erro) = acesso_storage_windows(tarefa["dados_storage"])
    if not sucesso:
        erro = "Acesso ao storage [" + ponto_montagem + "] falhou"
        # Talvez seja um problema de rede (trasiente)
        reportar_erro(erro)
        print_log_dual("Problema insolúvel neste momento, mas possivelmente transiente")
        # Tarefa não foi iniciada, então pode ser devolvida
        texto_status="Agente sem condição de executar tarefa. Devolvida ao servidor"
        print_log_dual(texto_status)
        # Abortando tarefa, pois tem algo errado aqui.
        # Não adianta ficar retentando nesta condição
        devolver(codigo_tarefa, texto_status)
        print_log("Dormindo por um bom tempo, para dar oportunidade de outro agente pegar tarefa")
        dormir(300)

        return



    # Conferir se pasta/arquivo de origem está ok
    # ------------------------------------------------------------------
    # O caminho de origem pode indicar um arquivo (.E01) ou uma pasta
    # Neste ponto, seria importante verificar se esta origem está ok
    # Ou seja, se existe o arquivo ou pasta de origem
    caminho_origem = ponto_montagem + tarefa["caminho_origem"]
    print_log_dual("Caminho de origem (", caminho_origem, "): localizado")

    if os.path.isfile(caminho_origem):
        print_log_dual("Arquivo de origem encontrado no storage")
    elif os.path.exists(caminho_origem):
        print_log_dual("Pasta de origem encontrada no storage")
    else:
        # Se não existe nem arquivo nem pasta, tem algo muito errado aqui
        # Aborta esta tarefa
        texto_status="Caminho de origem não encontrado no storage"
        print_log_dual(texto_status)
        # Abortando tarefa, pois tem algo errado aqui.
        # Não adianta ficar retentando nesta condição
        abortar(codigo_tarefa, texto_status)
        return

    # Criar pasta de destino
    # ------------------------------------------------------------------
    # Teria que criar a pasta de destino, caso ainda não exista
    # Se a pasta de destino já existe...opa, pode ter algo errado.
    # Neste cenário, teria que conferir se a pasta não tem nada
    # de útil (indicando alguma concorrência....ou processo abortado)
    caminho_destino = ponto_montagem + tarefa["caminho_destino"]
    print_log_dual("Caminho de destino (", caminho_destino, "): Criado")

    die('ponto267')

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

    # Todas as mensagens do log serão exibidas também na tela
    ligar_log_dual()

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


