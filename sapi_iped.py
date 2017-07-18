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
# ======================================================================================================================
# TODO:
# - Limpar pasta indexador no final da execução (IPED não está conseguindo limpar)
# - Rodar como serviço e/ou tarefa agendada do windows (talvez seja melhor a segunda, pois faz restart)
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
Gprograma = "sapi_iped"
Gversao = "1.7.5"

# Controle de tempos/pausas
GtempoEntreAtualizacoesStatus = 180
GdormirSemServico = 60
GmodoInstantaneo = False
# GmodoInstantaneo = True

#
Gconfiguracao = dict()
Gcaminho_pid="sapi_iped_pid.txt"

GnomeProgramaInterface="IPED-SearchApp.exe"

# Dados para laudo
Gdados_laudo = None


# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi.py, para evitar dependência
from sapilib_0_7_2 import *


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


def reinicia_sapi_iped():

    print_log("Reiniciando sapi_iped.py")
    args = sys.argv[:]
    args.insert(0, sys.executable)

    #if sys.platform == 'win32':
    #    args = ['"%s"' % arg for arg in args]

    # Escreve o que quer que esteja pendente
    sys.stdout.flush()

    print_log('Reiniciando => %s' % ' '.join(args))
    var_dump(sys.executable)
    var_dump(args)
    die('ponto125')

    os.execv(sys.executable, args)


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

    # Lista de ipeds disponíveis para execução
    lista_ipeds_ok = list()

    try:
        # Efetua inicialização
        # Neste ponto, se a versão do sapi_iped estiver desatualizada será gerado uma exceção
        print_log("Efetuando inicialização")
        sapisrv_inicializar(Gprograma, Gversao)  # Outros parâmetros: nome_agente='xxxx', ambiente='desenv'

        # Obtendo arquivo de configuração
        print_log("Obtendo configuração")
        Gconfiguracao = sapisrv_obter_configuracao_cliente(Gprograma)
        print_log(Gconfiguracao)

    except SapiExceptionVersaoDesatualizada:
        # Se versão do sapi_iped está desatualizada, irá tentar se auto atualizar
        print_log("sapi_iped desatualizado. Encerrando para efetuar atualização")
        # Ao retornar None, o chamador entenderá que tem que atualizar o sapi_iped, e encerrará a execução
        return None

    except SapiExceptionProgramaDesautorizado:
        # Servidor sapi pode não estar respondendo (banco de dados inativo)
        # Logo, encerra e aguarda uma nova oportunidade
        print_log("AVISO: Não foi possível obter acesso (ver mensagens anteriores). Encerrando programa")
        # Ao retornar None, o chamador encerrará a execução
        return None

    except SapiExceptionFalhaComunicacao:
        # Se versão do sapi_iped está desatualizada, irá tentar se auto atualizar
        print_log("Comunição com servidor falhou. Vamos encerrar e aguardar atualização, pois pode ser algum defeito no cliente")
        # Ao retornar None, o chamador entenderá que tem que atualizar o sapi_iped, e encerrará a execução
        return None

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
        return None

    # Verifica se máquina corresponde à configuração recebida, ou seja, se todos os programas de IPED
    # que deveriam estar instalados realmente estão instalados
    for t in Gconfiguracao["tipo_tarefa"]:
        tipo = Gconfiguracao["tipo_tarefa"][t]
        pasta_programa = tipo["pasta_programa"]
        if os.path.exists(pasta_programa):
            #print_log("Pasta de iped ", pasta_programa, " localizada")
            lista_ipeds_ok.append(t)
        else:
            erro = "Não foi localizada pasta de iped: " + pasta_programa
            reportar_erro(erro)

    if len(lista_ipeds_ok) == 0:
        # Como não achou IPED, provavelmente está configurado no servidor
        # para que seja utilizado uma nova versão
        # Tenta atualizar sapi_iped para sanar o problema
        tentar_atualizar_sapi_iped=True
        erro = "Nenhum IPED (na versão correta) encontrado nesta máquina"
        reportar_erro(erro)
        return None


    # Ok, tudo certo, retorna a lista opções de execução de iped disponíveis nesta máquina
    return lista_ipeds_ok


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


