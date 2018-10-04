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
#  - v1.5 : Atualização automática do IPED a partir de servidor de deployment
#  - v1.8 : Utilização de sapilib0.8, servidor de deployment linux
# ======================================================================================================================
# TODO:
# - Recurso de auto-atualização (sapi + iped)
# ======================================================================================================================

# ======================================================================
# Módulos necessários
# ======================================================================
from __future__ import print_function

import platform
import sys
import os
import datetime

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
Gprograma = "sapi_atualiza_iped"
Gversao = "1.9"

# Controle de tempos/pausas
GtempoEntreAtualizacoesStatus = 180
GdormirSemServico = 60
GmodoInstantaneo = False
# GmodoInstantaneo = True

#
Gconfiguracao = dict()
Gcaminho_pid="sapi_atualiza_iped_pid.txt"


# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi.py, para evitar dependência
from sapilib_0_8 import *


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


# Se ocorrer algum erro, será passado para o chamador
def executa_rename(origem, destino):
    dormir(5) # Pausa para deixar sistema operacional se situar
    print_log("Renomeando ", origem, " para ", destino)
    os.rename(origem, destino)
    dormir(5) # Pausa para deixar sistema operacional se situar
    # Verifica se efetuou rename com sucesso
    if os.path.exists(origem):
        print_log("Origem ainda existe. Rename falhou!!!")
        return False
    if not os.path.exists(destino):
        print_log("Destino não existe. Rename falhou!!!")
        return False
    # Tudo certo
    print_log("Ok, renomeado")
    return True

def executa_delete(caminho):
    dormir(5) # Pausa para deixar sistema operacional se situar
    print_log("Excluindo pasta ", caminho)
    shutil.rmtree(caminho)
    dormir(5) # Pausa antes de verificar, para dar tempo do SO se situar
    # Verifica se exclusão foi realmente executada
    if os.path.exists(caminho):
        print_log("Pasta ainda existe. Exclusão FALHOU. Erro inesperado!!!")
        return False

    # Tudo certo
    print_log("Ok, pasta excluída")
    return True


