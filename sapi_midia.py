# -*- coding: utf-8 -*-
#
# ===== PYTHON 3 ======
#
# =======================================================================
# SAPI - Sistema de Apoio a Procedimentos de Informática
# 
# Componente: sapi_laudo
# Objetivo: Agente para geração de laudo modelo SAPI
# Funcionalidades:
#  - Conexão com o servidor SAPI para obter de dados das tarefas
#    realizada (dados de materiais, procedimentos, etc)
#  - Geração e substituição de dados variáveis em template de laudo
#
#
# Histórico:
#  - v1.8 : Inicial - Cisão do sapi_laudo.py
# =======================================================================
#
#
# =======================================================================

# Módulos utilizados
# ====================================================================================================
from __future__ import print_function
import platform
import sys
import copy
import xml.etree.ElementTree
import tempfile
import shutil
import zipfile
import multiprocessing
import signal



# Verifica se está rodando versão correta de Python
# ====================================================================================================
if sys.version_info <= (3, 0):
    sys.stdout.write("Versao do intepretador python (" + str(platform.python_version()) + ") inadequada.\n")
    sys.stdout.write("Este programa requer Python 3 (preferencialmente Python 3.5.2).\n")
    sys.exit(1)

# =======================================================================
# GLOBAIS
# =======================================================================
Gprograma = "sapi_midia"
Gversao = "1.8.1"

# Para gravação de estado
Garquivo_estado = Gprograma + "v" + Gversao.replace('.', '_') + ".sapi"

# Base de dados (globais)
GdadosGerais = dict()  # Dicionário com dados gerais
Glaudo = None
Gitens = list()  # Lista de itens do laudo
Gstorages = None
Gsolicitacao_exame = None
Gmateriais_solicitacao = None
Gstorages_laudo = list()  # Lista de storages associados a tarefas do laudo
Gmod_constantes = list() # Dados coletados do modelo

# Relativo a mídia de destino
Gitem_midia=dict()
Gresumo_midia=dict()

# Diversos sem persistência
Gicor = 1
Glargura_tela = 129

# ------- Definição de comandos aceitos --------------
Gmenu_comandos = dict()
Gmenu_comandos['comandos'] = {
    # Comandos de navegacao
    '+': 'Navega para a tarefa seguinte da lista',
    '-': 'Navega para a tarefa anterior da lista',

    # Comandos relacionados com uma mídia
    '*gm': 'Gera mídia de destino, copiando dados do servidor para destino indicado',
    '*du': 'Dump: Mostra todas as propriedades de uma tarefa (utilizado para Debug)',

    # Comandos exibição
    '*sg': 'Exibir situação atualizada (com refresh do servidor). ',

    # Comandos para diagnóstico de problemas
    '*db': 'Ligar/desligar modo debug. No modo debug serão geradas mensagens adicionais no log.',
    '*lg': 'Exibir log geral.',

    # Comandos gerais
    '*tm': 'Troca mídia de destino dos itens',
    '*s3': 'Abrir solicitação de exame no SETEC3',
    '*s3g': 'Abrir lista de Pendências SAPI no SETEC3',
    '*sto': 'Exibir pasta da solicitaçaõ de exame no storage através do File Explorer',
    '*cl': 'Exibir laudo no SISCRIM',
    '*tt': 'Troca laudo',
    '*qq': 'Finaliza'
}

Gmenu_comandos['cmd_exibicao'] = ["*sg"]
Gmenu_comandos['cmd_navegacao'] = ["+", "-"]
Gmenu_comandos['cmd_item'] = ["*si", "*tm"]
Gmenu_comandos['cmd_geral'] = ['*sg', '*gm', '*s3', '*s3g', '*sto', '*cl',  '*tt', '*qq']
Gmenu_comandos['cmd_diagnostico'] = ['*lg', '*db']

# Debug
Gverbose = False  # Aumenta a exibição de detalhes (para debug)

# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi_xxx.py, para evitar dependência
from sapilib_0_8 import *

# **********************************************************************
# PRODUCAO
# **********************************************************************

# ======================================================================
# Funções Auxiliares específicas deste programa
# ======================================================================


def print_centralizado(texto='', tamanho=Glargura_tela, preenchimento='-'):
    direita = (tamanho - len(texto)) // 2
    esquerda = tamanho - len(texto) - direita
    print(preenchimento * direita + texto + preenchimento * esquerda)
    return


def exibir_dados_laudo(dados_laudo, tarefa):
    print_centralizado(" Dados para da tarefa laudo ")

    console_dump_formatado(dados_laudo, Glargura_tela)

    print("-" * 100)

    # var_dump(d)

    return

def exibir_dados_item(dados_item):

    # ------------------------------------------------------------------
    # Exibe dados do item para usuário
    # ------------------------------------------------------------------
    print()
    print_centralizado("")
    print("Item: ", dados_item["item_apreensao"])
    print("Material: ", dados_item["material"])
    print("Descrição: ", dados_item["descricao"])
    print_centralizado("")


# Exibe dados de laudo para um item
def exibir_situacao_item(item):
    # Cabeçalho
    print()
    print_centralizado(" Exibindo situação do item corrente ")
    print("- Recuperando dados do servidor. Aguarde...")

    # Recupera as tarefas de um item
    # ------------------------------------------------------------------
    item_tarefas = sapisrv_chamar_programa_sucesso_ok(
        programa="sapisrv_obter_tarefas.php",
        parametros={
            'codigo_solicitacao_exame_siscrim': GdadosGerais["codigo_solicitacao_exame_siscrim"],
            'item': item,
            'tipo': 'todos'
            # , 'situacao': 'finalizada'
        })

    # ------------------------------------------------------------------
    # Exibe dados do item para usuário
    # ------------------------------------------------------------------
    dados_item = Gitens[obter_midia_corrente()]
    exibir_dados_item(dados_item)

    # Exibe dados para laudo armazenados nas tarefas
    # ------------------------------------------------------------------
    for it in item_tarefas:
        t = it["tarefa"]

        print()
        print_centralizado(" Tarefa" + t["codigo_tarefa"] + " ")
        print("Tipo de tarefa:", t["tipo"])
        print("Situação:", t["codigo_situacao_tarefa"], "-", t["descricao_situacao_tarefa"])

        if t["dados_relevantes_json"] is not None:
            dados_relevantes_json = json.loads(t["dados_relevantes_json"])
            print()
            print("Dados para laudo:")
            print("=================")
            print()
            console_dump_formatado(dados_relevantes_json["laudo"], Glargura_tela)
            print()

    return


# Exibe dados de laudo para o item corrente
def exibir_situacao_item_corrente():
    item = Gitens[obter_midia_corrente()]["item"]
    exibir_situacao_item(item)

# ----------------------------------------------------------------------------------------------------------------------
# @*tm - Troca mídia de destino do item corrente
# ----------------------------------------------------------------------------------------------------------------------
def trocar_midia():
    console_executar_tratar_ctrc(funcao=_trocar_midia)

def _trocar_midia():

    print()
    print("- Troca identificador da mídia de destino")

    # Exibir lista de itens para usuário escolher o que deseja alterar

    while True:
        #
        try:
            exibir_lista_itens()
            print()
            ix_item = selecionar_item()
            ajustar_item_midia(ix_item)
        except KeyboardInterrupt:
            return False

def selecionar_item():

    while True:
        sq = input("< Sequencial (Sq) do item a ser ajustado ou CTR-C para interromper: ")
        sq = sq.strip()
        if sq=="":
            return

        if not sq.isdigit() or int(sq)<1 or int(sq)>len(Gitens):
            print("- Entre com número entre 1 e " + len(Gitens))

        # Retorna o índice, que inicia em zero
        ix_item=int(sq)-1
        return ix_item

