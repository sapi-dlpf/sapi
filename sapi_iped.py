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
    import shutil
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

    lista_ipeds_ok = list()

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

        except Exception as e:
            # Não importa a falha...irá ficar tentanto eternamente
            print_log_dual("Falhou durante procedimento iniciais: ", str(e))
            dormir(GdormirSemServico)
            print_log_dual("Tentando inicialização novamente")

        # Verifica se máquina corresponde à configuração recebida, ou seja, se todos os programas de IPED
        # que deveriam estar instalados realmente estão instalados
        for t in Gconfiguracao["tipo_tarefa"]:
            tipo=Gconfiguracao["tipo_tarefa"][t]
            pasta_programa=tipo["pasta_programa"]
            if os.path.exists(pasta_programa):
                print_log_dual("Pasta de iped ", pasta_programa, " localizada")
                lista_ipeds_ok.append(t)
            else:
                erro="Não foi localizada pasta de iped: " + pasta_programa
                reportar_erro(erro)

        if len(lista_ipeds_ok)==0:
            erro = "Nenhum IPED habilitado nesta máquina"
            reportar_erro(erro)
            # Vamos dormir por um bom tempo (60 minutos), pois este erro não deve ser corrigido tão cedo
            dormir(60*60)
            continue
        else:
            # Tudo bem, prossegue (mesmo que nem todos os ipeds estejam ativos)
            break

    # Retorna a lista de opções de execução de iped disponíveis nesta máquina
    return lista_ipeds_ok


# Tenta obter uma tarefa com tipo contido em lista_tipo, para o storage (se for indicado)
def solicita_tarefas(lista_tipos, storage=None):

    for tipo in lista_tipos:

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
            print_log("Tarefa disponível")
            return tarefa

    print_log("Nenhuma tarefa disponível")
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
        print_log_dual("Falhou upload de texto para tarefa [",codigo_tarefa,"]. Tentando novamente")
        dormir(60)  # Tenta novamente em 1 minuto

    #Ok, conseguiu atualizar
    print_log("Efetuado upload de texto [",titulo,"] para tarefa [",codigo_tarefa,"]")


def armazenar_texto_log_iped(codigo_tarefa, caminho_log_iped):

    # Le arquivo de log do iped e faz upload

    # Por enquanto, vamos ler tudo, mas talvez mais tarde seja melhor sintetizar, removendo informações sem valor
    # que só interesseriam para o desenvolvedor
    # Neste caso, talvez ter dois logs: O completo e o sintético.
    # Para arquivos maiores, terá que configurar no /etc/php.ini os parâmetros post_max_size e upload_max_filesize
    # para o tamanho necessário (atualmente no SETEC3 está bem baixo...8M)

    # Se precisar sintetizar no futuro, ver sapi_cellebrite => sintetizar_arquivo_xml
    # Fazer uma função específica
    conteudo=""
    # with codecs.open(caminho_log_iped, "r", "utf-8") as fentrada:
    # Tem algo no arquivo de log que não é UTF8
    with open(caminho_log_iped, "r") as fentrada:
        for linha in fentrada:
            conteudo=conteudo+linha

    armazenar_texto_tarefa(codigo_tarefa, 'Arquivo de log do IPED', conteudo)


