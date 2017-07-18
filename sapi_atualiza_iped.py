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
# ======================================================================================================================
# TODO:
# - Limpar pasta indexador no final da execução (IPED não está conseguindo limpar)
# - Recurso de auto-atualização (sapi + iped)
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
Gprograma = "sapi_atualiza_iped"
Gversao = "1.8.1"

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
    (sucesso, ponto_montagem, erro) = acesso_storage_windows(storage_deployment)
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
    caminho_destino_renomeado=caminho_destino.rstrip('\\')+"_old"
    # Pasta temporária para fazer a cópia
    caminho_destino_tmp = caminho_destino.rstrip('\\') + "_tmp"

    try:
        # Se a pasta old já existe, exclui
        if os.path.exists(caminho_destino_renomeado):
            print_log("Excluindo pasta [", caminho_destino_renomeado, "]")
            shutil.rmtree(caminho_destino_renomeado)
            if os.path.exists(caminho_destino_renomeado):
                print_log("Pasta ainda existe. Exclusão FALHOU. Erro inesperado!!!")
                return False

        # Se a pasta tmp já existe, exclui
        if os.path.exists(caminho_destino_tmp):
            print_log("Excluindo pasta [", caminho_destino_tmp, "]")
            shutil.rmtree(caminho_destino_tmp)
            if os.path.exists(caminho_destino_tmp):
                print_log("Pasta ainda existe. Exclusão FALHOU. Erro inesperado!!!")
                return False

        # Renomeia pasta de destino
        # Isto garantir que a pasta está disponível, sem nenhum tipo de lock que impeça a exclusão da mesma
        # (por exemplo, tem um prompt aberto na pasta)
        # Se não for possível renomear, também não será possível excluir depois
        print_log("Testando para ver se consegue renomear [",caminho_destino,"] para [", caminho_destino_renomeado,"]")
        os.rename(caminho_destino, caminho_destino_renomeado)

        print_log("Voltando para nome anterior")
        os.rename(caminho_destino_renomeado, caminho_destino)
        print_log("Ok, pasta sapi_iped está livre para ser trabalhada (sem nenhum tipo de lock)")

    except WindowsError as e:
        # Por algum motivo, Erros de windows não estão sendo capturado por OSError e por consequência também
        # não estão sendo capturados por BaseException
        # No manual do python, WindowsErro não é subclasse de OSError....mas segundo usuário deveria ser...
        # Cuidado: Windows excp
        # De qualquer forma, vamos deixar este "reparo" aqui, para repassar qualquer WindowsError para BaseException
        print_log("[258] Erro: ", e)
        return False

    try:

        # Copia a nova versão para pasta de destino temporária
        # Neste copia vai o sapi e também a pasta do IPED
        # Esta operação é relativamente demorada
        # Se for interrompida no meio, não dará problema,
        # pois estmaos apenas para outra pasta
        print_log("Copiando de ["+caminho_origem+"] para ["+caminho_destino_tmp+"]")
        shutil.copytree(caminho_origem, caminho_destino_tmp)

        # TODO: O ideal é que isto aqui fosse atômico. O windows parece ter este conceito, mas não é trivial (via API)
        # Renomeia pasta atual para OLD
        print_log("Renomeando [",caminho_destino,"] para [", caminho_destino_renomeado,"]")
        os.rename(caminho_destino, caminho_destino_renomeado)
        # Renomeia pasta tmp para atual
        print_log("Renomeando [",caminho_destino_tmp,"] para [", caminho_destino,"]")
        os.rename(caminho_destino_tmp, caminho_destino)

        # Sobrepõem os parâmetros do iped standard com as configurações específicas
        # -------------------------------------------------------------------------
        # Localiza pasta de destino de profiles do IPED
        pasta_iped = None
        for item in os.listdir(caminho_destino):
            if "IPED-" in item:
                pasta_iped = os.path.join(caminho_destino, item)
                print_log("Localizada pasta do IPED em  =>", pasta_iped)

        if pasta_iped is None:
            print_log("Não foi encontrada pasta do IPED")
            return False

        # Copia a pasta de profiles customizados para o IPED
        # --------------------------------------------------
        pasta_profiles_iped = os.path.join(pasta_iped, "profiles")
        pasta_profiles_customizados = os.path.join(caminho_origem, "profiles_customizados")
        print_log("Copiando pasta [", pasta_profiles_customizados, "] para [", pasta_profiles_iped, "]")
        adiciona_diretorio(pasta_profiles_customizados, pasta_profiles_iped)

        # Copia arquivo de configuração local (relacionado com a máquina, discos SSD, etc)
        # --------------------------------------------------------------------------------
        # Talvez no futuro, seja necessário mais de um arquivo de configuração
        # Neste caso, será necessário tornar configurável
        arquivo_origem = os.path.join(caminho_origem, "LocalConfig_customizados", "LocalConfig.txt")
        arquivo_destino = os.path.join(pasta_iped, "LocalConfig.txt")
        print_log("Copiando arquivo [", arquivo_origem, "] para [", arquivo_destino, "]")
        shutil.copy2(arquivo_origem, arquivo_destino)

    except WindowsError as e:
        # Por algum motivo, Erros de windows não estão sendo capturado por OSError e por consequência também
        # não estão sendo capturados por BaseException
        # No manual do python, WindowsErro não é subclasse de OSError....mas segundo usuário deveria ser...
        # Cuidado: Windows excp
        # De qualquer forma, vamos deixar este "reparo" aqui, para repassar qualquer WindowsError para BaseException
        print_log("Erro: ", e)
        return False

    # Ok, tudo certo
    print_log("Atualização efetuada com sucesso.")
    return True


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
        # Para outras exceçõs, irá ficar tentanto eternamente
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