def ajustar_item_midia(sq_item):

    # Recupera dados do item
    dados_item = Gitens[sq_item]
    exibir_dados_item(dados_item)

    item=dados_item["item"]

    # Mídia atual
    print()
    print("- Mídia atual: ", Gitem_midia.get(item,1))
    while True:
        #
        midia = input("< Nova mídia (ex: 2): ")
        midia = midia.strip()

        if not midia.isdigit():
            print("- Entre com o número identificador da mídia parcial (1, 2, 3, etc)")
            continue

        # Ok, tudo certo
        Gitem_midia[item]=int(midia)
        return



# Verifica se todos as tarefas dos materiais associados ao laudo estão concluídos
# Retorna: True/False
def laudo_pronto():

    refresh_itens()

    # Conta quantidade de itens que não estão prontos para laudo
    qtd_nao_pronto = 0
    for i in Gitens:
        if not i["pronto_para_laudo"] == 't':
            qtd_nao_pronto += 1

    if qtd_nao_pronto > 0:
        print("- Existem ", qtd_nao_pronto, "itens que NÃO ESTÃO PRONTOS para laudo.")
        return False

    # Tudo certo
    return True


# ==================================================================================================================
# @*gm - Geração de mídia
# ==================================================================================================================

# Gera mídia de destino
# ----------------------------------------------------------------------------------------------------------------------
def gerar_midia_destino():
    console_executar_tratar_ctrc(funcao=_gerar_midia_destino)

def _gerar_midia_destino():

    print()
    print_centralizado(" Gerar mídia de destino ")

    # Verifica se laudo pode ser gerado
    # ------------------------------------------------------------------------------------------------------------------
    if not laudo_pronto():
        # Mensagens já foram exibidas na rotina chamada
        print("- Geração de mídia não pode ser realizada nesta situação")
        print("- Comando cancelado")
        return


    # -----------------------------------------------------------------
    # Acessando dados de origem (no storage)
    # -----------------------------------------------------------------
    print()
    print("1) Verificando dados de origem no storage")
    print("=========================================")
    storage=recuperar_storage_unico()
    if storage is None:
        # Mensagens de erro já foram fornecidas
        return
    print("- Storage do laudo: ", storage["maquina_netbios"])

    # Montagem de storage
    # -------------------
    # Confirma que tem acesso ao storage escolhido
    ponto_montagem = conectar_storage_consulta_ok(storage)
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return

    # Confirma existência da pasta do exame
    pasta_memorando_storage = montar_caminho(
        ponto_montagem,
        Gsolicitacao_exame["pasta_memorando"])
    print("- Pasta do exame:")
    print("  ", pasta_memorando_storage)
    if not os.path.exists(pasta_memorando_storage):
        print("- Não foi encontrando pasta para memorando no storage")
        print("- Comando cancelado")
        return


    # Confere lista de pastas a serem copiadas
    # ----------------------------------------
    lista_subpastas=list()

    # Verificação de integridade no storage
    # -------------------------------------------------------------------
    # Verifica pasta multicase
    subpasta="multicase"
    pasta_multicase = montar_caminho(
        pasta_memorando_storage,
        subpasta)
    if not os.path.exists(pasta_multicase):
        print("- Não foi encontrado no storage pasta multicase", pasta_multicase)
        print("- Comando cancelado")
        return False
    else:
        print("- Pasta encontrada:", pasta_multicase)
        lista_subpastas.append(subpasta)

    # Verificar se existem pastas no storage para todos os itens do laudo
    # -------------------------------------------------------------------
    print("- Conferindo existência de pasta para os itens/materiais do laudo...")
    falta_pasta=False
    for m in Gitens:
        subpasta=m["subpasta"]
        pasta_item = montar_caminho(
            pasta_memorando_storage,
            subpasta)
        if not os.path.exists(pasta_item):
            print("- Não foi encontrado no storage pasta de dados", pasta_item,"para o item: ", m["item"],"(",m["material"],")")
            falta_pasta=True
        else:
            print("- Pasta encontrada:", pasta_item)
            lista_subpastas.append(subpasta)

    if falta_pasta:
        print("- A falta de pasta de destino pode significar que existe algum item que é inexequível, ou que por algum outro motivo não foi processado")
        print("- Ou ainda uma incompatibilidade entre os materiais vínculados ao laudo com o que foi efetivamente examinado")
        prosseguir = pergunta_sim_nao("< Deseja prosseguir mesmo assim?", default="n")
        if not prosseguir:
            # Encerra
            print("- Cancelado pelo usuário.")
            return
    else:
        print("- Todas as pastas dos itens do laudo foram localizadas no storage")


    # ------------------------------------------------------------------------------------------------------------------
    # Exibe tamanhos de pastas, e dá opção para subdivisão de mídia
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("2) Mídia de destino")
    print("===================")

    # Confirma escolha das mídias de destino
    resumir_midia()
    print()
    qtd_midias=0
    for k_m in Gresumo_midia:
        tamanho_destino_bytes = int(Gresumo_midia[k_m]["tamanho_destino_bytes"])
        lista_itens = ", ".join(Gresumo_midia[k_m]["lista_itens"])
        print("* Mídia", k_m, "=> tamanho total: ", converte_bytes_humano(tamanho_destino_bytes), "itens: ", lista_itens)
        qtd_midias += 1

    if qtd_midias == 0:
        print("- [2615] Situação inesperada. Não foi encontrado mídias")
        return

    if qtd_midias == 1:
        print()
        print("- Você escolheu gerar apenas uma mídia de destino com", converte_bytes_humano(tamanho_destino_bytes))

    print()
    if qtd_midias==1:
        print("- Confira se o tamanho total a ser gravado cabe na mídia de destino")
    else:
        print("- Confira se o tamanho total a ser gravado por mídia está adequado com a capacidade de cada mídia de destino")
    print("- Se for necessário ajustar a quantidade de mídias de destino, cancele a execução deste comando")
    print("  e depois utilize a comando *TM para informar a mídia para cada item")
    print()
    prosseguir = pergunta_sim_nao(
        "< Prosseguir na gravação de mídia de destino?",
        default="n")
    if not prosseguir:
        # Encerra
        print("- Cancelado pelo usuário.")
        return

    # zzzz
    #var_dump(Gresumo_midia)
    #var_dump(len(Gresumo_midia))
    #die('ponto2614')
    # zzzz


    # ------------------------------------------------------------------------------------------------------------------
    # Seleciona a pasta de destino
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("2) Selecione o caminho para onde será copiado dados da mídia de destino")
    print("========================================================================")
    if qtd_midias==1:
        print("- Agora você deverá informar o caminho para a mídia de destino")
    else:
        print("- Agora você deverá informar o caminho para cada uma das mídias de destino")
    print("- Para HD externo, informe o drive em que está montando o HD externo.")
    print("- Para mídia óptica, informe a pasta de trabalho, para a qual posteriormente você produzirá o iso")
    print()

    lista_pasta_destino=list()
    for k_m in Gresumo_midia:
        label_midia=str(k_m)
        if  qtd_midias==1:
            label_midia=""

        while True:

            titulo_selecionar_pasta=None
            if qtd_midias>1:
                print()
                print("========= Mídia", label_midia, "===============")
                titulo_selecionar_pasta="Selecionar pasta para Mídia "+ label_midia

            print("- Informe o caminho para a mídia de destino", label_midia)

            # Solicita a pasta de destino (ou drive)
            root = tkinter.Tk()
            j = JanelaTk(master=root)
            caminho_destino = j.selecionar_pasta(titulo_selecionar_pasta)
            root.quit()
            root.destroy()

            # Valida pasta/drive de destino
            if (caminho_destino == ""):
                print("- Nenhum caminho de destino foi selecionado.")
                # Interrompe comando
                return
            print("- Caminho de destino selecionado para mídia", label_midia, ":", caminho_destino)

            # Verifica se no caminho de destino já existe uma pasta com o nome da pasta de origem
            pasta_memorando_destino = montar_caminho(
                caminho_destino,
                Gsolicitacao_exame["pasta_memorando"])
            print("- Pasta de destino (a ser criada):")
            print("  ", pasta_memorando_destino)
            if os.path.exists(pasta_memorando_destino):
                print_atencao()
                print("- Pasta a ser criada na mídia de destino já existe.")
                print("- Isto pode ocorrer se o comando de geração de mídia já foi iniciado anteriormente.")
                print("- Caso contrário, procure entender a situação antes de prosseguir.")
                print()
                print("- Para prosseguir, será necessário primeiramente excluir a pasta existente")
                prosseguir = pergunta_sim_nao(
                    "< Você realmente deseja excluir a pasta de destino?",
                    default="n")
                if not prosseguir:
                    # Encerra
                    print("- Cancelado pelo usuário.")
                    return
                print("- Ok, pasta de destino será excluída.")
                print_log("Usuário solicitou exclusão da pasta de destino na mídia de destino: ", pasta_memorando_destino)

            # Verifica se usuário repetiu a pasta de destino por engano
            if pasta_memorando_destino in lista_pasta_destino:
                print_atencao()
                print("- Esta pasta de destino já foi informada para outra mídia")
                print("- Cada mídia deve ter uma pasta de destino distinta")
                continue
            lista_pasta_destino.append(pasta_memorando_destino)

            # Tudo certo, armazena pasta de destino na mídia e passa para a próxima
            Gresumo_midia[k_m]["pasta_memorando_destino"]=pasta_memorando_destino
            break

    # ------------------------------------------------------------------------------------------------------------------
    # Gerar mídia de destino
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("3) Gerar mídia de destino")
    print("=========================")
    print()
    for k_m in Gresumo_midia:
        m = Gresumo_midia[k_m]
        tamanho_destino_bytes = int(m["tamanho_destino_bytes"])
        lista_itens = ", ".join(m["lista_itens"])
        pasta_memorando_destino = m["pasta_memorando_destino"]
        print("* Mídia", k_m,
              "=> tamanho total: ", converte_bytes_humano(tamanho_destino_bytes))
        print("  itens:", lista_itens)
        print("  destino:", pasta_memorando_destino)
        print()

    print("- Está tudo pronto para iniciar geração da mídia de destino, que será efetuada em background.")
    print("- Efetue a conferência final para garantir que está tudo ok.")
    print()
    prosseguir = pergunta_sim_nao("< Iniciar geração das mídias de destino? ", default="n")
    if not prosseguir:
        return

    # ------------------------------------
    # Inicia procedimentos em background
    # ------------------------------------
    print_log("Iniciando geração de mídia (*gm)")

    # Os processo filhos irão atualizar o mesmo arquivo log do processo pai
    nome_arquivo_log_para_processos_filhos = obter_nome_arquivo_log()

    for k_m in Gresumo_midia:
        # Label da mídia, se houver mais do que uma
        label_midia=str(k_m)
        if  qtd_midias==1:
            label_midia=""

        # Daos para para serem passados para processo em background
        m = Gresumo_midia[k_m]
        pasta_memorando_destino = m["pasta_memorando_destino"]
        lista_subpastas = m["lista_subpastas"]
        print_log("Iniciando processo em background geração da mídia", label_midia, "contendo subpastas", lista_subpastas)

        # Adiciona pasta de multicase na lista de subpastas
        lista_subpastas.append("multicase")

        # Inicia processo filho para execução da geração da mídia
        # ------------------------------------------------------------------------------------------------------------------
        label_processo = "background_gerar_midia" + label_midia
        dados_pai_para_filho=obter_dados_para_processo_filho()
        p_executar = multiprocessing.Process(
            target=background_gm,
            args=(pasta_memorando_storage, pasta_memorando_destino, lista_subpastas,
                  nome_arquivo_log_para_processos_filhos, label_processo,
                  dados_pai_para_filho)
        )
        p_executar.start()

        registra_processo_filho(label_processo, p_executar)

    # Tudo certo, agora é só aguardar
    print()
    print("- Ok, geração da mídia (Cópia + ajustes no multicase) será feita em background.")
    print("- Você pode continuar trabalhando, e será avisando quando geração da mídia for concluída.")
    print("- Para acompanhar o progresso, ou em caso de dúvida, utilize *LG para visualizar o log")
    print("- IMPORTANTE: NÃO feche este programa antes da conclusão da geração da mídia, ")
    print("  caso contrário o procedimento terá que ser reiniciado")
    print("")

    return