# Atualiza a pasta do sapi_iped
# a partir do servidor de deployment
def atualizar_sapi_iped():

    print_log("Atualizando sapi_iped")

    # Recupera configuração do iped, para determinar pastas
    Gconfiguracao = sapisrv_obter_configuracao_cliente('sapi_iped')
    print_log('Configuracao sapi_iped = ',Gconfiguracao)

    info = obter_info_deployment()
    storage_deployment=info['storage_deployment']
    pasta_deployment_origem=info['pasta_deployment_origem']
    if pasta_deployment_origem is None:
        print_log("pasta_deployment_origem não definida. Verificar configuração no servidor")
        return False

    # Conecta no storage de deployment
    (sucesso, ponto_montagem, erro) = acesso_storage_windows(storage_deployment, tipo_conexao='consulta')
    if not sucesso:
        # Talvez seja um problema de rede (trasiente)
        reportar_erro(erro)
        return False

    print_log("Conectado com sucesso no servidor de deployment")
    caminho_origem = os.path.join(ponto_montagem, pasta_deployment_origem)


    # Aqui deve ter as pastas reais
    # var_dump(Gconfiguracao)

    # Pasta de destino
    caminho_destino = Gconfiguracao.get("pasta_deployment_destino", None)
    if caminho_destino is None:
        print_log("pasta_deployment_destino não definida. Verificar configuração no servidor")
        return False

    # Tudo certo, exibe origem e destino
    print_log("Deployment - Caminho de origem : ", caminho_origem)
    print_log("Deployment - Caminho de destino: ", caminho_destino)

    # Para teste
    #caminho_origem = "C:\\sapi_deployment_dummy\\"
    #caminho_destino = "C:\\sapi_iped\\"


    # Nome para o qual pasta atual sera renomeada
    # ex: C:\sapi_iped => C:\sapi_iped_old
    caminho_destino_old=caminho_destino.rstrip('\\')+"_old"
    # Pasta temporária para fazer a cópia
    caminho_destino_tmp = caminho_destino.rstrip('\\') + "_tmp"

    try:


        # 1) Verifica se pasta de destino do deployment existe
        # -----------------------------------------------------
        print_log("1) Testando se pasta de destino do deployment existe")
        if not os.path.exists(caminho_destino):
            print_log("Erro fatal: Pasta de destino do deployment não existe")
            return False
        else:
            print_log("Ok, pasta de destino existe")

        # 2) Exclui pastas temporárias que podem ter restado de processamento anterior
        # ----------------------------------------------------------------------------
        print_log("2) Excluindo pastas intermediárias que podem ter sobrado de processamentos anteriores")
        # Se a pasta old já existe, exclui
        if os.path.exists(caminho_destino_old):
            if not executa_delete(caminho_destino_old):
                # Falhou. Motivo já foi explicado na função chamada
                return False

        # Se a pasta old já existe, exclui
        #if os.path.exists(caminho_destino_old):
        #    print_log("Excluindo pasta ", caminho_destino_old)
        #    shutil.rmtree(caminho_destino_old)
        #    dormir(5)
        #    if os.path.exists(caminho_destino_old):
        #        print_log("Pasta ainda existe. Exclusão FALHOU. Erro inesperado!!!")
        #        return False
        #dormir(5)  # Pausa para deixar sistema operacional se "situar"

        # Se a pasta tmp já existe, exclui
        if os.path.exists(caminho_destino_tmp):
            if not executa_delete(caminho_destino_tmp):
                # Falhou. Motivo já foi explicado na função chamada
                return False

        # # Se a pasta tmp já existe, exclui
        # if os.path.exists(caminho_destino_tmp):
        #     print_log("Excluindo pasta", caminho_destino_tmp)
        #     shutil.rmtree(caminho_destino_tmp)
        #     dormir(5)
        #     if os.path.exists(caminho_destino_tmp):
        #         print_log("Pasta ainda existe. Exclusão FALHOU. Erro inesperado!!!")
        #         return False
        #
        # dormir(5)  # Pausa para deixar sistema operacional se "situar"

        print_log("Ok, nada mais a excluir")

        # 3) Verifica se pasta de destino do deployment está desimpedida
        # O que pode estar impedindo:
        # - Algum arquivo aberto na pasta
        # - Um prompt de comando aberto na pasta
        # --------------------------------------------------------------
        print_log("3) Testando se pasta de destino do deployment está desimpedida")
        # Renomeia pasta de destino
        # Isto garantir que a pasta está disponível, sem nenhum tipo de lock que impeça a exclusão da mesma
        # (por exemplo, tem um prompt aberto na pasta)
        # Se não for possível renomear, também não será possível excluir depois
        print_log("Testando para ver se consegue renomear",caminho_destino)
        if not executa_rename(caminho_destino, caminho_destino_old):
            # Mensagem de explicação já foi apresenta na função chamada
            return False

        print_log("Voltando para nome anterior")
        if not executa_rename(caminho_destino_old, caminho_destino):
            # Mensagem de explicação já foi apresenta na função chamada
            return False

        print_log("Ok, pasta sapi_iped está livre para ser trabalhada (sem nenhum tipo de lock)")

    except WindowsError as e:
        # Por algum motivo, Erros de windows não estão sendo capturado por OSError e por consequência também
        # não estão sendo capturados por BaseException
        # No manual do python, WindowsErro não é subclasse de OSError....mas segundo usuário deveria ser...
        # Cuidado: Windows excp
        # De qualquer forma, vamos deixar este "reparo" aqui, para repassar qualquer WindowsError para BaseException
        print_log("[281] Erro: ", e)
        return False

    try:

        # Copia a nova versão para pasta de destino temporária
        # --------------------------------------------------------
        # Neste copia vai o sapi e também a pasta do IPED
        # Esta operação é relativamente demorada
        # Se for interrompida no meio, não dará problema,
        # pois estamos apenas para uma pasta tempória
        print_log("4) Copiando "+caminho_origem+" para "+caminho_destino_tmp)
        shutil.copytree(caminho_origem, caminho_destino_tmp)

        dormir(5)  # Pausa para deixar sistema operacional se "situar"

        # Salva a pasta atual para old, caso ocorra algum problema que tenha que ser restaurada
        # -------------------------------------------------------------------------------------
        print_log("5) Protege pasta atual, renomeando para _OLD")
        if not executa_rename(caminho_destino, caminho_destino_old):
            # Mensagem de explicação já foi apresenta na função chamada
            return False

    except WindowsError as e:
        # Por algum motivo, Erros de windows não estão sendo capturado por OSError e por consequência também
        # não estão sendo capturados por BaseException
        # No manual do python, WindowsErro não é subclasse de OSError....mas segundo usuário deveria ser...
        # Cuidado: Windows excp
        # De qualquer forma, vamos deixar este "reparo" aqui, para repassar qualquer WindowsError para BaseException
        print_log("[310] Erro: ", e)
        return False


    try:
        # Renomeia a nova pasta para pasta atual
        # ------------------------------------------------------------------
        deu_erro_rename = False;
        print_log("6) Renomeia TMP (copiada) para pasta atual")
        executa_rename(caminho_destino_tmp, caminho_destino)

    except WindowsError as e:
        # Isto não deveria ter acontecido....já foi tentando em passo anterior e funcionou...
        print_log("[327] Erro: ", e)
        print_log("Isto não deveria ocorrer. Verifique se a pasta de destino está em uso (algum arquivo aberto, prompt ou mesmo aberta no File Explorer")
        deu_erro_rename=True;
        # Aqui não vamos encerrar,
        # Vamos apenas sair da exception para o erro ser melhor tratado
        # pois é muito complicado executar dentro do bloco de exception coisas que podem causar exception

    # Se der erro no rename do TMP para a pasta oficial, volta a situação anterior
    # Se no próximo rename der erro também, aí não tem solução, o servidor ficará inativo exigindo intervenção humana
    if deu_erro_rename:
        print_log("Como o rename da pasta TMP falhou, vamos retornar a pasta old, para deixar o sistema com a situação anterior")
        executa_rename(caminho_destino_old, caminho_destino)
        print_log("Restaurada a situação anterior")
        print_log("Atualização FALHOU, pois não foi possível concluir o procedimento")
        return False

    try:
        # Sobrepõem os parâmetros do iped standard com as configurações específicas
        # -------------------------------------------------------------------------
        print_log("7) Ajustando IPED")
        # Localiza pasta de destino de profiles do IPED
        lista_pasta_iped=list()
        for item in os.listdir(caminho_destino):
            if "IPED-" in item.upper():
                pasta_iped = os.path.join(caminho_destino, item)
                print_log("Localizada pasta do IPED em  =>", pasta_iped)
                lista_pasta_iped.append(pasta_iped)

        if len(lista_pasta_iped)==0:
            print_log("Não foi encontrada pasta do IPED. Confira pasta de deployment")
            return False

        for pasta_iped in lista_pasta_iped:
            print_log("Ajustando IPED que fica na pasta: ", pasta_iped)

            # Copia a pasta de profiles customizados para o IPED
            # --------------------------------------------------
            pasta_profiles_iped = os.path.join(pasta_iped, "profiles", "pt-BR")
            pasta_profiles_customizados = os.path.join(caminho_origem, "profiles_customizados")
            print_log("Copiando pasta [", pasta_profiles_customizados, "] para [", pasta_profiles_iped, "]")
            adiciona_diretorio(pasta_profiles_customizados, pasta_profiles_iped)

            # Copia arquivo de configuração local (relacionado com a máquina, discos SSD, etc)
            # --------------------------------------------------------------------------------
            # Talvez no futuro, seja necessário mais de um arquivo de configuração
            # pois máquinas diferentes podem ter estruturas diferentes (SSD em outra letra, por exemplo)
            # Neste caso, será necessário tornar configurável qual o LocalConfig a ser utilizado
            arquivo_origem = os.path.join(caminho_origem, "LocalConfig_customizados", "LocalConfig.txt")
            arquivo_destino = os.path.join(pasta_iped, "LocalConfig.txt")
            print_log("Copiando arquivo [", arquivo_origem, "] para [", arquivo_destino, "]")
            shutil.copy2(arquivo_origem, arquivo_destino)

            print_log("Ajustado IPED OK")



    except WindowsError as e:
        # Por algum motivo, Erros de windows não estão sendo capturado por OSError e por consequência também
        # não estão sendo capturados por BaseException
        # No manual do python, WindowsErro não é subclasse de OSError....mas segundo usuário deveria ser...
        # Cuidado: Windows excp
        # De qualquer forma, vamos deixar este "reparo" aqui, para repassar qualquer WindowsError para BaseException
        print_log("Erro: ", e)
        return False

    # Ok, tudo certo
    print_log("8) Atualização efetuada com sucesso.")
    return True