# Atualiza status no servidor
# fica em loop até conseguir
def atualizar_status_servidor_loop(codigo_tarefa, codigo_situacao_tarefa, texto_status, dados_relevantes=None):
    # Se a atualização falhar, fica tentando até conseguir
    # Se for problema transiente, vai resolver
    # Caso contrário, algum humano irá mais cedo ou mais tarde intervir
    while True:

        atualizou = False
        try:
            # Registra situação
            sapisrv_atualizar_status_tarefa(codigo_tarefa=codigo_tarefa,
                                            codigo_situacao_tarefa=codigo_situacao_tarefa,
                                            status=texto_status,
                                            dados_relevantes=dados_relevantes
                                            )
            atualizou = True
        except Exception as e:
            atualizou = False
            print_log("Falhou atualização de situação para tarefa [", codigo_tarefa, "]. Tentando novamente")
            dormir(60)  # Tenta novamente em 1 minuto

        # Encerra se conseguiu atualizar
        if atualizou:
            # Ok, conseguiu atualizar
            break

    # Registra atualização com sucesso
    msg_log="Tarefa [" +  codigo_tarefa + "]: Atualizada. "
    if codigo_situacao_tarefa>0:
        msg_log = msg_log + " Código da situação=[" + str(codigo_situacao_tarefa) + "]"
    if texto_status != "":
        msg_log = msg_log + " Texto Situação=[" +  texto_status + "]"
    print_log(msg_log)


# Atualiza apenas status no servidor
def atualizar_apenas_status(codigo_tarefa, texto_status):
    return atualizar_status_servidor_loop(codigo_tarefa, GManterSituacaoAtual, texto_status)


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


# Devolve ao servidor uma tarefa
# Retorna sempre False
def devolver(codigo_tarefa, texto_status):

    erro="Devolvendo [[tarefa:" + codigo_tarefa+ "]] ao servidor (para ser executada por outro agente) em função de ERRO: " + texto_status

    # Registra em log
    print_log(erro)

    # Reportar erro para ficar registrado no servidor
    # Desta forma, é possível analisar os erros diretamente
    reportar_erro(erro)

    # Registra situação de devolução
    codigo_situacao_tarefa = GAguardandoProcessamento
    atualizar_status_servidor_loop(codigo_tarefa, codigo_situacao_tarefa, texto_status)

    # Ok
    print_log("Tarefa devolvida")

    # Para garantir que a tarefa devolvida não será pega por este mesmo agente logo em seguida,
    # vamos dormir um pouco
    dormir(60, "Pausa para dar oportunidade de outro agente pegar tarefa")

    # Retorna false, para uso pelo chamador
    return False

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
    codigo_situacao_tarefa = GAbortou
    atualizar_status_servidor_loop(codigo_tarefa, codigo_situacao_tarefa, texto_status)

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


# Acompanha a execução do IPED e atualiza o status da tarefa
def acompanhar_iped(codigo_tarefa, caminho_tela_iped):
    # Inicializa sapilib, pois pode estar sendo executando em background (outro processo)
    sapisrv_inicializar(Gprograma, Gversao)

    print_log("Iniciado processo de acompanhamento de IPED")

    # Um pequeno delay inicial, para dar tempo de começar a registrar algo no arquivo de resultado/tela
    time.sleep(30)

    # Fica em loop infinito. Será encerrado pelo pai (com terminate)
    while True:

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
            print_log("IPED status: ",texto_status)
            atualizar_apenas_status(codigo_tarefa, texto_status)
            print_log("Status atualizado para tarefa [",codigo_tarefa,"] : ", texto_status)
            # Intervalo entre atualizações de status
            dormir(GtempoEntreAtualizacoesStatus, "Dormindo entre atualização de status do IPED")
        else:
            # Como ainda não atualizou o status, vamos dormir por um período menor
            # Assim pega a primeira atualização de status logo que sair
            dormir(30)