# Efetua a geração da mídia (cópia, ajustes multicase, checagens, etc)
def background_gm(
        pasta_memorando_storage, pasta_memorando_destino, lista_subpastas,
        nome_arquivo_log, label_processo,
        dados_pai_para_filho):

    # Impede interrupção por sigint
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Inicializa sapilib
    # Será utilizado o mesmo arquivo de log do processo pai
    sapisrv_inicializar(Gprograma, Gversao, nome_arquivo_log=nome_arquivo_log, label_processo=label_processo)

    # Restaura dados herdados do processo pai
    restaura_dados_no_processo_filho(dados_pai_para_filho)
    # Label do processo será utilizado para rotular as linhas de log
    # Tem que resetar aqui, pois restauração limpou esta informação
    if label_processo is not None:
        set_parini('label_log', label_processo)

    # ------------------------------------------------------------------
    # Conceito:
    # ------------------------------------------------------------------
    sucesso=False
    try:
        # 1) Marca início em background
        print_log("Início de geração de mídia")

        # 2) Prepara pasta de destino
        # ------------------------------------------------------------------
        # Se pasta do memorando já existe, exclui
        if os.path.exists(pasta_memorando_destino):
            # Exclui pasta de destino
            print_log("Excluindo pasta de destino:", pasta_memorando_destino)
            shutil.rmtree(pasta_memorando_destino)
            # Verifica se excluiu com sucesso
            time.sleep(5)
            if os.path.exists(pasta_memorando_destino):
                raise Exception("Exclusão de pasta de destino falhou")

            # Ok, exclusão concluída
            print_log("Pasta de destino excluída")

        # 3) Copia cada uma das subpastas
        # ------------------------------------------------------------------
        for subpasta in lista_subpastas:
            caminho_origem=montar_caminho(pasta_memorando_storage, subpasta)
            caminho_destino=montar_caminho(pasta_memorando_destino, subpasta)

            print_log("Copiar de:", caminho_origem)
            print_log("Copiar para:", caminho_destino)

            # 3.1) Determina características da pasta de origem
            # ---------------------------------------------------
            print_log("Calculando tamanho da pasta de origem...")
            # Registra características da pasta de origem
            carac_origem = obter_caracteristicas_pasta(caminho_origem)
            tam_pasta_origem = carac_origem.get("tamanho_total", None)
            if tam_pasta_origem is None:
                # Se não tem conteúdo, aborta...
                # Isto não deveria acontecer nunca....
                raise Exception("Pasta de origem com tamanho indefinido")
            # Registra em log
            print_log("Pasta de origem com " + converte_bytes_humano(tam_pasta_origem) + \
                           " (" + str(carac_origem["quantidade_arquivos"]) + " arquivos)")

            # 3.2) Executa a cópia
            # ------------------------------------------------------------------
            print_log("Copiando", subpasta,"...")
            shutil.copytree(caminho_origem, caminho_destino)
            print_log("Cópia finalizada")

            # 3.3) Confere se cópia foi efetuada com sucesso
            # ------------------------------------------------------------------
            # Compara tamanho total e quantidade de arquivos
            print_log("Conferindo cópia (tamanho e quantidade de arquivos)...")

            carac_destino = obter_caracteristicas_pasta(caminho_destino)
            if carac_origem["tamanho_total"]==carac_destino["tamanho_total"]:
                print_log("Tamanho total confere")
            else:
                print("Divergência entre tamanho total de origem (",carac_origem["tamanho_total"],") e destino (",carac_origem["tamanho_total"],")")
                raise Exception("Divergência de tamanho")

            if carac_origem["quantidade_arquivos"]==carac_destino["quantidade_arquivos"]:
                print_log("Quantidade de arquivos confere")
            else:
                print("Divergência de quantidade de arquivos entre origem (", carac_origem["quantidade_arquivos"], ") e destino (",
                      carac_origem["quantidade_arquivos"], ")")
                raise Exception("Divergência de quantidade de arquivos")

            print_log("Tamanho total e quantidade de arquivos compatíveis")

            # 3.4) Se chegou aqui, sucesso
            # ============================
            print_log("Cópia da subpasta",subpasta,"concluída com sucesso")
            sucesso=True

        # Se chegou aqui, todas as subpastas foram copiadas com sucesso
        print_log("Todas as subpastas dos itens do laudo foram copiadas COM SUCESSO")

        # 4) Copia de arquivos avulsos
        # ------------------------------------------------------------------
        print_log("Copiando arquivos avulsos...")
        lista_avulsos=["ferramenta_pesquisa.bat"]
        for arquivo in lista_avulsos:
            caminho_arquivo_origem=montar_caminho(pasta_memorando_storage, arquivo)
            caminho_arquivo_destino=montar_caminho(pasta_memorando_destino, arquivo)
            shutil.copyfile(caminho_arquivo_origem, caminho_arquivo_destino)
            print_log("Copiado arquivo",arquivo)

        # 5) Conferir/ajustar multicase
        # ------------------------------------------------------------------
        print_log("Ajuste de multicase")
        arquivo_multicase=montar_caminho(pasta_memorando_destino, "multicase", "iped-itens.txt")

        # Exemplo de arquivo 'iped_itens.txt'
        #../item01Arrecadacao01/item01Arrecadacao01_extracao_iped
        #../item04Arrecadacao06/item04Arrecadacao06_extracao_iped
        #../item05Arrecadacao06/item05Arrecadacao06_extracao_iped
        #../item08Arrecadacao18/item08Arrecadacao18_extracao_iped

        # Durante o ajuste, serão mantidas apenas as pastas relativas a itens que fazem parte do laudo

        # Le conteúdo atual do arquivo multicase
        with open(arquivo_multicase, "r") as f:
            linhas = f.readlines()

        # Reescreve arquivo, removendo linhas que não estão na lista de subpastas dos itens do laudo (parcial)
        with open(arquivo_multicase, "w") as new_f:
            for linha in linhas:
                # Verifica se linha contém alguma das subpastas de itens do laudo
                achou=False
                for subpasta in lista_subpastas:
                    procurar="/"+subpasta+"/"
                    if procurar in linha:
                        achou=True
                        break
                if achou:
                    print_log("Pasta mantida no multicase: ", linha)
                    new_f.write(linha)
                else:
                    print_log("Pasta descartada do multicase (laudo parcial): ", linha)

    except OSError as e:
        # Erro fatal: Mesmo estando em background, exibe na tela
        print_tela_log("- [2758] ** ERRO em *GM:" + str(e))
        print("- Consulte log para mais informações")
        sucesso=False

    except BaseException as e:
        # Erro fatal: Mesmo estando em background, exibe na tela
        print_tela_log("- [2587]** ERRO em *GM:" + str(e))
        print("- Consulte log para mais informações")
        sucesso=False

    # -----------------------------------------------------------------------------------------------------------------
    # COPIA COM ERRO
    # -----------------------------------------------------------------------------------------------------------------
    if not sucesso:
        # Encerra
        print_log("ERRO: Comando *GM falhou")
        sys.exit(0)

    # -----------------------------------------------------------------------------------------------------------------
    # Tudo certo
    # -----------------------------------------------------------------------------------------------------------------
    print()
    print("- Geração de mídia foi efetuada com sucesso na pasta: ", pasta_memorando_destino)
    print("- Efetue conferência para garantir que resultado está ok")
    print_log("Fim da *GM com sucesso")
    sys.exit(0)