# Efetua limpeza na pasta de logs,  mantendo apenas os logs mais recentes
# ----------------------------------------------------------------------------------------------------------------------
def limpa_log():
    logdir=get_parini('logdir', get_parini('pasta_execucao'))
    print_log("9) Efetuando limpeza de arquivo de logs na pasta",logdir)

    qtd_dias_manter_log=7
    data_limite = datetime.datetime.now() - datetime.timedelta(days=qtd_dias_manter_log)
    #data_limite = datetime.datetime.now() - datetime.timedelta(hours=1)
    print_log("Excluindo arquivos de log gerados antes de: ",data_limite)

    qtd_excluido=0
    for arq in os.listdir(logdir):
        arquivo = os.path.join(logdir, arq)
        ts = obter_arquivo_data_modificacao(arquivo)
        if str(ts) <= str(data_limite):
            debug("Excluindo arquivo %-40s alterado em %-20s" % (arquivo,ts))
            os.remove(arquivo)
            qtd_excluido=qtd_excluido+1

    print_log("Quantidade de arquivos excluídos: ", qtd_excluido)


# ======================================================================
# Rotina Principal 
# ======================================================================
def main():

    global Gconfiguracao

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
        finalizar_sucesso("Já existe uma instância deste programa rodando. Abandonando execução, pois só pode haver uma única instância deste programa")

    # Ok, iniciando
    print_log("============= INÍCIO ", Gprograma, " - (Versão " + Gversao + ")")

    # Verifica se deve ser atualizado
    # -------------------------------
    try:
        # Efetua inicialização
        # Neste ponto, se a versão do sapi_iped estiver desatualizada será gerado uma exceção
        print_log("Efetuando inicialização")
        sapisrv_inicializar(Gprograma, Gversao)  # Outros parâmetros: nome_agente='xxxx', ambiente='desenv'
        print_log("Inicialização efetuada")

    except SapiExceptionVersaoDesatualizada:
        # Se versão do sapi_atualiza_iped está desatualizado, prossegue da mesma forma
        # pois este programa também será atualizado
        print_log("sapi_iped desatualizado, será atualizado na sequencia")

    except Exception as e:
        # Para outras exceçõs, exibe erro e aborta
        print_log("[285]: ", str(e))
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                                  limit=2, file=sys.stdout)
        finalizar_erro("Erro inesperado")

    try:
        # Efetuando atualização
        atualizou=atualizar_sapi_iped()
    except Exception as e:
        # Para outras exceçõe, registra e finaliza
        trc_string=traceback.format_exc()
        print_log("[332]: Exceção abaixo sem tratamento específico. Avaliar se deve ser tratada")
        print_log(trc_string)
        finalizar_erro("Falhou na tentativa de atualizar versão")

    # Se atualizou com sucesso, efetua outras atividades
    if atualizou:
        limpa_log()

    # Para evitar sobrecarregar o servidor (com muitos clientes solicitando efetuando atualização)
    # durante períodos de problema (indisponibilidade do servidor SAPI, por exemplo)
    # faz um pausa após cada atualização/tentativa
    dormir(GdormirSemServico,"Dormindo para evitar sobrecarga do servidor")

    # Tudo certo
    if atualizou:
        finalizar_sucesso("sapi_iped atualizado com sucesso")
    else:
        finalizar_erro("Falha na atualização do sapi_iped")



def finalizar_sucesso(mensagem):
    finalizar(0, mensagem)

def finalizar_erro(mensagem):
    finalizar(1, mensagem)

def finalizar(status, mensagem):
    print_log(mensagem)
    print_log("============= FIM ", Gprograma, " - (Versao " + Gversao + ")")
    sys.exit(status)


# ===================================================================================================================
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