# Executa IPED
# Retorna:
#   True: Executado com sucesso
#   False: Execução falhou
def executa_iped(codigo_tarefa, comando, caminho_destino, caminho_log_iped, caminho_tela_iped):

    # ------------------------------------------------------------------------------------------------------------------
    # Pasta de destino
    # ------------------------------------------------------------------------------------------------------------------
    # Se já existe conteúdo na pasta, verifica se foi concluído com sucesso
    if os.path.exists(caminho_destino):
        print_log("Pasta de destino já existe.")
        print_log("Verificando se existe IPED rodado com sucesso")
        if verificar_sucesso_iped(caminho_tela_iped):
            # Tudo certo, IPED finalizado
            atualizar_status_servidor_loop(codigo_tarefa, GIpedFinalizado, "Execução de IPED anterior foi concluída com sucesso.")
            return True

    # Se pasta para armazenamento de resultado já existe, tem que limpar pasta antes
    # pois pode conter algum lixo de uma execução anterior
    if os.path.exists(caminho_destino):
        try:
            # Registra situação
            atualizar_status_servidor_loop(codigo_tarefa, GPastaDestinoCriada,
                                           "Pasta de destino ["+ caminho_destino + "] já existe, mas sem IPED finalizado ok."+
                                           " Excluindo pasta para rodar iped desde o início")
            print_log("Excluindo pasta ["+caminho_destino+"]")
            # Limpa pasta de destino
            # shutil.rmtree(caminho_destino, ignore_errors=True)
            shutil.rmtree(caminho_destino)
            atualizar_status_servidor_loop(codigo_tarefa, GPastaDestinoCriada,
                                           "Pasta de destino ["+ caminho_destino + "] excluída")
        except Exception as e:
            erro = "Não foi possível limpar pasta de destino da tarefa: " + str(e)
            # Aborta tarefa
            return abortar(codigo_tarefa, erro)

    # Não pode existir. Se existir, processo de exclusão acima falhou
    if os.path.exists(caminho_destino):
        erro = "Tentativa de excluir pasta falhou: Verifique se existe algo aberto na pasta, que esteja criando um lock em algum dos seus recursos"
        # Aborta tarefa
        return abortar(codigo_tarefa, erro)

    # Cria pasta de destino
    try:
        os.makedirs(caminho_destino)
    except Exception as e:
        erro = "Não foi possível criar pasta de destino: " + str(e)
        # Pode ter alguma condição temporária impedindo. Continuar tentando.
        return devolver(codigo_tarefa, erro)

    # Confere se deu certo
    if not os.path.exists(caminho_destino):
        erro = "Criação de pasta de destino falhou sem causar exceção!! Situação inesperada!"
        # Aborta tarefa
        return abortar(codigo_tarefa, erro)

    # Tudo certo, pasta criada
    atualizar_status_servidor_loop(codigo_tarefa, GPastaDestinoCriada, "Pasta de destino criada")


    # ------------------------------------------------------------------------------------------------------------------
    # Inicia em background processo para monitorar avanço do IPED
    # Todo: Implementar
    # ------------------------------------------------------------------------------------------------------------------
    processo_acompanhar = multiprocessing.Process(target=acompanhar_iped,
                                           args=(codigo_tarefa, caminho_tela_iped))
    processo_acompanhar.start()
    print_log("Iniciando processo background para acompanhamento de iped")

    # ------------------------------------------------------------------------------------------------------------------
    # Executa comando do iped
    # ------------------------------------------------------------------------------------------------------------------
    deu_erro = False
    try:
        # Registra comando iped na situação
        atualizar_status_servidor_loop(codigo_tarefa, GIpedExecutando, "Chamando IPED: " + comando)
        # Executa comando
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

    # Como iped terminou, finaliza o processo de acompanhamento
    processo_acompanhar.terminate()
    print_log("Encerrando processo background de acompanhamento")

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
        # Aborta tarefa
        erro = "Chamada de IPED falhou (retornou exit code de erro). Analise arquivo de resultado. Tarefa devolvida para reiniciar processamento."
        if erro_exception!="":
            erro = erro + ": " + erro_exception
        # Tolerância a Falhas: Permite que outro agente execute
        # return devolver(codigo_tarefa, erro)

        # Como o IPED falhou, é possível que haja algum problema com a instalação do IPED,
        # a qual seria corrigida pela atualização do IPED
        # Desta forma, devolve a tarefa
        # e em seguida encerra o programa, para que seja atualizado
        devolver(codigo_tarefa, erro)
        # Encerra sapi_iped
        print_log("Em função do erro do IPED, programa será encerrado para permitir atualização")
        os._exit(1)

    # Se não deu erro (exit code), espera-se que o IPED tenha chegado até o final normalmente
    # Para confirmar isto, confere se existe o string abaixo
    if not verificar_sucesso_iped(caminho_tela_iped):
        # Algo estranho aconteceu, pois não retornou erro (via exit code),
        # mas também não retornou mensagem de sucesso na tela
        erro = "Não foi detectado indicativo de sucesso do IPED. Verifique arquivos de Resultado e Log."
        # Neste caso, vamos abortar definitivamente, para fazer um análise do que está acontecendo
        # pois isto não deveria acontecer jamais
        return abortar(codigo_tarefa, erro)

    # Tudo certo, IPED finalizado com sucesso
    atualizar_status_servidor_loop(codigo_tarefa, GIpedFinalizado, "IPED finalizado com sucesso")
    return True

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

    print_log("Calculando hash do resultado do IPED")

    # Monta linha de comando
    nome_arquivo = "Lista de Arquivos.csv"
    caminho_arquivo_calcular_hash = caminho_destino + "/" + nome_arquivo

    deu_erro = False
    try:
        algoritmo_hash = 'sha256'
        texto_status = "Calculando hash " + algoritmo_hash + " para " + caminho_arquivo_calcular_hash
        atualizar_status_servidor_loop(codigo_tarefa, GManterSituacaoAtual, texto_status)
        valor_hash =calcula_sha256_arquivo(caminho_arquivo_calcular_hash)
    except Exception as e:
        erro = "Não foi possível calcular hash para " + nome_arquivo + " => " + str(e)
        # Não deveria ocorrer este erro??? Abortar e analisar
        return abortar(codigo_tarefa, erro)

    # Extrai a subpasta de destino
    partes=caminho_destino.split("/")
    subpasta_destino=partes[len(partes)-1]
    if subpasta_destino=="":
        subpasta_destino = partes[len(partes) - 2]


    # Armazena dados de hash
    h = dict()
    h["sapiHashDescricao"] = "Hash do arquivo " + subpasta_destino + "/listaArquivos.csv"
    h["sapiHashValor"] = valor_hash
    h["sapiHashAlgoritmo"] = algoritmo_hash
    lista_hash = [h]

    Gdados_laudo['sapiHashes']=lista_hash

    print_log("Hash calculado para resultado do IPED: ", valor_hash, "(",algoritmo_hash,")")

    # Tudo certo, Hash calculado
    atualizar_status_servidor_loop(codigo_tarefa, GIpedHashCalculado, "Hash calculado com sucesso")
    return True