# *gm - fim ----------------------------------------------------------------



def print_linha_cabecalho():
    # Cabeçalho geral
    # --------------------------------------------------------------------------------
    cls()
    # ambiente de execução
    ambiente = obter_ambiente()
    if ambiente == 'PRODUCAO':
        ambiente = ''
    else:
        ambiente = "@" + ambiente
    # Dados identificadores
    print(GdadosGerais.get("identificacaoObjeto", None), " | ",
          GdadosGerais.get("data_hora_ultima_atualizacao_status", None), " | ",
          Gprograma + str(Gversao),
          ambiente)
    print_centralizado()

# Monta resumo por mídia de destino
def resumir_midia():

    global Gresumo_midia

    Gresumo_midia=dict()
    for i in Gitens:

        # Dados do item
        item=i['item']
        subpasta=i["subpasta"]
        t=i.get("tamanho_destino_bytes",0)
        if t is None:
            t=0
        tamanho_destino_bytes=int(t)

        # Mídia de destino
        midia = Gitem_midia.get(i["item"], 1)
        # Se não existe, coloca como default '1'
        Gitem_midia[i["item"]] = midia

        # Se não existe resumo para a mídia, gera
        if Gresumo_midia.get(midia, None) is None:
            Gresumo_midia[midia]=dict()
            Gresumo_midia[midia]["lista_itens"] = list()
            Gresumo_midia[midia]["lista_subpastas"] = list()
            Gresumo_midia[midia]["tamanho_destino_bytes"] = 0

        # Subtotal de tamanho por mídia
        resumo=Gresumo_midia[midia]
        resumo["lista_itens"].append(item)
        resumo["lista_subpastas"].append(subpasta)
        resumo["tamanho_destino_bytes"]+=tamanho_destino_bytes




# Exibe lista de itens
# ----------------------------------------------------------------------------------------------------------------------
def exibir_lista_itens():

    # cabecalho geral
    print_linha_cabecalho()
    resumir_midia()

    # Calcula largura da última coluna, que é variável (item : Descrição)
    # A constante na subtração é a soma de todos os campos e espaços antes da última coluna
    lid = Glargura_tela - 45
    lid_formatado = "%-" + str(lid) + "." + str(lid) + "s"

    string_formatacao = '%2s %-20s %-5s %-7s ' + lid_formatado

    # Lista de itens
    q = 0
    for i in Gitens:
        q += 1

        if (q == 1):
            print(string_formatacao % ("Sq", "Item", "Mídia", "Tamanho", "Pasta"))
            print_centralizado("")

        # Subpasta
        subpasta=i["subpasta"]

        # Tamanho
        t=i.get("tamanho_destino_bytes", None)
        if t is None:
            tamanho_destino_bytes=0
            tamanho_destino_str="Indef"
        else:
            tamanho_destino_bytes=int(i["tamanho_destino_bytes"])
            tamanho_destino_str=converte_bytes_humano(tamanho_destino_bytes)

        # Mídia de destino
        midia=Gitem_midia.get(i["item"],'?')

        print(string_formatacao % (q, i["item"], midia, tamanho_destino_str, subpasta))

    # Total por mídia
    if len(Gresumo_midia)>0:
        print_centralizado()
        total_tamanho_destino_bytes = 0
        for k in sorted(Gresumo_midia):
            print("Midia ", k,"=", converte_bytes_humano(Gresumo_midia[k]["tamanho_destino_bytes"]))
            # Total de tamanho
            total_tamanho_destino_bytes += Gresumo_midia[k]["tamanho_destino_bytes"]
        if len(Gresumo_midia)>1:
            print("Tamanho total: ", converte_bytes_humano(total_tamanho_destino_bytes))

    print_centralizado()

    return