# Devolve ao servidor uma tarefa
def devolver(codigo_tarefa, texto_status):

    # Registra em log
    print_log_dual("Devolvendo tarefa [",codigo_tarefa,"] para servidor: ",texto_status)

    # Atualiza status no servidor
    codigo_situacao_tarefa = GAguardandoProcessamento
    atualizar_status_servidor_loop(codigo_tarefa, codigo_situacao_tarefa, texto_status)

    # Ok
    print_log_dual("Tarefa devolvida")

    # Para garantir que a tarefa devolvida não será pega por este mesmo agente logo em seguida,
    # vamos dormir por um tempo longo
    print_log("Dormindo por um bom tempo, para dar oportunidade de outro agente pegar tarefa")
    dormir(3*60)  # Tenta novamente em 1 minuto


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

    except Exception as e:
        # Se não conseguiu reportar ao servidor, deixa para lá
        # Afinal, já são dois erros seguidos (pode ser que tenha perdido a rede)
        print_log_dual("Não foi possível reportar o erro ao servidor: ", str(e))


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

    # Se ainda não tem tarefa, e agente trabalha com outros storages, solicita para qualquer storage
    if tarefa is None and outros_storages:
        # Solicita tarefa para qualquer storage
        tarefa=solicita_tarefas(lista_ipeds)

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

    #die('ponto298')

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
        return


    # Confere se pasta/arquivo de origem está ok
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
        # Aborta esta tarefa para que PCF possa analisar
        texto_status="Caminho de origem não encontrado no storage"
        print_log_dual(texto_status)
        # Abortando tarefa, pois tem algo errado aqui.
        # Não adianta ficar retentando nesta condição
        abortar(codigo_tarefa, texto_status)
        return

    # Pasta de destino
    # ------------------------------------------------------------------
    caminho_destino = ponto_montagem + tarefa["caminho_destino"]

    # Se pasta para armazenamento de resultado já existe, tem que limpar pasta antes
    # pois pode conter algum lixo de uma execução anterior
    if os.path.exists(caminho_destino):
        try:
            # Registra situação
            atualizar_status_servidor_loop(codigo_tarefa, GPastaDestinoCriada,
                                           "Pasta de destino já existe. Excluindo pasta para reiniciar")
            # Limpa pasta de destino
            shutil.rmtree(caminho_destino, ignore_errors=True)
        except Exception as e:
            erro="Não foi possível limpar pasta de destino da tarefa: " + str(e)
            # Aborta tarefa
            abortar(codigo_tarefa, erro)
            return

    # Não pode existir. Se existir, processo de exclusão acima falhou
    if os.path.exists(caminho_destino):
        erro = "Pasta de destino ainda existe, mesmo após ter sido excluída?"
        # Aborta tarefa
        abortar(codigo_tarefa, erro)
        return

    # Cria pasta de destino
    try:
        os.makedirs(caminho_destino)
    except Exception as e:
        erro = "Não foi possível criar pasta de destino: " + str(e)
        # Aborta tarefa
        abortar(codigo_tarefa, erro)
        return

    # Confere se deu certo
    if not os.path.exists(caminho_destino):
        erro = "Criação de pasta de destino falhou"
        # Aborta tarefa
        abortar(codigo_tarefa, erro)
        return

    # Tudo certo, pasta criada
    atualizar_status_servidor_loop(codigo_tarefa, GPastaDestinoCriada, "Pasta de destino criada")

    # ------------------------------------------------------------------------------------------------------------------
    # Inicia em background processo para controlar a execução do IPED
    # Todo: Implementar
    # ------------------------------------------------------------------------------------------------------------------


    # ------------------------------------------------------------------------------------------------------------------
    # Executa IPED
    # ------------------------------------------------------------------------------------------------------------------

    #var_dump(Gconfiguracao)
    #var_dump(tarefa)
    #die('ponto402')

    tipo_iped=tarefa["tipo"]
    comando=Gconfiguracao["tipo_tarefa"][tipo_iped]["comando"]

    # Adiciona a pasta de origem e destino
    comando=comando + " -d " + caminho_origem + " -o " + caminho_destino

    #Para teste
    #comando='dir'
    #comando='java -version'
    #comando='java' #Executa mas com exit code =1
    # Para teste
    #caminho_origem  ="C:\\teste_iped\\Memorando_1086-16\\item11\\item11_extracao"
    #caminho_destino ="C:\\teste_iped\\Memorando_1086-16\\item11\\item11_extracao_iped"
    #comando='java -Xmx24G -jar c:\\iped-basico-3.11\\iped.jar -d ' + caminho_origem + " -o " + caminho_destino
    resultado=''

    #var_dump(comando)
    #die('ponto415')

    # Adiciona parâmetros na linha de comando
    caminho_log_iped=caminho_destino + "\\iped.log"
    comando=comando +" --nogui " + " -log " + caminho_log_iped

    # Executa comando
    deu_erro=False
    try:
        # Registra comando iped na situação
        atualizar_status_servidor_loop(codigo_tarefa, GEmAndamento, "Chamando IPED: " + comando)
        # Executa comando
        resultado = subprocess.check_output(comando, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        # Se der algum erro, não volta nada acima, mas tem como capturar pegando o output da exception
        resultado = str(e.output)
        deu_erro=True
    except Exception as e:
        # Alguma outra coisa aconteceu...
        resultado = "Erro desconhecido: " + str(e)
        deu_erro = True

    # Faz upload do resultado e do log
    armazenar_texto_tarefa(codigo_tarefa, 'Resultado IPED (tela)', resultado)
    armazenar_texto_log_iped(codigo_tarefa, caminho_log_iped)

    if deu_erro:
        # Aborta tarefa
        erro = "IPED falhou (retornou exit code de erro)"
        abortar(codigo_tarefa, erro)
        # Tolerância a Falhas: Permite que outro agente execute
        devolver(codigo_tarefa, "Sem sucesso: Repassando tarefa para outro agente")
        return

    # Se não deu erro (exit code), espera-se que o IPED tenha chegado até o final normalmente
    # Para confirmar isto, confere se existe o string abaixo
    if "IPED finalizado" not in resultado:
        # Algo estranho aconteceu, pois não retornou erro (via exit code), mas também não retornou mensagem de sucesso
        erro = "Não foi detectado string de sucesso no resultado do IPED. Consulte desenvolvedor."
        abortar(codigo_tarefa, erro)
        # Neste caso, vamos abortar definitivamente, para fazer um análise do que está acontecendo
        return


    # Tudo certo, IPED finalizado
    atualizar_status_servidor_loop(codigo_tarefa, GEmAndamento, "IPED finalizado com sucesso")

    # Prepara para execução multicase
    # 1) Copia pasta lib para
    # 2) Cria bat para usuário invocar multicase

    # Calcula hash


    devolver(codigo_tarefa, "Para teste, retornando para novo processamento")

    die('ponto267')

    # Fork para monitorar andamento
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
    # comando='dir'
    # comando='java -version'
    # comando='java' #Executa mas com exit code =1
    # caminho_origem  ="C:\\teste_iped\\Memorando_1086-16\\item11\\item11_extracao"
    # caminho_destino ="C:\\teste_iped\\Memorando_1086-16\\item11\\item11_extracao_iped"
    # comando='java -Xmx24G -jar c:\\iped-basico-3.11\\iped.jar -d ' + caminho_origem + " -o " + caminho_destino
    # resultado=''
    # deu_erro=False
    # print(comando)
    # try:
    #     resultado = subprocess.check_output(comando, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
    # except subprocess.CalledProcessError as e:
    #     # Se der algum erro, não volta nada acima, mas tem como capturar pegando o output da exception
    #     resultado = str(e.output)
    #     deu_erro=True
    # except Exception as e:
    #     # Alguma outra coisa aconteceu...
    #     print(str(e))
    #     die('ponto600')
    #
    # # java -jar Indexador/lib/iped-search-app.jar
    # var_dump(deu_erro)
    # var_dump(resultado)
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
    lista_ipeds=inicializar()
    #var_dump(lista_ipeds)
    #die('ponto591')

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