# Ajuste para execução multicase
def ajusta_multicase(tarefa, codigo_tarefa, caminho_destino):

    # Ajusta caminho de destino
    caminho_destino = caminho_destino + "\\"

    # Extraí pasta do memorando
    # Localiza pasta do item no caminho de destino
    inicio_pasta_item = caminho_destino.find(tarefa["pasta_item"])
    caminho_memorando = caminho_destino[0:inicio_pasta_item]

    # ------------------------------------------------------------------------------------------------------------------
    # O iped multicase possui a seguinte estrutura:
    # Memorando_xxxx_xx
    #   + multicase
    #     + indexador
    #       + lib
    #       + conf
    #       + Ferramenta de Pesquisa.exe
    #       + iped-itens.txt
    # ------------------------------------------------------------------------------------------------------------------

    caminho_iped_multicase = caminho_memorando + "multicase\\"
    caminho_indexador = caminho_iped_multicase + "indexador\\"

    try:
        if not os.path.exists(caminho_iped_multicase):
            os.makedirs(caminho_iped_multicase)

        if not os.path.exists(caminho_indexador):
            os.makedirs(caminho_indexador)
    except Exception as e:
        erro = "Não foi possível criar estrutura de pasta para multicase " + str(e)
        # Neste caso, aborta tarefa, pois este erro deve ser analisado
        return abortar(codigo_tarefa, erro)

    # Confere criação de pasta
    if os.path.exists(caminho_iped_multicase):
        print_log("Encontrada pasta [" + caminho_iped_multicase + "]: ok")
    else:
        erro = "Situação inesperada: Pasta [" + caminho_iped_multicase + "] não existe"
        # Neste caso, aborta tarefa, pois este erro deve ser analisado
        return abortar(codigo_tarefa, erro)

    if os.path.exists(caminho_indexador):
        print_log("Encontrada pasta [" + caminho_indexador + "]: ok")
    else:
        erro = "Situação inesperada: Pasta [" + caminho_indexador + "] não existe"
        # Neste caso, aborta tarefa, pois este erro deve ser analisado
        return abortar(codigo_tarefa, erro)


    # ------------------------------------------------------------------------------------------------------------------
    # Pasta LIB => Esta pasta contém os programas java e bibliotecas utilizados na pesquisa
    # Efetua a cópia da pasta lib do item para a pasta do iped multicase, caso isto já não tenha sido feito anteriormente
    # ------------------------------------------------------------------------------------------------------------------
    caminho_lib = caminho_indexador + "lib"

    # Se pasta lib não existe, cria pasta, copiando da pasta de processamento de IPED do item
    if not os.path.exists(caminho_lib):
        try:
            caminho_lib_do_item = caminho_destino + "/indexador/lib"
            print_log("Copiando lib do item [" + caminho_lib_do_item + "] " +
                      " para lib da pasta raiz [" + caminho_lib + "], para rodar multicase")
            shutil.copytree(caminho_lib_do_item, caminho_lib)
        except Exception as e:
            erro = "Não foi possível copiar lib do item para lib da pasta raiz: " + str(e)
            # Neste caso, aborta tarefa, pois este erro deve ser analisado
            return abortar(codigo_tarefa, erro)

    # Confere se lib existe
    if os.path.exists(caminho_lib):
        print_log("Encontrada pasta [" + caminho_lib + "]: ok")
    else:
        erro = "Situação inesperada: Pasta [" + caminho_lib + "] não existe"
        # Neste caso, aborta tarefa, pois este erro deve ser analisado
        return abortar(codigo_tarefa, erro)

    # ------------------------------------------------------------------------------------------------------------------
    # Pasta CONF => Copia a pasta conf do item para a pasta do iped multicase, caso isto ainda não tenha sido feito
    # A rigor, cada item pode ter uma configuração indepenente, logo existe um problema conceitual aqui.
    # Mas como todos são rodados pelo sistema, isto não deve dar diferença
    # ------------------------------------------------------------------------------------------------------------------
    caminho_conf = caminho_indexador + "conf"

    # Se pasta conf não existe, cria pasta, copiando da pasta de processamento de IPED do item
    if not os.path.exists(caminho_conf):
        try:
            caminho_conf_do_item = caminho_destino + "/indexador/conf"
            print_log("Copiando conf do item [" + caminho_conf_do_item + "] " +
                      " para conf da pasta raiz [" + caminho_conf + "], para rodar multicase")
            shutil.copytree(caminho_conf_do_item, caminho_conf)
        except Exception as e:
            erro = "Não foi possível copiar conf do item para conf da pasta raiz: " + str(e)
            # Neste caso, aborta tarefa, pois este erro deve ser analisado
            return abortar(codigo_tarefa, erro)

    # Confere se conf existe
    if os.path.exists(caminho_conf):
        print_log("Encontrada pasta [" + caminho_conf + "]: ok")
    else:
        erro = "Situação inesperada: Pasta [" + caminho_conf + "] não existe"
        # Neste caso, aborta tarefa, pois este erro deve ser analisado
        return abortar(codigo_tarefa, erro)



    # ------------------------------------------------------------------------------------------------------------------
    # Arquivo Ferramenta de Pesquisa.exe => Copia do item para a pasta do iped multicase
    # ------------------------------------------------------------------------------------------------------------------
    nome_arquivo=GnomeProgramaInterface
    caminho_de = caminho_destino + nome_arquivo
    caminho_para = caminho_iped_multicase + nome_arquivo
    try:
        shutil.copy(caminho_de, caminho_para)
    except Exception as e:
        erro = "Não foi possível copiar [" + caminho_de + "] para [" + caminho_para +"] : " + str(e)
        # Neste caso, aborta tarefa, pois este erro deve ser analisado
        return abortar(codigo_tarefa, erro)

    # Confere se copiou ok
    if os.path.isfile(caminho_para):
        print_log("Encontrado arquivo [" + caminho_para + "]: ok")
    else:
        erro = "Situação inesperada: Arquivo [" + caminho_para + "] não existe"
        # Neste caso, aborta tarefa, pois este erro deve ser analisado
        return abortar(codigo_tarefa, erro)

    # ------------------------------------------------------------------------------------------------------------------
    # Gera arquivo contendo as listas de pasta dos itens, para ser utilizado na opção multicase
    # Este passo sempre é executado e o arquivo é refeito, refletindo o conteúdo completo da pasta
    # ------------------------------------------------------------------------------------------------------------------
    arquivo_pastas="iped-itens.txt"
    caminho_arquivo_pastas = caminho_iped_multicase + arquivo_pastas

    # Recupera lista de pastas
    lista_pastas=list()
    for root, subdirs, files in os_walklevel(caminho_memorando, level=1):
        if ("_iped" in root):
            # Converte caminho absoluto em relativo
            # Exemplo:
            # De    \\gtpi-sto-01\storage\Memorando_1086-16\item11\item11_extracao_iped
            # para  ..\item11\item11_extracao_iped'
            pasta="..\\" +root.replace(caminho_memorando,'')
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
        return abortar(codigo_tarefa, erro)



    # ------------------------------------------------------------------------------------------------------------------
    # Cria arquivo bat "ferramenta_pesquisa.bat"
    # Este será o arquivo que o usuário irá clicar para invocar o IPED multicase
    # ------------------------------------------------------------------------------------------------------------------
    nome_bat = "ferramenta_pesquisa.bat"

    conteudo_bat="""
@echo off
REM ====================================================================================
REM SAPI - Carregamento do caso no iped, modo multicase
REM ====================================================================================

REM Ajusta diretório corrente para a pasta de armazenamento do multicase
CD /D %~dp0
CD multicase

REM Executa Ferramenta de Pesquisa, passando os parâmetros para multicase
"xxx_programa_interface.exe" -multicases iped-itens.txt
"""

    # Troca o nome do programa do executavel
    conteudo_bat=conteudo_bat.replace("xxx_programa_interface.exe", GnomeProgramaInterface)


    # Caminho para bat
    caminho_bat = caminho_memorando + nome_bat

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
            return abortar(codigo_tarefa, erro)

    # Confere se arquivo existe
    if os.path.isfile(caminho_bat):
        print_log("Encontrado arquivo [" + caminho_bat + "]: ok")
    else:
        erro = "Situação inesperada: Arquivo [" + caminho_bat + "] não existe"
        # Neste caso, aborta tarefa, pois este erro deve ser analisado
        return abortar(codigo_tarefa, erro)


    # Tudo certo, ajuste multicase concluído
    atualizar_status_servidor_loop(codigo_tarefa, GIpedMulticaseAjustado, "Ajuste multicase efetuado")
    return True