# Exibe situação das mídias
# ----------------------------------------------------------------------------------------------------------------------
def exibir_situacao():

    # Monta resumo por mídia
    resumir_midia()

    # cabecalho geral
    print_linha_cabecalho()

    # Lista de itens
    q = 0
    total_tamanho_destino_bytes = 0
    for i in sorted(Gresumo_midia):
        q += 1

        # Dados da mídia
        m=Gresumo_midia[i]

        # Sinalizador de Corrente
        espaco = "  "
        corrente = espaco
        if (q == Gicor):
            corrente = '=>'

        # Prepara dados da mídia para exibição
        t=m.get("tamanho_destino_bytes", None)
        if t is None:
            tamanho_destino_bytes=0
            tamanho_destino_str="Indef"
        else:
            tamanho_destino_bytes=int(m["tamanho_destino_bytes"])
            tamanho_destino_str=converte_bytes_humano(tamanho_destino_bytes)

        lista_itens = ", ".join(m["lista_itens"])
        pasta_memorando_destino = m.get("pasta_memorando_destino", "Indefinido")

        # Total de tamanho
        total_tamanho_destino_bytes += tamanho_destino_bytes

        # Exibe linha da mídia de destino
        string_formatacao = '%2s %-10s %-90s '
        situacao="Não iniciado"
        #print(corrente, "Mídia",i)
        print(string_formatacao % (corrente, "Mídia:", i))
        print(string_formatacao % (espaco,   "Itens:", lista_itens))
        print(string_formatacao % (espaco,   "Tamanho:", tamanho_destino_str))
        print(string_formatacao % (espaco,   "Destino:", pasta_memorando_destino))
        print(string_formatacao % (espaco,   "Situação:", situacao))
        print_centralizado("")

    # Observações gerais
    print("- Se os materiais não couberem em uma só mídia de destino, ")
    print("  utilize o comando *TM para escolher a mídia de cada item")
    print("  (Por exemplo: Itens 1, 2 e 3 na mídia 1, e itens 3 e 4 na mídia 2)")
    print("- Em seguida utilize o comando *GM para gerar a(s) mídia(s)")
    return



# Carrega situação de arquivo
# ----------------------------------------------------------------------
def carregar_estado():

    return

    # Irá atualizar as duas variáveis relacionadas com estado
    global Gitens
    global GdadosGerais

    # Por enquanto, não vamos habilitar a carga de estado
    return

    # Se estiver em ambiente de produção, não efetua o carregamento do estado
    if not ambiente_desenvolvimento():
        return

    # Não tem arquivo de estado
    if (not os.path.isfile(Garquivo_estado)):
        return

    # Le dados do arquivo e fecha
    arq_estado = open(Garquivo_estado, "r")
    estado = json.load(arq_estado)
    arq_estado.close()

    # Recupera variaveis do estado
    Gitens = estado["Gitens"]
    GdadosGerais = estado["GdadosGerais"]


# Avisa que dados vieram do estado
# print("Dados carregados do estado.sapi")
# sprint("Isto so deve acontecer em ambiente de desenvolvimento")


# Inicia procedimento de obtenção de laudo, cancelando com CTR-C
# Retorna: Verdadeiro se foi selecionado um laudo
# ----------------------------------------------------------------------------------------------------------------------
def obter_laudo_ok():
    try:
        matricula = obter_laudo_parte1()
        return obter_laudo_parte2(matricula)
    except KeyboardInterrupt:
        print()
        print("- Operação interrompida pelo usuário <CTR><C>s")
        return False


# Seleciona matricula
# ----------------------------------------------------------------------------------------------------------------------
def obter_laudo_parte1():

    print()
    print_centralizado(" Seleção de Laudo para geração de mídia")
    print("- Dica: CTR-C para cancelar seleção")
    print()

    # Solicita que o usuário se identifique através da matricula
    # Todo: Trocar identificação para login/senha (GUI)
    # ----------------------------------------------------------
    lista_laudos = list()
    while True:
        matricula = input("Entre com sua matrícula: ")
        matricula = matricula.lower().strip()

        if (matricula == ''):
            print("- Nenhuma matrícula informada. Programa finalizado.")
            sys.exit()

        if (not matricula.isdigit()):
            print("- Matrícula deve ser campo numérico (ex: 15123).")
            continue

        (sucesso, msg_erro, lista_laudos) = sapisrv_chamar_programa(
            "sapisrv_obter_laudos_pcf.php",
            {'matricula': matricula})

        # Insucesso....normalmente matricula incorreta
        if (not sucesso):
            # Continua no loop
            print("Erro: ", msg_erro)
            continue

        # Tudo certo
        return matricula


# Verifica se o laudo atende parcialmente a solicitação de exame.
# Se for parcial, solicita confirmação do usuários
def confirma_laudo_parcial():

    # Monta lista de materiais do laudo
    m_laudo=list()
    for m in Gitens:
        material=m["material"]
        m_laudo.append(material)

    # Monta lista de materiais da solicitação de exame
    m_solicitacao=dict()
    for i in Gmateriais_solicitacao:
        m=Gmateriais_solicitacao[i]
        # Se for material de destino, ignora
        if m["item"]=='destino':
            continue
        m_solicitacao[m["material"]]=m["item"]

    # Verifica se existe algum material a mais na solicitação de exame
    # que não está no laudo
    laudo_parcial=False
    for m in m_solicitacao.keys():
        if m not in m_laudo:
            print("- Item",m_solicitacao[m],"(",m,") não está vinculado a este laudo")
            laudo_parcial=True

    # Se for laudo parcial, solicita informação
    if laudo_parcial:
        print()
        print("- Este laudo NÃO COBRE todos os itens/materiais da solicitação de exame.")
        print("- Se isto não está de acordo com as suas expectativas, ")
        print("  revise o laudo no Siscrim, pois você provavelmente esqueceu de vincular os materiais examinados faltantes.")
        print("- Um laudo parcial terá em seu corpo e na mídia gerada apenas os ites/materiais vínculados ao laudo.")
        print()
        if not pergunta_sim_nao("< Continuar com laudo parcial?", default="n"):
            return False

    # Tudo certo
    return True


# Seleciona laudo
# Retorna: Verdadeiro se foi selecionado um laudo
# ----------------------------------------------------------------------------------------------------------------------
def obter_laudo_parte2(matricula):

    # Irá atualizar a variável global de itens
    global Glaudo
    global Gitens
    global Gstorages_laudo
    global GdadosGerais

    while True:

        (sucesso, msg_erro, lista_laudos) = sapisrv_chamar_programa(
            "sapisrv_obter_laudos_pcf.php",
            {'matricula': matricula})

        # Falhou...???
        if (not sucesso):
            print("- Erro: ", msg_erro)
            return False

        laudo=escolher_laudo(lista_laudos, matricula)
        if laudo is None:
            continue

        # Salva dados do laudo escolhido
        Glaudo = laudo
        GdadosGerais["codigo_laudo"] = laudo['codigo_documento_interno']
        GdadosGerais["identificacaoLaudo"] = (
            "Laudo: " +
            laudo["numero_documento"] + "/" + laudo["ano_documento"] +
            " (" +
            laudo["identificacao"] +
            " Prot: " +
            laudo["numero_protocolo"] + "/" + laudo["ano_protocolo"] +
            ")")

        GdadosGerais["codigo_solicitacao_exame_siscrim"] = laudo['codigo_documento_externo']
        GdadosGerais["identificacaoObjeto"] = GdadosGerais["identificacaoLaudo"]

        print("- Laudo selecionado:", GdadosGerais["identificacaoLaudo"])
        print()
        print("- Buscando itens associados ao laudo. Aguarde...")

        # Carrega os itens/materiais do exame
        # --------------------------------------------------------------
        codigo_solicitacao_exame_siscrim = GdadosGerais["codigo_solicitacao_exame_siscrim"]
        codigo_laudo = GdadosGerais["codigo_laudo"]
        dados = sapisrv_chamar_programa_sucesso_ok(
            programa="sapisrv_obter_itens_laudo.php",
            parametros={'codigo_solicitacao_exame_siscrim': codigo_solicitacao_exame_siscrim,
                        'codigo_laudo': codigo_laudo}
            #,registrar_log = True
        )

        # Itens e storages associados ao laudo
        Gitens = dados["itens"]
        Gstorages_laudo = dados["storages"]

        # Tem que ter ao menos um item vinculado
        if (len(Gitens) == 0):
            print()
            print("ERRO: Este laudo NÃO possui nenhum material vinculado que tenha sido processado no SAPI. Verifique no SAPI (itens processados) e no Laudo no SisCrim (materiais vinculados ao laudo).")
            print()
            continue

        # Verifica se o laudo é parcial, ou seja, se existem itens na solicitação de exame
        # que não fazem parte do laudo
        carregar_solicitacao_exame()

        # Se laudo for parcial, solicita confirmação do usuário
        print()
        if not confirma_laudo_parcial():
            continue

        # Tudo certo, interrompe o loop
        break


    # Retorna itens para o memorando selecionado
    GdadosGerais["data_hora_ultima_atualizacao_status"] = datetime.datetime.now().strftime('%H:%M:%S')

    # Muda log para o arquivo com nome
    nome_arquivo_log = "log_sapi_laudo_" + laudo["numero_documento"] + "_" + laudo["ano_documento"] + ".txt"

    # Sanitiza, removendo e trocando caracteres especiais
    nome_arquivo_log = nome_arquivo_log.replace('/', '-')
    nome_arquivo_log = nome_arquivo_log.replace(' ', '')

    renomear_arquivo_log_default(nome_arquivo_log)

    # Laudo selecionado
    return True


# Carrega dados da solicitação de exame
def carregar_solicitacao_exame():

    global Gsolicitacao_exame
    global Gmateriais_solicitacao

    print("- Carregando solicitação de exame: Aguarde...")

    codigo_solicitacao_exame_siscrim = GdadosGerais["codigo_solicitacao_exame_siscrim"]


    # Recupera dados gerais da solicitação de exame
    # ------------------------------------------------------------------
    dados = sapisrv_chamar_programa_sucesso_ok(
        programa="sapisrv_consultar_solicitacao_exame.php",
        parametros={'codigo_solicitacao_exame_siscrim': GdadosGerais["codigo_solicitacao_exame_siscrim"]},
        registrar_log=Gverbose
    )

    # Guarda na global de tarefas
    Gsolicitacao_exame = dados["solicitacao"]
    Gmateriais_solicitacao = dados["materiais"]


    #print('===============================')
    #var_dump(Gsolicitacao_exame)
    #print('===============================')
    #var_dump(Gmateriais_solicitacao)
    #die('ponto3063')

    return True



def escolher_laudo(lista_laudos, matricula):

    # Matricula ok, vamos ver se tem solicitacoes de exame
    if (len(lista_laudos) == 0):
        print()
        print("- Não existe nenhum laudo de exame SAPI para sua matrícula.")
        if pergunta_sim_nao("< Deseja criar um novo laudo"):
            criar_novo_laudo(matricula)
        else:
            return None

    # Exibe lista de laudos do usuário
    # -----------------------------------------------
    print()
    q = 0
    for d in lista_laudos:
        q += 1
        if (q == 1):
            # Cabecalho
            print('%2s  %10s %10s  %s' % ("Sq", "Laudo", "Protocolo", "Solicitação de exame"))
            print_centralizado("")
        protocolo_ano = d["numero_protocolo"] + "/" + d["ano_protocolo"]
        laudo_ano = d["numero_documento"] + "/" + d["ano_documento"]
        print('%2d  %10s %10s  %s' % (q, laudo_ano, protocolo_ano, d["identificacao"]))

    print()
    print("- Estes são os seus laudos SAPI em andamento.")
    print()

    # Usuário escolhe o laudo de interesse
    # --------------------------------------------------------
    itens = list()
    while True:
        #
        num_solicitacao = input("< Selecione o laudo (pelo número de sequencia Sq ou *NL para criar um novo): ")
        num_solicitacao = num_solicitacao.strip()

        if num_solicitacao.upper()=='*NL':
            criar_novo_laudo(matricula)
            return None

        if not num_solicitacao.isdigit():
            print("- Entre com o numero do laudo ou digite *NL para criar um novo laudo")
            continue

        # Verifica se existe na lista
        num_solicitacao = int(num_solicitacao)
        if not (1 <= num_solicitacao <= len(lista_laudos)):
            # Número não é válido
            print("- Entre com o numero do laudo, entre 1 e ", str(len(lista_laudos)))
            continue

        ix_solicitacao = int(num_solicitacao) - 1

        # Ok, selecionado
        print()
        laudo = lista_laudos[ix_solicitacao]

        return laudo