# Recupera dados relevantes do log do IPED
def recupera_dados_laudo(codigo_tarefa, caminho_log_iped):

    # Será lido o arquivo de log
    print_log("Recuperando dados para laudo de log do IPED: [", caminho_log_iped, "]")

    if not os.path.exists(caminho_log_iped):
        print_log("Arquivo de log do IPED não encontrado")
        return False

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
        return abortar(codigo_tarefa, erro)

    if total_itens is None:
        erro="Não foi possível recuperar quantidade total de itens processados"
        return abortar(codigo_tarefa, erro)

    # Armazena dados para laudo
    Gdados_laudo['sapiSoftwareVersao']=versao
    Gdados_laudo['sapiItensProcessados'] = total_itens

    # Todo: 'sapiItensProcessados':
    # Todo: 'sapiItensComErro':

    # Ok, finalizado com sucesso
    return True

# Executa uma tarefa de iped que esteja ao alcance do agente
# Retorna verdadeiro se executou uma tarefa e falso se não executou nada
def executar_uma_tarefa(lista_ipeds_suportados):

    # Inicializa repositório de dados para laudo
    global Gdados_laudo
    Gdados_laudo = dict()

    # Solicita tarefa, dependendo da configuração de storage do agente
    outros_storages = True
    tarefa = None
    if Gconfiguracao["storage_unico"] != "":
        print_log("Este agente trabalha apenas com storage=", Gconfiguracao["storage_unico"])
        tarefa = solicita_tarefas(lista_ipeds_suportados, Gconfiguracao["storage_unico"])
        outros_storages = False
    elif Gconfiguracao["storage_preferencial"] != "":
        print_log("Este agente trabalha com storage preferencial=", Gconfiguracao["storage_preferencial"])
        tarefa = solicita_tarefas(lista_ipeds_suportados, Gconfiguracao["storage_preferencial"])
        outros_storages = True
    else:
        print_log("Este agente trabalha com qualquer storage")
        outros_storages = True

    # Se ainda não tem tarefa, e agente trabalha com outros storages, solicita para qualquer storage
    if tarefa is None and outros_storages:
        # Solicita tarefa para qualquer storage
        tarefa = solicita_tarefas(lista_ipeds_suportados)

    # Se não tem nenhuma tarefa disponível, não tem o que fazer
    if tarefa is None:
        print_log("Nenhuma tarefa fornecida. Nada a fazer.")
        return False

    # Ok, temos trabalho a fazer
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]  # Identificador único da tarefa
    codigo_situacao_tarefa = int(tarefa["codigo_situacao_tarefa"])

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

    # Para ver o conjunto completo, descomentar a linha abaixo
    # var_dump(Gconfiguracao)
    # var_dump(tarefa)

    # Teste de devolução
    #texto_status="teste de devolução"
    #return devolver(codigo_tarefa, texto_status)

    # Teste abortar
    #texto_status="teste de abotar"
    #return abortar(codigo_tarefa, texto_status)


    # Montar storage
    # ------------------------------------------------------------------
    # Confirma que tem acesso ao storage escolhido
    (sucesso, ponto_montagem, erro) = acesso_storage_windows(tarefa["dados_storage"])
    if not sucesso:
        erro = "Acesso ao storage [" + ponto_montagem + "] falhou. Verifique se servidor está acessível (rede) e disponível."
        # Talvez seja um problema de rede (trasiente)
        reportar_erro(erro)
        print_log("Problema insolúvel neste momento, mas possivelmente transiente")
        # Devolve para ser executada por outro agente
        return devolver(codigo_tarefa, erro)

    # Confere se pasta/arquivo de origem está ok
    # ------------------------------------------------------------------
    # O caminho de origem pode indicar um arquivo (.E01) ou uma pasta
    # Neste ponto, seria importante verificar se esta origem está ok
    # Ou seja, se existe o arquivo ou pasta de origem
    caminho_origem = ponto_montagem + tarefa["caminho_origem"]
    print_log("Caminho de origem (", caminho_origem, "): localizado")

    if os.path.isfile(caminho_origem):
        print_log("Arquivo de origem encontrado no storage")
    elif os.path.exists(caminho_origem):
        print_log("Pasta de origem encontrada no storage")
    else:
        # Se não existe nem arquivo nem pasta, tem algo muito errado aqui
        # Aborta esta tarefa para que PCF possa analisar
        erro = "Caminho de origem ["+ caminho_origem + "] não encontrado no storage"
        print_log(erro)
        # Abortando tarefa, pois tem algo errado aqui.
        # Não adianta ficar retentando nesta condição
        return abortar(codigo_tarefa, erro)

    # ------------------------------------------------------------------
    # Pasta de destino
    # ------------------------------------------------------------------
    caminho_destino = ponto_montagem + tarefa["caminho_destino"]

    # ------------------------------------------------------------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------------------------------------------------------------
    # var_dump(Gconfiguracao)
    # var_dump(tarefa)

    # Prepara parâmetros para execução das subatarefas do IPED
    # ========================================================
    tipo_iped = tarefa["tipo"]
    comando = Gconfiguracao["tipo_tarefa"][tipo_iped]["comando"]

    # Adiciona a pasta de origem e destino
    comando = comando + " -d " + caminho_origem + " -o " + caminho_destino

    # Define arquivo para log
    caminho_log_iped = caminho_destino + "\\iped.log"
    comando = comando + " -log " + caminho_log_iped

    # Sem interface gráfica
    comando = comando + " --nogui "

    # Portable
    # Isto aqui é essencial. Caso contrário o multicase não funciona...
    comando = comando + " --portable "

    # Redireciona saída de tela (normal e erro) para arquivo
    caminho_tela_iped = caminho_destino + "\\iped_tela.txt"
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


    # 1) IPED
    # ====================================
    # Executa IPED
    sucesso=executa_iped(codigo_tarefa, comando, caminho_destino, caminho_log_iped, caminho_tela_iped)
    if not sucesso:
        return False

    # Recupera dados do log para utilizar em laudo
    sucesso=recupera_dados_laudo(codigo_tarefa, caminho_log_iped)
    if not sucesso:
        return False

    # 2) Cálculo de HASH
    # ====================================
    # Calcula hash
    sucesso=calcula_hash_iped(codigo_tarefa, caminho_destino)
    if not sucesso:
        return False

    # 3) Ajusta ambiente para Multicase
    # =================================
    sucesso=ajusta_multicase(tarefa, codigo_tarefa, caminho_destino)
    if not sucesso:
        return False


    # Tudo certo, finalizado com sucesso
    dados_relevantes=dict()
    dados_relevantes['laudo'] = Gdados_laudo
    atualizar_status_servidor_loop(codigo_tarefa, GFinalizadoComSucesso, "Tarefa de IPED completamente concluída",
                                   dados_relevantes)
    return True