# Conduz o usuário na criação de um novo laudo para um solicitação de exame
# Retorna: True  => Usuário foi conduzido para criar laudo no SisCrim
#          False => Usuário desistiu da criação do laudo
# --------------------------------------------------------------------------
def criar_novo_laudo(matricula):

    # Solicita que o usuário se identifique através da matricula
    # ----------------------------------------------------------
    lista_solicitacoes = None

    print()
    print("- Consultando solicitações de exame SAPI no SETEC3 para matrícula",matricula,": Aguarde...")
    try:
        print_log("Recuperando solicitações de exame para matrícula: ", matricula)
        (sucesso, msg_erro, lista_solicitacoes) = sapisrv_chamar_programa(
            "sapisrv_obter_pendencias_pcf.php",
            {'matricula': matricula}
        )

        # Insucesso. Servidor retorna mensagem de erro (exemplo: matricula incorreta)
        if (not sucesso):
            # Exibe mensagem de erro reportada pelo servidor e continua no loop
            print("-",msg_erro)
            return False

    except BaseException as e:
        # Provavel falha de comunicação
        print("- Falhou comunicação com servidor: ", str(e))
        return False

    # Tem solicitações?
    if (len(lista_solicitacoes) == 0):
        print_tela_log(
            "- Não existe nenhuma solicitacao de exame com tarefas SAPI para esta matrícula. Verifique no setec3")
        return False

    # Exibe lista de solicitações de exame do usuário
    # -----------------------------------------------
    print()
    q = 0
    for d in lista_solicitacoes:
        q += 1
        if (q == 1):
            # Cabecalho
            print('%2s  %10s  %s' % ("Sq", "Protocolo", "Documento"))
            print_centralizado("-")
        protocolo_ano = d["numero_protocolo"] + "/" + d["ano_protocolo"]
        print('%2d  %10s  %s' % (q, protocolo_ano, d["identificacao"]))

    print()
    print("- Estas são as solicitações de exames SAPI.")

    # Usuário escolhe a solicitação de exame de interesse
    # --------------------------------------------------------
    tarefas = None
    while True:
        #
        print()
        num_solicitacao = input(
            "< Indique o número de sequência (Sq) da solicitação na lista acima para a qual você deseja criar laudo: ")
        num_solicitacao = num_solicitacao.strip()

        if num_solicitacao=='*s3g':
            abrir_browser_setec3_sapi()
            continue

        if not num_solicitacao.isdigit():
            print("- Entre com o número sequencial da solicitacao (coluna Sq)")
            print("- Digite *s3g para abrir a página de seus exames SAPI no SETEC3")
            print("- Digite <CTR><C> para cancelar")
            continue

        # Verifica se existe na lista
        num_solicitacao = int(num_solicitacao)
        if not (1 <= num_solicitacao <= len(lista_solicitacoes)):
            # Número não é válido
            print("Entre com o numero da solicitacao, entre 1 e ", str(len(lista_solicitacoes)))
            continue

        ix_solicitacao = int(num_solicitacao) - 1

        # Ok, selecionado
        solicitacao = lista_solicitacoes[ix_solicitacao]

        pagina_parametros = "controle_documento.php?action=elaborar&"\
                            +"objeto_pai="+solicitacao["codigo_documento_externo"]\
                            +"&categoria=2"
        abrir_browser_siscrim(pagina_parametros)
        print()
        print("- Foi aberta no browser padrão a página de criação de laudo no SisCrim")
        print("- Crie o laudo no SisCrim lembrando de associar todos os materiais citados no mesmo")
        pausa("< Após concluir cadastramento do laudo, pressione <ENTER> para prosseguir")

        # Tudo certo, retorna indicativo de que laudo está em criação
        return True


def refresh_itens():
    # Irá atualizar a variável global de itens
    global Gitens
    global Gstorages_laudo

    print("- Buscando situação atualizada do servidor. Aguarde...")

    # Carrega os materiais do exame
    # --------------------------------------------------------------
    codigo_solicitacao_exame_siscrim = GdadosGerais["codigo_solicitacao_exame_siscrim"]
    codigo_laudo = GdadosGerais["codigo_laudo"]
    dados = sapisrv_chamar_programa_sucesso_ok(
        programa="sapisrv_obter_itens_laudo.php",
        parametros={'codigo_solicitacao_exame_siscrim': codigo_solicitacao_exame_siscrim,
                    'codigo_laudo': codigo_laudo},
        registrar_log=Gverbose
    )

    # Guarda na global
    Gitens = dados["itens"]
    Gstorages_laudo = dados["storages"]

    #var_dump(Gitens)
    #var_dump(Gstorages_laudo)
    #die('ponto3029')

    GdadosGerais["data_hora_ultima_atualizacao_status"] = datetime.datetime.now().strftime('%H:%M:%S')

    return True


# Exibir informações sobre tarefa
# ----------------------------------------------------------------------
def dump_item():
    print("===============================================")

    var_dump(Gitens[Gicor])

    print("===============================================")


# Funções relacionada com movimentação nas tarefas
# ----------------------------------------------------------------------
def avancar_midia():
    global Gicor

    if (Gicor < len(Gresumo_midia)):
        Gicor += 1


def recuar_midia():
    global Gicor

    if (Gicor > 1):
        Gicor -= 1


def posicionar_midia(n):
    global Gicor

    n = int(n)

    if (1 <= n <= len(Gresumo_midia)):
        Gicor = n


def obter_midia_corrente():
    return (Gicor - 1)


# ======================================================================================================================
# @*sto - Exibe storage (pasta do memorando) invocando o File Explorer
# ======================================================================================================================

# Recupera o ÚNICO storage do exame
# Mais tarde, se o conceito de multiprocessamento for expandido para permitir que uma solicitação de exame
# seja processada em múltiplos storages, esta função não será mais necessária
def recuperar_storage_unico():
    if (len(Gstorages_laudo)==0):
        # Não deveria acontecer jamais.
        # Se laudo tem ao menos uma tarefa, tem que ter um storage
        print_tela_log("[3095] Erro inesparado: Não foi possível determinar o storage de armazenamento das tarefas do laudo")
        return None

    if (len(Gstorages_laudo)>1):
        # Não deveria acontecer jamais.
        # Se laudo tem ao menos uma tarefa, tem que ter um storage
        print_tela_log("[3103] Laudo possui tarefas armazenadas em mais de um storage. Não é possível abrir automaticamente o storage")
        return None

    # Só tem um storage
    storage= Gstorages_laudo[0]

    return storage


def exibir_storage_file_explorer():

    print()
    print("- Exibir pasta do memorando no storage")
    print()

    storage=recuperar_storage_unico()
    if storage is None:
        # Mensagens de erro já foram fornecidas
        return

    print("- Storage do memorando: ", storage["maquina_netbios"])

    # Montagem de storage
    # -------------------
    ponto_montagem = conectar_storage_consulta_ok(storage)
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return

    # Determina a pasta do memorando
    pasta = montar_caminho(
        ponto_montagem,
        Gsolicitacao_exame["pasta_memorando"])
    print("- Pasta do exame:")
    print("  ", pasta)
    if not os.path.exists(pasta):
        print("- Não foi encontrando pasta para memorando no storage")
        print("- Comando cancelado")
        return

    # Abre pasta no File Explorers
    print("- Abrindo file explorer na pasta selecionada")
    os.startfile(pasta)
    print("- Pasta foi aberta no file explorer")

# ----------------------------------------------------------------------------------------------------------------------
# Exibe conteúdo do arquivo de log
# ----------------------------------------------------------------------------------------------------------------------
def exibir_log(comando, filtro_base="", filtro_usuario="", limpar_tela=True):

    # Filtros
    filtro_base     =filtro_base.strip()
    filtro_usuario  =filtro_usuario.strip()

    # Limpa tela e imprime cabeçalho do programa
    # --------------------------------------------------------------------------------
    if limpar_tela:
        cls()
        print_linha_cabecalho()
        print("Arquivo de log: ", obter_nome_arquivo_log())

    print_centralizado()

    if filtro_usuario!= "":
       print("Contendo termo: ", filtro_usuario)
       print_centralizado()

    arquivo_log = obter_nome_arquivo_log()

    # Não tem arquivo de log
    if (not os.path.isfile(arquivo_log)):
        print("*** Arquivo de log vazio ***")
        return

    with codecs.open(arquivo_log, 'r', "utf-8") as sapi_log:
        qtd=0
        for linha in sapi_log:
            exibir=True
            if filtro_base!="" and filtro_base.lower() not in linha.lower():
                exibir=False
            if filtro_usuario!="" and filtro_usuario.lower() not in linha.lower():
                exibir=False

            if exibir:
                qtd=qtd+1
                print(format(qtd, '03d'),":", linha.strip())

    sapi_log.close()

    if qtd==0:
        print("*** Nenhuma mensagem de log disponível ***")
        return


    if filtro_usuario=="":
        print()
        print("- Dica: Para filtrar o log, forneça um string após comando.")
        print("  Exemplo: ",comando," erro => Lista apenas linhas que contém o termo 'erro'")

    return


# Retorna True se realmente pode e deve ser finalizado
def finalizar_programa():

    print()
    # Varre lista de processos filhos, e indica o que está rodando
    qtd_ativos = 0
    for ix in sorted(Gpfilhos):
        if Gpfilhos[ix].is_alive():
            dummy, codigo_tarefa = ix.split(':')
            print("- Processo", ix,"ainda está executando (",ix,Gpfilhos[ix].pid,")")
            qtd_ativos += 1

    # Se não tem nenhum programa em background
    # pode finalizar imediatamente
    if qtd_ativos == 0:
        return True

    # Pede confirmação, se realmente deve finalizar processos em background
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("- Se você finalizar o programa agora, o que está sendo executado será perdido e terá de ser reiniciado.")
    print()
    prosseguir_finalizar = pergunta_sim_nao("< Deseja realmente finalizar programa? ", default="n")
    if not prosseguir_finalizar:
        # Não finaliza
        return False


    # Eliminando processos filhos que ainda estão ativos
    # --------------------------------------------------------------------------------------------------------------
    print_log("Usuário foi avisado que existem processos rodando, e respondeu que desejava encerrar mesmo assim")
    print("- Finalizando processos. Aguarde...")
    for ix in sorted(Gpfilhos):
        if Gpfilhos[ix].is_alive():
            # Finaliza processo
            print_log("Finalizando processo ", ix, " [", Gpfilhos[ix].pid, "]")
            Gpfilhos[ix].terminate()


    # Para garantir, aguarda caso ainda tenha algum processo não finalizado...NÃO DEVERIA ACONTECER NUNCA
    # --------------------------------------------------------------------------------------------------------------
    repeticoes=0
    while True:
        # Uma pequena pausa para dar tempo dos processos finalizarem
        lista = multiprocessing.active_children()
        qtd = len(lista)
        if qtd == 0:
            # Tudo certo
            print_log("Todos os processos filhos foram eliminados")
            break
        repeticoes=repeticoes+1
        if repeticoes>5:
            print_tela_log("Aguardando encerramento de", len(lista),
                       " processo. Situação incomum. Se demorar excessivamente, comunique desenvolvedor.")
        # Aguarda e repete, até finalizar tudo...isto não deveria acontecer....
        time.sleep(2)

    # Tudo certo, finalizar
    return True




# ======================================================================
# Código para teste
# ======================================================================

'''
lista=dict()
lista["2"]=5
lista["1"]=12
lista["3"]=25
lista["17"]=28
lista["0"]=15
for k in sorted(lista):
    print(k, lista[k])
#var_dump(lista)
die('ponto3769')
'''

'''
d={}
d['chave1']=10
d['chave2']=['abc','def']
d['chave3']={'c31': 12.5, 'c32': ['xyz', 'def']}

d_json=json.dumps(d,sort_keys=True)
print(d_json)

die('ponto2031')
'''

'''
import pyperclip # The name you have the file
x = pyperclip.paste()
print(x)
'''

'''
start_time=time.time()
time.sleep(5)
tempo=time.time()-start_time

print("tempo = ", tempo)
#print("tempo = ", str(tempo))
die('ponto1345')
var_dump(tempo)
'''

'''
pasta='c:/tempr'
tamanho=tamanho_pasta(pasta)
print(pasta,tamanho, converte_bytes_humano(tamanho))

pasta='c:/teste_iped'
tamanho=tamanho_pasta(pasta)
print(pasta,tamanho, converte_bytes_humano(tamanho))

die('ponto1174')

'''

# ======================================================================
# Rotina Principal
# ======================================================================

def main():
    # Cabeçalho inicial do programa
    # ------------------------------------------------------------------------------------------------------------------
    print()
    cls()
    print(Gprograma, "Versão", Gversao)
    print_centralizado("-")
    print()
    print("Dicas:")
    print("- Este programa foi projetado para utilizar uma janela com largura mínima de 130 caracteres.")
    print("- Se a linha de separador ---- está sendo dívida/quebrada,")
    print("  configure o buffer de tela e tamanho de janela com largura mínima de 130 caracteres.")
    print("- Recomenda-se também trabalhar com a janela na altura máxima disponível do monitor.")
    print()
    print("- Aguarde conexão com servidor...")
    print()

    # Inicialização de sapilib
    # -----------------------------------------------------------------------------------------------------------------
    print_log('Iniciando ', Gprograma, ' - ', Gversao)
    sapisrv_inicializar_ok(Gprograma, Gversao, auto_atualizar=True)

    # Carrega a lista de itens do laudo selecionado pelo usuário
    # -----------------------------------------------------------------------------------------------------------------
    if not obter_laudo_ok():
        # Se usuário interromper seleção de itens
        print("- Execução finalizada.")
        return

    # Processamento
    # ---------------------------
    exibir_situacao()

    # Recebe comandos
    while (True):
        (comando, argumento) = console_receber_comando(Gmenu_comandos)

        if comando is None:
            continue

        if comando == '':
            # Se usuário simplemeste der um <ENTER>, exibe a situação
            exibir_situacao()
            continue

        if (comando == '*qq'):
            # Finaliza programa, mas antes verifica se tem algo rodando em background
            if finalizar_programa():
                # Finaliza
                print()
                print("- Finalizando por solicitação do usuário. Aguarde...")
                print_log("Finalizado por comando de usuário (*qq)")
                break
            else:
                # Continua recebendo comandos
                continue


        # Executa os comandos
        # -----------------------

        # Comandos de navegação
        if (comando.isdigit()):
            posicionar_midia(comando)
            exibir_situacao()
        elif (comando == '+'):
            avancar_midia()
            exibir_situacao()
        elif (comando == '-'):
            recuar_midia()
            exibir_situacao()
        elif (comando == "*ir"):
            posicionar_midia(argumento)
            exibir_situacao()

        # Comandos de item
        if (comando == '*du'):
            dump_item()
            continue
        elif (comando == '*si'):
            exibir_situacao_item_corrente()
            continue
        elif (comando == '*tm'):
            trocar_midia()
            exibir_situacao()
            continue

        # Comandos gerais
        if (comando == '*sg'):
            refresh_itens()
            exibir_situacao()
            continue
        elif (comando == '*lg'):
            exibir_log(comando='*lg', filtro_base='', filtro_usuario=argumento)
            continue
        elif (comando == '*tt'):
            obter_laudo_ok()
            #salvar_estado()
            exibir_situacao()
            continue
        elif (comando == '*db'):
            if modo_debug():
                desligar_modo_debug()
                print("- Modo debug foi desligado")
            else:
                ligar_modo_debug()
                print("- Modo debug foi ligado")
            continue
        elif (comando == '*s3'):
            abrir_browser_setec3_exame(GdadosGerais["codigo_solicitacao_exame_siscrim"])
            continue
        elif (comando == '*s3g'):
            abrir_browser_setec3_sapi()
            continue
        elif (comando == '*sto'):
            exibir_storage_file_explorer()
            continue
        elif (comando == '*gm'):
            gerar_midia_destino()
            continue
        elif (comando == '*cl'):
            abrir_browser_siscrim_documento(GdadosGerais["codigo_laudo"])
            continue

            # Loop de comando

    # Finaliza programa
    # Encerrando conexão com storage
    print()
    desconectar_todos_storages()

    # Finaliza
    print()
    print("FIM ",Gprograma,"- Versão: ", Gversao)

if __name__ == '__main__':

    main()

    print()
    espera_enter("Programa finalizado. Pressione <ENTER> para fechar janela.")