# ======================================================================
# Rotina Principal 
# ======================================================================

def main():
    # Salva parâmetros da linhas de comando

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
        print("Já existe uma instância deste programa rodando. Abortando execução, pois só pode haver uma única instância deste programa")
        sys.exit(0)


    # Inicialização do programa
    # -----------------------------------------------------------------------------------------------------------------
    print_log(" ===== INÍCIO ", Gprograma, " - (Versao " + Gversao + ")")

    while True:
        lista_ipeds = inicializar()
        if lista_ipeds is None or len(lista_ipeds)==0:
            # Requer atualização para continuar
            # Interrompe o loop, e finaliza
            break

        executou = executar_uma_tarefa(lista_ipeds)
        if not executou:
            # Se não tem atividade, faz uma pausa para evitar sobrecarregar o servidor com requisições
            dormir(GdormirSemServico)


    # Finalização do programa
    # -----------------------------------------------------------------------------------------------------------------
    print_log("===== FIM SAPI - ", Gprograma, " (Versao " + Gversao + ")")


if __name__ == '__main__':

    # testes gerais
    # caminho_destino = "Memorando_1086-16/item11/item11_extracao_iped/"
    # partes=caminho_destino.split("/")
    # subpasta_destino=partes[len(partes)-1]
    # if subpasta_destino=="":
    #     subpasta_destino = partes[len(partes) - 2]
    #
    # var_dump(subpasta_destino)

    main()

