# -*- coding: utf-8 -*-
#
# ===== PYTHON 3 ======
#
# =======================================================================
# SAPI - Sistema de Apoio a Procedimentos de Informática
# 
# Componente: sapi_cellebrite
# Objetivo: Agente para tratamento de extração de dados do cellebrite
# Funcionalidades:
#  - Conexão com o servidor SAPI para obter lista de tarefas
#    de imagem e reportar situação de execução das imagens
#  - Criação de pasta para aramazenamento da extração no storage
#  - Validação dos dados do Cellebrite
#  - Cópia para pasta do storage
#  - Atualização do servidor da situação da tarefa
# Histórico:
#  - v1.0 : Inicial
#  - v1.7: Ajuste para versão de sapilib_0_7_1 que trata https
#  - v1.8: Ajustes para sapilib (controle de timeout e retentativas)
#          Diversas pequenas melhorias no funcionamento do programa (ver release.txt)
# ======================================================================================================================
# Todo:
# - Se memorando já foi concluido, desprezar o que está em cache (caso contrário da erro)
#
# TODO: Como garantir que a cópia foi efetuada com sucesso? Hashes?
# TODO: XML está quase do tamanho do PDF (em alguns casos, fica bem grande).
#       Criar opção para excluir do destino? Excluir sempre?
# TODO: Reportar ao servidor a versão do programa quando for solicitar tarefas. Se a versão não for mais suportada,
#       servidor deve negar fornecer tarefas para o agente
# TODO: Quando agente atualizar status, reportar o nome do programa e versão (ajustar servidor antes para armazenar)
# ======================================================================================================================

# Módulos utilizados
# ====================================================================================================
from __future__ import print_function
import platform
import sys
import time
import xml.etree.ElementTree as ElementTree
import shutil
import tempfile
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
Gprograma = "sapi_cellebrite"
Gversao = "1.8.1"

# Para gravação de estado
Garquivo_estado = Gprograma + "v" + Gversao.replace('.', '_') + ".sapi"

# Base de dados (globais)
GdadosGerais = dict()  # Dicionário com dados gerais
Gtarefas = list()  # Lista de tarefas

# Diversos sem persistência
Gicor = 1
Glargura_tela = 129

# Controle de frequencia de atualizacao
GtempoEntreAtualizacoesStatus = 180  # Tempo normal de produção
# GtempoEntreAtualizacoesStatus = 10  # Debug: Gerar bastante log

# ------- Definição de comandos aceitos --------------
Gmenu_comandos = dict()
Gmenu_comandos['comandos'] = {
    # Comandos de navegação
    '+': 'Navega para a tarefa seguinte da lista',
    '-': 'Navega para a tarefa anterior da lista',
    '*ir': 'Posiciona na tarefa com sequencial(Sq) indicado (ex: *ir 4, pula para o quarto item da lista).' +
           '\nPara simplificar, pode-se digitar apenas o sequencial (ex: 4)',

    # Comandos relacionados com um item
    '*cr': 'Verifica a pasta de relatórios do Cellebrite no computador local e em seguida copia para o storage',
    '*at': 'Aborta da tarefa',
    '*si': 'Compara a situação da tarefa (no SETEC3) com a situação observada no storage',
    '*du': 'Dump: Mostra todas as propriedades de uma tarefa (utilizado para Debug)',

    # Comandos gerais
    '*sg': 'Efetua Refresh da situação das tarefas. ',
    '*tt': 'Troca memorando',
    '*qq': 'Finaliza',

    # Comandos para diagnóstico de problemas
    '*el': 'Exibe log desta instância do sapi_cellebrite (para ver outros logs, verifique arquivos diretamente na pasta). ',
    '*dg': 'Liga/desliga modo debug. Este modo incluí mensagens adicionais no log visando facilitar o diagnóstico de problemas'

}

Gmenu_comandos['cmd_navegacao'] = ["+", "-", "*ir"]
Gmenu_comandos['cmd_item'] = ["*cr", "*si", "*at"]
Gmenu_comandos['cmd_geral'] = ["*sg", "*tt", "*qq"]
Gmenu_comandos['cmd_diagnostico'] = ["*el", "*dg"]

# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi_lib_xxx.py, para evitar dependência
from sapilib_0_8 import *

# **********************************************************************
# PRODUCAO 
# **********************************************************************


# ======================================================================
# Funções Auxiliares específicas deste programa
# ======================================================================


# ======================================================================
# Funções Auxiliares específicas deste programa
# ======================================================================

# ======================================================================
# Funções Auxiliares com janelas (Tkinter) - Para  W I N D O W S
# Posteriormente jogar isto aqui para um módulo também
# Como foi feito para o sapi
# ======================================================================

# Interface gráfica (tk)
# from tkinter import Tk
import tkinter
from tkinter import filedialog


class Janela(tkinter.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.pack()

    def selecionar_arquivo(self):
        self.file_name = tkinter.filedialog.askopenfilename(filetypes=([('All files', '*.*'),
                                                                        ('ODT files', '*.odt'),
                                                                        ('CSV files', '*.csv')]))
        return self.file_name

    def selecionar_pasta(self):
        directory = tkinter.filedialog.askdirectory()
        return directory


# Recupera os componentes da tarefa correntes e retorna em tupla
# ----------------------------------------------------------------------
def obter_tarefa_item_corrente():
    x = Gtarefas[Gicor - 1]
    return (x.get("tarefa"), x.get("item"))


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


# Atualiza status da tarefa do sapisrv
# def atualizar_status_tarefa_deprecated(codigo_tarefa, codigo_situacao_tarefa, status, dados_relevantes=None):
#     # Define nome do agente
#     # xxxx@yyyy, onde xxx é o nome do programa e yyyy é o hostname
#     nome_agente = socket.gethostbyaddr(socket.gethostname())[0]
#
#     # Parâmetros
#     param = {'codigo_tarefa': codigo_tarefa,
#              'codigo_situacao_tarefa': codigo_situacao_tarefa,
#              'status': status,
#              'execucao_nome_agente': nome_agente
#              }
#     if (dados_relevantes is not None):
#         dados_relevantes_json = json.dumps(dados_relevantes, sort_keys=True)
#         param['dados_relevantes_json'] = dados_relevantes_json
#
#     # Invoca sapi_srv
#     (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
#         "sapisrv_atualizar_tarefa.php", param)
#
#     # Retorna resultado
#     if (sucesso):
#         return (True, '')
#     else:
#         return (False, msg_erro)


# Atualiza status da tarefa em andamento
# Não efetua verificação de erro, afinal este status é apenas informativo
def atualizar_status_tarefa_andamento(codigo_tarefa, texto_status):
    codigo_situacao_tarefa = GEmAndamento
    print_log("Tarefa ", codigo_tarefa, "=> atualizado status: ", texto_status)
    (ok, msg_erro) = sapisrv_atualizar_status_tarefa(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=codigo_situacao_tarefa,
        status=texto_status
    )

    # Se ocorrer algum erro, registra apenas no log, e ignora
    # Afinal, o status em andamento é apenas informativo
    if not ok:
        print_log("Atualização de status em andmento para tarefa (" + codigo_tarefa + ") falhou: " + msg_erro)

    return


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
    pasta = "/".join(partes)

    return (pasta, nome_arquivo)


# Processa arquivo XML, retornando erros e avisos
# resultado: Sucesso (true) ou fracasso (false)
# dados_relevantes: Dados para laudo
# erros: Lista de erros
# avisos: Lista de avisos
# ----------------------------------------------------------------------
def processar_arquivo_xml(arquivo, numero_item, explicar=True):
    # Cria um arquivo temporario para armazenar a versão sintética do arquivo XML
    arquivo_temporario = tempfile.NamedTemporaryFile(delete=False)
    caminho_arquivo_temporario = arquivo_temporario.name
    arquivo_temporario.close()

    # Sintetiza arquivo recebido, armazenando no arquivo temporário
    sintetizar_arquivo_xml(arquivo, caminho_arquivo_temporario)

    # Efetua a validação do arquivo temporário
    (resultado, dados_relevantes, erros, avisos) = validar_arquivo_xml(caminho_arquivo_temporario, numero_item,
                                                                       explicar)

    # Elimina arquivo temporário, pois não é mais necessário
    os.unlink(caminho_arquivo_temporario)

    # Retorna resultado
    return (resultado, dados_relevantes, erros, avisos)


# Dependendo do caso, o arquivo XML é muito grande
# Nesta situação, o parse completo fica muito lento e em alguns casos acaba a memória.
# Logo, extrai apenas as partes relevantes do arquivo
def sintetizar_arquivo_xml(arquivo, caminho_arquivo_temporario):
    # Criar arquivo de saída e copia inicio do arquivo XML
    # -----------------------------------------------------
    with codecs.open(caminho_arquivo_temporario, 'w+b', encoding='utf-8') as ftemp:
        with codecs.open(arquivo, "r", "utf-8") as fentrada:
            for linha in fentrada:
                # Interrompe a cópia quando encontrar um dos elementos da lista abaixo
                irrelevantes = ["<images", "<taggedFiles", "<decodedData", "<carvedFiles", "<infectedFiles"]
                encontrou = False
                for termo in irrelevantes:
                    if termo in linha: encontrou = True

                if encontrou:
                    ftemp.write("")
                    break

                # Grava linha na saída
                ftemp.write(linha)

    # Extrai as linhas de bloco de modelType relevantes
    # -------------------------------------------------
    # <modelType type="SIMData">
    # ...
    # </modelType>

    # Lista de seções modelType que contém informações úteis
    # <modelType type="UserAccount">    # Contas de usuário
    # <modelType type="SIMData">        # Dados do simCard, incluindo MSISDN
    lista_model_type = ['<modelType type="UserAccount">', '<modelType type="SIMData">']

    with codecs.open(caminho_arquivo_temporario, 'a+b', encoding='utf-8') as ftemp:
        with codecs.open(arquivo, "r", "utf-8") as fentrada:
            iniciado = False
            for linha in fentrada:

                if not iniciado:
                    for mt in lista_model_type:
                        if mt in linha:
                            iniciado = True

                if iniciado:
                    # Grava linha linha
                    ftemp.write(linha)

                if iniciado and '</modelType>' in linha:
                    ftemp.write("")
                    iniciado = False

    # Encerra XML
    with codecs.open(caminho_arquivo_temporario, 'a+b', encoding='utf-8') as ftemp:
        ftemp.write("</project>")

    print_log("Arquivo XML sintetizado gravado em ", caminho_arquivo_temporario)

    return


# Validar arquivo XML do cellebrite
# ----------------------------------------------------------------------
def validar_arquivo_xml(caminho_arquivo, numero_item, explicar=True):
    # Dados para retorno
    # ------------------------------------------------------------------
    dados = {}

    erros = list()
    avisos = list()

    # mensagens=[]

    # Armazenamento de dados de resultado
    dext = {}  # Dicionário com dados de cada extração

    # Indice do componente
    quantidade_componentes = 0

    # dicionários para montagem de dados para laudo
    d_aquis_geral = {}  # Dados gerais da aquisição

    # Abre arquivo XML sintetico e faz parse
    # ------------------------------------------------------------------
    tree = ElementTree.parse(caminho_arquivo)
    root = tree.getroot()

    # ------------------------------------------------------------------
    # Valida cabeçalho do XML
    # XML tem que começar por
    # <?xml version="1.0" encoding="utf-8"?>
    # <project id="6867effe-489a-4ece-8fc7-c1e3bb644efc" name="Item 11" reportVersion="5.2.0.0" licenseID="721705392"
    # containsGarbage="False" extractionType="FileSystem" xmlns="http://pa.cellebrite.com/report/2.0">
    # ------------------------------------------------------------------
    # A raiz tem que ser <project>
    if ('project' not in root.tag):
        mensagem = ("XML com raiz inesperada: '" + root.tag + "'. Deveria iniciar por <project ...>")
        erros += [mensagem]
        if_print_ok(explicar, mensagem)
        return (False, dados, erros, avisos)

    # Extrai componente fixo do tag (namespace), removendo a constante "project"
    # O tag da raiz é algo como
    # {http://pa.cellebrite.com/report/2.0}project
    # O componente fixo (namespace) é o que está entre colchetes
    ns = root.tag.replace('project', '')

    # Verifica atributos do projeto
    # ------------------------------------------------------------------
    a = root.attrib

    # 'containsGarbage': 'False',
    # 'extractionType': 'FileSystem',
    # 'id': '6867effe-489a-4ece-8fc7-c1e3bb644efc',
    # 'licenseID': '721705392',
    # 'name': 'Item 11',
    # 'reportVersion': '5.2.0.0'

    # Versão do relatório
    report_version = a.get('reportVersion', None)
    if report_version not in ['5.2.0.0']:
        # Apenas um aviso. Continua
        mensagem = ("Relatório com esta versão (" +
                    report_version +
                    ") não foi testada com este validador. Pode haver incompatibilidade.")
        avisos += [mensagem]
        if_print_ok(explicar, "#", mensagem)
    d_aquis_geral['reportVersion'] = report_version


    # # Nome do projeto
    name = a.get('name', None)
    d_aquis_geral['project_name'] = name

    # Acho que isto aqui não está ajudando muito.
    # Talvez reativar mais tarde
    # if (numero_item not in name):
    #     # Se o nome do projeto está fora do padrão, emite apenas um aviso
    #     mensagem = ("Nome do projeto (" + name + ") não contém referência ao item de exame. "
    #                 + "\nPara tornar o relatório mais claro para o usuário, recomenda-se que o nome do projeto contenha no seu nome o item de apreensão, "
    #                 + "algo como: 'Item" + numero_item + "'")
    #     avisos += [mensagem]
    #     if_print_ok(explicar, "#", mensagem)

    # ------------------------------------------------------------------
    # Valida extrações
    # O nome da extração identifica a sua natureza
    # Apenas alguns nomes são válidos
    # ------------------------------------------------------------------
    # <extractionInfo id="0" name="Aparelho - Lógica" isCustomName="True" type="Logical" deviceName="Report"
    #   fullName="Cellebrite UFED Reports" index="0" IsPartialData="False" />
    # <extractionInfo id="1" name="Aparelho - Sistema de arquivos (Downgrade)" isCustomName="True" type="FileSystem" 
    #   deviceName="SAMG531F" fullName="Samsung SM-G531F Galaxy Grand Prime" index="1" IsPartialData="False" />
    # <extractionInfo id="2" name="Cartão SIM 2" isCustomName="True" type="Logical" deviceName="Report"
    #   fullName="Cellebrite UFED Reports" index="2" IsPartialData="False" />
    # <extractionInfo id="3" name="Cartão SIM 1" isCustomName="True" type="Logical" deviceName="Report"
    #   fullName="Cellebrite UFED Reports" index="3" IsPartialData="False" />

    # Valida cada extração
    # ------------------------------------------------------------------
    for extractionInfo in root.iter(tag=ns + 'extractionInfo'):
        id_extracao = extractionInfo.get('id', None)
        dext[id_extracao] = {}

        nome_extracao = extractionInfo.get('name', None)
        dext[id_extracao]['extractionInfo_name'] = nome_extracao
        dext[id_extracao]['extractionInfo_type'] = extractionInfo.get('type', None)
        dext[id_extracao]['extractionInfo_IsPartialData'] = extractionInfo.get('IsPartialData', None)

    # ------------------------------------------------------------------
    # Informações adicionais
    # ------------------------------------------------------------------
    '''
    <metadata section="Additional Fields">
     <item name="DeviceInfoCreationTime"><![CDATA[14/09/2016 18:31:44]]></item>
     <item name="UFED_PA_Version"><![CDATA[5.2.0.213]]></item>
    </metadata>
    '''

    # Busca versão do physical Analyzer
    # Por enquanto, não está utilizando isto
    p = ns + "metadata/" + ns + "item" + "[@name='UFED_PA_Version']"
    ufed_pa_version = None
    if (root.find(p) is not None):
        ufed_pa_version = root.find(p).text

    # ------------------------------------------------------------------
    # Dados das extrações
    # ------------------------------------------------------------------

    # <metadata section="Extraction Data">
    #   <item name="DeviceInfoExtractionStartDateTime" sourceExtraction="1">
    #       <![CDATA[14/09/2016 16:49:42(UTC-3)]]></item>
    #   <item name="DeviceInfoExtractionEndDateTime" sourceExtraction="1"><![CDATA[14/09/2016 17:32:15(UTC-3)]]></item>
    #   <item name="DeviceInfoUnitIdentifier" sourceExtraction="1"><![CDATA[UFED S/N 5933940]]></item>
    #   <item name="DeviceInfoUnitVersion" sourceExtraction="1"><![CDATA[5.2.0.689]]></item>
    #   <item name="DeviceInfoInternalVersion" sourceExtraction="1"><![CDATA[4.3.8.689]]></item>
    #   <item name="DeviceInfoSelectedManufacturer" sourceExtraction="1"><![CDATA[Samsung GSM]]></item>
    #   ... continua

    # Localiza a seção <metadata section="Extraction Data">
    p = ns + 'metadata' + '[@section="Extraction Data"]'
    secao = root.find(p)
    # print(secao)
    for item in secao:
        # Armazena todos os valores
        name = item.get('name', None)
        source_extraction = item.get('sourceExtraction', None)
        if (source_extraction is None):
            # Tem que ser associado a alguma extração
            continue

        valor = item.text
        # print('name=',name,' sourceExtraction = ',sourceExtraction, " valor=",valor)
        if (source_extraction is not None):
            if (source_extraction not in dext):
                dext[source_extraction] = {}
            dext[source_extraction][name] = valor

    # Infere o tipo de componente baseado no fabricante DeviceInfoSelectedManufacturer
    # Todo: Melhorar esta inferência de componente. Tem que ver o backup...mais alguma coisa que o cellebrite processa?
    # SIM Card => Sim Card
    # Por enquantoMass Storage Device => SD
    # ??backup??
    # Qualquer outra coisa => Aparelho
    qtd_extracao_aparelho = 0
    qtd_extracao_sim = 0
    qtd_extracao_sd = 0
    qtd_extracao_backup = 0

    for id_extracao in dext:
        tipo = None
        for n in dext[id_extracao]:
            if n == 'DeviceInfoSelectedManufacturer':
                v = dext[id_extracao][n]
                if v == 'SIM Card':
                    qtd_extracao_sim += 1
                    tipo = 'sapiSIM'
                elif v == 'Mass Storage Device':
                    qtd_extracao_sd += 1
                    tipo = 'sapiSD'
                elif v == 'backup????':  # Todo: Como identificar o backup
                    qtd_extracao_backup += 1
                    tipo = 'sapiBackup'
                else:
                    qtd_extracao_aparelho += 1
                    tipo = 'sapiAparelho'

        dext[id_extracao][tipo] = True

    # Verifica conjunto de extrações
    # ------------------------------------------------------------------

    # Se tem algum erro na seção de extração, não tem como prosseguir.
    # if len(erros) > 0:
    #    return (False, dados, erros, avisos)

    # Verifica quantidade de extrações e emite avisos para situações incomuns
    if (qtd_extracao_aparelho == 0):
        mensagem = ("Não foi encontrada nenhuma extração com nome contendo a palavra 'Aparelho'." +
                    " O material não tem aparelho? Assegure-se que está correto.")
        avisos += [mensagem]
        if_print_ok(explicar, "#", mensagem)

    if (qtd_extracao_sim == 0):
        mensagem = ("Não foi encontrada nenhuma extração com nome contendo a palavra 'SIM'." +
                    "Realmente não tem SIM Card?. Assegure-se que isto está correto.")
        avisos += [mensagem]
        if_print_ok(explicar, "#", mensagem)

    if (qtd_extracao_sd > 0):
        mensagem = ("Sistema ainda não é capaz de inserir dados do cartão automaticamente no laudo.")
        avisos += [mensagem]
        if_print_ok(explicar, "#", mensagem)

    if (qtd_extracao_backup > 0):
        mensagem = (
            "Sistema ainda não preparado para tratar relatório de processamento de Backup. Consulte desenvolvedor.")
        avisos += [mensagem]
        if_print_ok(explicar, "#", mensagem)

    # ------------------------------------------------------------------
    # Informações sobre os dispositivos
    # Na realidade, também tem relação com as extração
    # Não sei porque foi separado em duas seçoes.
    # ------------------------------------------------------------------
    # <metadata section="Device Info">
    #     <item id="42f3c65b-d20f-4b60-949c-d77e92da93bb" name="DeviceInfoAndroidID" sourceExtraction="1">
    #       <![CDATA[ec4c58699c0e4f1e]]></item>
    #     <item id="53b63a05-927a-4c2c-b415-3e3811b90290" name="DeviceInfoAndroidID" sourceExtraction="0">
    #       <![CDATA[ec4c58699c0e4f1e]]></item>
    #     <item id="432da4c4-e060-4134-804c-f0cd0ee80a81" name="DeviceInfoDetectedManufacturer" sourceExtraction="0">
    #       <![CDATA[samsung]]></item>
    #     <item id="fdff5848-2077-42f6-a488-8f743233266a" name="DeviceInfoDetectedModel" sourceExtraction="0">
    #       <![CDATA[SM-G531BT]]></item>
    #     <item id="28bfe23c-861f-4ab4-836a-aebbf9b51ef2" name="DeviceInfoRevision" sourceExtraction="0">
    #       <![CDATA[5.1.1 LMY48B G531BTVJU0AOL1]]></item>

    # Localiza a seção <metadata section="Device Info">
    p = ns + 'metadata' + '[@section="Device Info"]'
    secao = root.find(p)
    # print(secao)
    for item in secao:
        name = item.get('name', None)
        source_extraction = item.get('sourceExtraction', None)
        valor = item.text
        # print('name=',name,' sourceExtraction = ',sourceExtraction, " valor=",valor)
        if (source_extraction is not None):
            if (source_extraction not in dext):
                dext[source_extraction] = {}
            dext[source_extraction][name] = valor

    # ------------------------------------------------------------------
    # Recupera dados ds Seção ModelType SIMDATA
    # <modelType type = "SIMData">
    #  <model
    #     type = "SIMData"
    #     id = "fe5bdfe1-2e9c-47de-a9b5-3ec3d418446e"
    #     deleted_state = "Intact"
    #     decoding_confidence = "High"
    #     isrelated = "False"
    #     extractionId = "1">
    #
    #     <field name = "Name" type = "String">
    #     <value type = "String" > <![CDATA[MSISDN 1]] > </value>
    #     </field >
    #     <field name = "Value" type = "String" >
    #     < value type = "String" > <![CDATA[99192334]] > </value>
    #     </field>
    #     <field name = "Category" type = "String" >
    #     <value type = "String" > <![CDATA[SIM / USIM MSISDN]] > </value>
    #     </field >
    # </model>
    #
    # ------------------------------------------------------------------

    # <model type="SIMData" id="fe5bdfe1-2e9c-47de-a9b5-3ec3d418446e" deleted_state="Intact"
    # decoding_confidence="High" isrelated="False" extractionId="1">
    p = ns + 'modelType' + '[@type="SIMData"]'
    model_type = root.find(p)
    if model_type is not None:
        # Processa dados de tags localizados
        for model in model_type:
            # var_dump(model)
            # die('ponto645')

            # Armazena todos os valores
            extraction_id = model.get('extractionId', None)
            if (extraction_id is None):
                # Tem que ser associado a alguma extração
                continue

            m = dict()
            # Existe três fields. Utilizamos aqui apenas o Name e o Value
            # Cada um tem o seu valor na seção subordinada value
            # <field name="Name" type="String">
            # <field name="Value" type="String">
            # <field name="Category" type="String">
            for field in model:
                # var_dump(field)
                nome = field.get('name', None)

                # <value type="String"><![CDATA[MSISDN 1]]></value>
                # <value type="String"><![CDATA[99192334]]></value>
                for value in field:
                    valor = value.text
                    m[nome] = valor

                    # print("nome=", nome)
                    # print("valor=", valor)
                    # die('ponto643')

            # Se for MSIDN, e contiver algo válido, armazena
            if 'MSISDN' in m['Name'] and m['Value'] != 'N/A':
                dext[extraction_id]['MSISDN'] = m['Value']

    # Recupera dados da seção "UserAccount"
    # -----------------------------------------------------------------------------------------------------------------
    # <modelType type="UserAccount">
    #  <model type="UserAccount" id="0d350d00-e2a7-42f4-9bfb-e964f1dd3a9c" deleted_state="Intact"
    #          decoding_confidence="High" isrelated="False" extractionId="4">
    #    <field name="Name" type="String">
    #      <value type="String"><![CDATA[luizca1992]]></value>
    #    </field>
    #    <field name="Username" type="String">
    #      <value type="String"><![CDATA[554599192334@s.whatsapp.net]]></value>
    #    </field>
    #    <field name="Password" type="String">
    #      <empty />
    #    </field>
    #    <field name="ServiceType" type="String">
    #      <value type="String"><![CDATA[WhatsApp]]></value>
    #    </field>
    #    <field name="ServerAddress" type="String">
    #      <empty />
    #    </field>
    # -----------------------------------------------------------------------------------------------------------------
    p = ns + 'modelType' + '[@type="UserAccount"]'
    model_type = root.find(p)
    usernames_conhecidos = list()
    if model_type is not None:
        # Processa informações de conta
        for model in model_type:
            # var_dump(model)
            if model.get('type', None) != 'UserAccount':
                # Despreza, se não for userAccount...tem fotos e outras coisas aqui também....
                # Quem sabe no futuro, colocar a foto associada ao perfil.
                continue

            # Armazena todos os valores
            extraction_id = model.get('extractionId', None)
            if (extraction_id is None):
                # Tem que ser associado a alguma extração
                continue

            # Recupera os valores
            m = dict()
            for field in model:
                if '}field' not in field.tag:
                    # Tem outros tags aqui, como <multiModelField
                    continue
                nome = field.get('name', None)

                for value in field:
                    valor = value.text
                    m[nome] = valor

            # Exemplo de dados extraídos
            # 'Name': 'luizca1992',
            # 'Password': None,
            # 'ServerAddress': None,
            # 'ServiceType': 'WhatsApp',
            # 'TimeCreated': None,
            # 'Username': '554599192334@s.whatsapp.net'}

            # Se for MSIDN, e contiver algo válido, armazena
            # Campos relevantes
            lista_relevantes = ['Name', 'Username', 'ServiceType']
            lista_partes_conta = list()
            for campo in lista_relevantes:
                if m.get(campo, None) is not None:
                    lista_partes_conta.append(m[campo])

            conta_formatada = "/".join(lista_partes_conta)

            # Despreza algumas contas inúteis
            desprezar_conta = False
            lista_inuteis = ["primary.sim", "vnd.sec.contact", "recarga.tim"]
            for inutil in lista_inuteis:
                if inutil in conta_formatada:
                    desprezar_conta = True
            if desprezar_conta:
                continue

            # Se o username for repetido (mesma conta de email), ignora
            # Normalmente ocorre de diversos serviços do google compartilharem a mesma conta
            # Isto gera uma lista muito extensa e sem utilidade
            # TODO: O melhor seria apresentar a conta com todos os serviços associados...se for necessário
            user_name = m.get('Username', None)
            if user_name is not None:
                if user_name in usernames_conhecidos:
                    continue
                usernames_conhecidos.append(user_name)

            # var_dump(conta_formatada)
            # var_dump(lista)
            # die('ponto766')
            # var_dump(m)
            # die('ponto750')

            # Insere contas na lista de contas da respectiva extração
            user_account = 'UserAccount'
            # Se campo entrada no dicionário, não existe, cria
            if dext[extraction_id].get(user_account, None) is None:
                dext[extraction_id][user_account] = list()
            dext[extraction_id][user_account].append(conta_formatada)
            # var_dump(dext[extraction_id][user_account])

            # die('ponto783')

    # ------------------------------------------------------------------
    # Prepara propriedades para laudo
    # Todo: Revisar a incluir novamente propriedades, a medida que for examinando novos modelos
    # ------------------------------------------------------------------

    proplaudo_aparelho = {
        # Dados gerais
        # -------------
        # Fabricante do aparelho detectado durante exame
        'DeviceInfoDetectedManufacturer': 'sapiAparelhoMarca',
        # Modelo do aparelho detectado durante exame
        'DeviceInfoDetectedModel': 'sapiAparelhoModelo',
        # Versão do sistema operacional '5.1.1 LMY48B G531BTVJU0AOL1',
        'DeviceInfoRevision': 'sapiAparelhoSistemaOperacional',
        # Descrição do método de extração (ex: 'Lógico [ Android Backup ]')
        'ExtractionType': 'sem uso...sera agrupado',
        # IMEI do aparelho (Ex: '351972070993501')
        'IMEI': 'sapiAparelhoIMEI',
        # Foi extraído de <modelType type="UserAccount">
        'UserAccount': 'sapiUserAccount'
        # A princípio vamos pegar apenas o dado do SimCard...será que precisar o que está no seção do aparelho?
        # ,
        # Número telefonico associado ao aparelho (deve valer para quando tem apenas um SimCard?)
        # 'MSISDN': 'sapiMSISDN'
    }

    proplaudo_sim = {
        # Ex: '89550317001039126416'
        'ICCID': 'sapiSimICCID',
        # Ex: '724044440381414'
        'IMSI': 'sapiSimIMSI',
        # Operadora. (Ex: 'TIM')
        'SPN': 'sapiSimOperadora',
        # Descrição do método de extração do SIM
        'ExtractionType': 'sapiExtracoes',
        # Número telefonico associado ao SimCard, extraído de <model type="SIMData">
        'MSISDN': 'sapiSimMSISDN'
    }

    # Dicionário para armazenamento de dados para laudo
    dlaudo = {}

    # Processa as extrações do aparelho, separando o que é relevante para laudo
    # -------------------------------------------------------------------------
    if (qtd_extracao_aparelho > 0):
        dcomp = dict()
        lista_extracoes = list()
        lista_contas = list()
        for i in dext:
            if not dext[i].get("sapiAparelho", False):
                continue
            # var_dump(dext[i])
            for j in dext[i]:
                if (j not in proplaudo_aparelho):
                    continue
                if (j == 'ExtractionType'):
                    # Como pode haver vária extrações, colocamos em uma lista
                    lista_extracoes.append(dext[i][j])
                elif j == 'UserAccount':
                    # Fazer um lista com a junção de todas as listas de contas
                    lista_contas += dext[i][j]
                else:
                    # Armazena valor da propriedade
                    dcomp[proplaudo_aparelho[j]] = dext[i][j]

        # Verifica se localizou IMEI do dispositivo
        if dcomp.get('sapiAparelhoIMEI', None) is None:
            mensagem = (
                "Não foi detectado IMEI para aparelho. Dica: Normalmente o IMEI é recuperado em extração lógica.")
            avisos += [mensagem]
            if_print_ok(explicar, "#", mensagem)

        # Dados do aparelho
        dcomp['sapiTipoComponente'] = 'aparelho'
        dcomp['sapiNomeComponente'] = 'Aparelho'
        dcomp['sapiExtracoes'] = ', '.join(lista_extracoes)
        lista_contas.sort()
        dcomp['sapiUserAccount'] = ', '.join(lista_contas)

        # Inclui componente
        quantidade_componentes += 1
        ix_comp = "comp" + str(quantidade_componentes)

        dlaudo[ix_comp] = dcomp

    # Processa os cartões SIM, separando o que é relevante para laudo
    # -----------------------------------------------------------------
    # Aqui não agrupa várias extrações.
    # Se por algum motivo houver necessidade de agrupar várias,
    # terá que embutuir alguma lógica para mesclar dados por IMSI
    for i in dext:
        if not dext[i].get("sapiSIM", False):
            continue
        dcomp = dict()
        dcomp["sapiTipoComponente"] = "sim"
        # Nome da extração definida pelo perito
        dcomp["sapiNomeComponente"] = dext[i]["extractionInfo_name"]

        # Propriedades relevantes do SIM
        for j in dext[i]:
            if (j not in proplaudo_sim):
                continue
            dcomp[proplaudo_sim[j]] = dext[i][j]

        # Inclui componente nos dados relevantes para laudo
        quantidade_componentes += 1
        ix_comp = "comp" + str(quantidade_componentes)
        dlaudo[ix_comp] = dcomp

    # TODO: Outros dispositivos...cartões SD, por exemplo
    # Tem que ter um exemplo....

    # Finaliza dados para laudo
    # -----------------------------------------------------------------
    dlaudo['sapiQuantidadeComponentes'] = quantidade_componentes
    dlaudo["sapiTipoAquisicao"] = "extracao"
    dlaudo["sapiSoftwareVersao"] = "UFED/cellebrite " + ufed_pa_version

    dados['laudo'] = dlaudo

    # Estamos guardando os dados gerais da extração para algum uso futuro....
    # ...talvez uma base de conhecimento, estatísticas, buscas técnicas
    # No momento, nem precisaria
    # Tirei isto...não tem muita utilidade, e pode dar confusão
    # dados['tecnicos']['extracoes'] = dext

    # var_dump(dados)
    # die('ponto1044')

    # Ok, validado, mas pode conter avisos
    return (True, dados, erros, avisos)


# Sanitiza strings em UTF8, substituindo caracteres não suportados pela codepage da console do Windows por '?'
# Normalmente a codepage é a cp850 (Western Latin)
# Retorna a string sanitizada e a quantidade de elementos que forma recodificados
def sanitiza_utf8_console(dado):
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
            (saida[k], q) = sanitiza_utf8_console(dado[k])
            qtd += q
        return (saida, qtd)

    # Lista
    if isinstance(dado, list):
        saida = list()
        qtd = 0
        for v in dado:
            (novo_valor, q) = sanitiza_utf8_console(v)
            saida.append(q)
            qtd += q
        return (saida, qtd)

    # Qualquer outro tipo de dado (numérico por exemplo), retorna o próprio valor
    # Todo: Será que tem algum outro tipo de dado que precisa tratamento!?...esperar dar erro
    saida = dado
    return (saida, 0)


# Exibe dados para laudo, com uma pequena formatação para facilitar a visualização
# --------------------------------------------------------------------------------
def exibir_dados_laudo(d):
    print_centralizado(" Dados para laudo ")

    # Sanitiza, para exibição na console
    (d_sanitizado, qtd_alteracoes) = sanitiza_utf8_console(d)

    # Exibe formatado
    pp = pprint.PrettyPrinter(indent=4, width=Glargura_tela)
    pp.pprint(d_sanitizado)
    print_centralizado("")

    if qtd_alteracoes > 0:
        print("#Aviso: Em", qtd_alteracoes,
              "strings foi necessário substituir caracteres especiais que não podem ser exibidos na console por '?'.")

    return


def arquivo_existente(pasta, arquivo):
    caminho_arquivo = pasta + "/" + arquivo
    return os.path.isfile(caminho_arquivo)


# Valida pasta de relatório do cellebrite
# Se o parâmetro explicar=True, irá detalhar os problemas encontrados
# Retorna: True/False
def valida_pasta_relatorio_cellebrite(pasta, explicar=False):
    # Verifica se pasta informada existe
    if not os.path.exists(pasta):
        if_print_ok(explicar)
        if_print_ok(explicar, "* ERRO: Pasta informada não localizada")
        return False

    # Listas de saída
    erros = list()
    avisos = list()

    # PDF
    arquivo = "Relatório.pdf"
    if not arquivo_existente(pasta, arquivo):
        erros += ["Não foi encontrado " + arquivo]

    # HTML
    arquivo = "Relatório.html"
    if not arquivo_existente(pasta, arquivo):
        erros += ["Não foi encontrado " + arquivo]

    # Relatório em formato excel (pode ser xls ou xlsx)
    if not arquivo_existente(pasta, "Relatório.xlsx") and not arquivo_existente(pasta, "Relatório.xls"):
        erros += ["Não foi encontrado Relatório compatível com excel (Relatório.xls ou Relatório.xlsx)"]

    # XML tem que existir, para poder extrair dados para laudo
    arquivo = "Relatório.xml"
    if not arquivo_existente(pasta, arquivo):
        erros += ["Não foi encontrado " + arquivo]

    # xml_em_copia não deve existir...
    arquivo = "Relatório.xml_em_copia"
    if arquivo_existente(pasta, arquivo):
        erros += ["Encontrado arquivo  '" + arquivo + "'. " +
                  " Isto significa que um procedimento de cópia está em andamento ou foi interrompido. " +
                  " Assegure que a pasta que você indicou é REALMENTE deste item" +
                  " Se você tem certeza que esta é a pasta correta, corrija a extensão do arquivo para .xml e rode novamente."]

    # Para os arquivos abaixo, emite apenas warning se estiverem faltando
    # Talvez mais tarde tenha que ter algum parâmetros de configuração, do tipo de exame de celular
    # podendo ser configurado a obrigatoriedade por tipo de exame
    arquivo = "UFEDReader.exe"
    if not arquivo_existente(pasta, arquivo):
        avisos += ["Não foi encontrado " + arquivo]

    arquivo = "Relatório.ufdr"
    if not arquivo_existente(pasta, arquivo):
        avisos += ["Não foi encontrado " + arquivo]

    # Explica resultado com mensagens
    if explicar:
        for m in erros:
            print("* ERRO: ", m)
        for m in avisos:
            print("# Aviso: ", m)

    # Retorna resultado
    return (erros, avisos)


# Chama copia e intercepta/trata erros
def copia_cellebrite_ok():
    try:
        copia_cellebrite()
    except KeyboardInterrupt:
        print("Operação interrompida pelo usuário")
        return


def print_centralizado(texto='', tamanho=Glargura_tela, preenchimento='-'):
    direita = (tamanho - len(texto)) // 2
    esquerda = tamanho - len(texto) - direita
    print(preenchimento * direita + texto + preenchimento * esquerda)



# Exibe dados gerais da tarefa e item, para conferência do usuário
def exibe_dados_tarefa(tarefa):
    print()
    print_centralizado("")
    print("Código da tarefa   : ", tarefa["codigo_tarefa"])
    print("Storage            : ", tarefa['dados_storage']['maquina_netbios'])
    print("Pasta armazenamento: ", tarefa['caminho_destino'])
    print("Situação           : ", tarefa['descricao_situacao_tarefa'])
    if obter_dict_string_ok(tarefa,'status_ultimo')!='':
        print_centralizado("")
        print("Último status  : ", obter_dict_string_ok(tarefa,'status_ultimo'))
        print("Atualizado em  : ", obter_dict_string_ok(tarefa,'status_ultimo_data_hora_atualizacao'))
        print("Tempo          : ", obter_dict_string_ok(tarefa,'tempo_desde_ultimo_status'), " desde última atualização de status")
    print_centralizado("")
    print("Item     : ", tarefa["dados_item"]["item_apreensao"])
    print("Material : ", tarefa["dados_item"]["material"])
    print("Descrição: ", tarefa["dados_item"]["descricao"])
    print_centralizado("")
    print()


# Recupera dados do sevidor relativo à tarefa marcada como corrente (selecionada pelo usuário)
def recupera_servidor_tarefa_corrente():

    # Recupera tarefa
    (tarefa, item) = obter_tarefa_item_corrente()

    # Recupera dados atuais da tarefa do servidor,
    codigo_tarefa = tarefa["codigo_tarefa"]
    (sucesso, msg_erro, tarefa) = sapisrv_chamar_programa(
        "sapisrv_consultar_tarefa.php",
        {'codigo_tarefa': codigo_tarefa},
        abortar_insucesso=True
    )

    # Insucesso. Provavelmente a tarefa não foi encontrada
    if (not sucesso):
        # Continua no loop
        print("Erro: ", msg_erro)
        print("Efetue refresh na lista de tarefa")
        return None

    return tarefa



# Aborta execução de tarefa
# ----------------------------------------------------------------------
def abortar_tarefa_item():
    try:
        _abortar_tarefa_item()
    except KeyboardInterrupt:
        print("Operação interrompida pelo usuário")
        return

def _abortar_tarefa_item():

    print()
    print("- Abortar tarefa.")

    # Recupera situação atual da tarefa corrente do servidor
    # ------------------------------------------------------------------
    print("- Contactando servidor para obter dados atualizados da tarefa. Aguarde...")
    tarefa=recupera_servidor_tarefa_corrente()
    if tarefa is None:
        return False

    # Exibe dados da tarefa para usuário
    # ------------------------------------------------------------------
    exibe_dados_tarefa(tarefa)

    # Verifica se tarefa pode ser abortada
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]
    codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])

    if codigo_situacao_tarefa!=GEmAndamento:
        # Tarefas com outras situações não são permitidas
        print("Tarefa com situação ", codigo_situacao_tarefa, "-",
              tarefa['descricao_situacao_tarefa'] + " NÃO pode ser abortada")
        print("Apenas tarefas EM ANDAMENTO podem ser abortadas")
        print("Em caso de divergência, efetue em Refresh na lista de tarefas (*SG)")
        return


    # ------------------------------------------------------------------------------------------------------------------
    # Ok, está em andamento
    # Vamos ver se atende as condições para ser abortada
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("******* Atenção *******")
    print("- Uma tarefa que está a muito tempo sem atualizar o status pode ter sido interrompida ou estar travada.")
    print("- Contudo, nem sempre isto é verdade.")
    print("  Se por algum motivo a tarefa perdeu contato com o SETEC3, ")
    print("  o seu status não será atualizado, mas a tarefa pode ainda estar rodando,")
    print("  uma vez que os agentes python do SAPI são tolerantes a falhas de comunição com o servidor.")
    print("- Antes de abortar a tarefa, assegure-se que a tarefa realmente NÃO ESTÁ rodando. Sugestões:")
    print("  - Consulte o log com a opção *EL")
    print("  - Conecte no storage de destino via VNC e verifique se a pasta da tarefa está recebendo novos arquivos")
    print("  - Em caso de dúvida, AGUARDE para ver se ocorre alguma evolução...")

    # Se tarefa estiver em andamento, e está sem atualização de status a um longo tempo,
    # isto indica que a mesma deve ter sido interrompida
    # Neste caso, permite abortar a tarefa
    tempo_ultimo_status_segundos = int(tarefa['tempo_ultimo_status_segundos'])
    # Considerando que o tempo normal entre atualizações de status é de 3 minutos
    # vamos dar aqui uma margem de segurança
    minimo_minutos=10 #minutos
    if tempo_ultimo_status_segundos>0 and tempo_ultimo_status_segundos<(minimo_minutos*60):
        print()
        print("- Somente é permitido abortar uma tarefa que esteja a mais de ",str(minimo_minutos)," minutos sem atualizar status")
        print("- Esta tarefa ainda não atende esta condição. Aguarde mais algum tempo.")
        print("- Comando cancelado por não atender tempo mínimo")
        return

    # Ok, já passou do tempo mínimo
    print()
    print("- Abortar uma tarefa é um procedimento irreversível, e implica em refazer a cópia desde o início")
    print("- Se você acha que a cópia foi concluída (está tudo no storage), efetue uma conferência via VNC,")
    print("  e se realmente estiver ok utilize o comando *SI para atualizar o status")
    print()
    prosseguir = pergunta_sim_nao("< Deseja realmente abortar esta tarefa?", default="n")
    if not prosseguir:
        print("- Cancelado pelo usuário.")
        return

    # ------------------------------------------------------------------------------------------------------------------
    # Aborta tarefa
    # ------------------------------------------------------------------------------------------------------------------
    # Atualiza que tarefa foi abortada
    print_log("Usuário comandou (*AT) para tarefa [",codigo_tarefa,"] ser abortada")
    codigo_situacao_tarefa = GAbortou
    texto_status = "Abortada por comando do usuário"
    # Atualiza o status da tarefa com o resultado
    print_log("Atualizando tarefa com: ", codigo_situacao_tarefa, "-", texto_status)
    (ok, msg_erro) = sapisrv_atualizar_status_tarefa(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=codigo_situacao_tarefa,
        status=texto_status
    )

    if (not ok):
        print()
        print("- Não foi possível ABORTAR tarefa. Servidor respondeu: ", msg_erro)
        print("- Comando cancelado")
        return

    # Sucesso
    print()
    print("- Tarefa abortada com sucesso")
    print("- Para consultar situação atualizada, utilize comando *SG")
    return


def intercepta_signal(signal, frame):
    print('signal interceptado')
    return


# Valida e copia relatórios do UFED/Cellebrite
# ----------------------------------------------------------------------
def copia_cellebrite():
    # Verificações antes da cópia
    # -----------------------------------------------------------------------------------------------------------------
    print()
    print("- Cópia de relatório Cellebrite para storage.")
    print("- Contactando servidor para obter dados atualizados da tarefa. Aguarde...")

    # Recupera tarefa
    (tarefa, item) = obter_tarefa_item_corrente()

    # var_dump(item)

    # Recupera dados atuais da tarefa do servidor,
    codigo_tarefa = tarefa["codigo_tarefa"]
    (sucesso, msg_erro, tarefa) = sapisrv_chamar_programa(
        "sapisrv_consultar_tarefa.php",
        {'codigo_tarefa': codigo_tarefa},
        abortar_insucesso=True
    )

    # Insucesso. Provavelmente a tarefa não foi encontrada
    if (not sucesso):
        # Continua no loop
        print("Erro: ", msg_erro)
        print("Efetue refresh na lista de tarefa")
        return False

    # var_dump(item["item"])

    # ------------------------------------------------------------------
    # Exibe dados da tarefa para usuário confirmar
    # ------------------------------------------------------------------
    exibe_dados_tarefa(tarefa)

    # ------------------------------------------------------------------
    # Verifica se tarefa tem o tipo certo
    # ------------------------------------------------------------------
    if (not tarefa["tipo"] == "extracao"):
        # Isto aqui não deveria acontecer nunca...mas para garantir...
        print("Tarefa do tipo [", tarefa["tipo"], "] não pode ser resolvida por sapi_cellebrite")
        return

    # Verifica se tarefa possui situação coerente para execução
    codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
    if (codigo_situacao_tarefa == GAguardandoPCF or codigo_situacao_tarefa == GAbortou):
        # Tudo bem, prossegue
        prosseguir=True
    elif codigo_situacao_tarefa==GEmAndamento:
        #var_dump(tarefa)
        #die('ponto1124')
        print("- ATENÇÃO: Esta tarefa já está em andamento: ", codigo_situacao_tarefa, "-",
              tarefa['descricao_situacao_tarefa'] + " : " + tarefa["status_ultimo"])
        print("- Última atualização de status: ", tarefa['status_ultimo_data_hora_atualizacao'])
        print("- Tempo desde última atualização de status: ", tarefa['tempo_desde_ultimo_status'])
        print("- Se você deseja reiniciar esta tarefa, utilizar primeiramente o comando *AT para abortar.")
        return
    else:
        # Tarefas com outras situações não são permitidas
        print("Tarefa com situação ", codigo_situacao_tarefa, "-",
              tarefa['descricao_situacao_tarefa'] + " NÃO pode ser processada")
        print("Apenas tarefas com situação 'Aguardando ação PCF' ou 'Abortada' podem ser processadas")
        print("Em caso de divergência, efetue em Refresh na lista de tarefas (*SG)")
        return


    # ------------------------------------------------------------------
    # Verifica se tarefa está com o status correto
    # ------------------------------------------------------------------
    # var_dump(tarefa)
    # die('ponto1224')
    # var_dump(tarefa["codigo_situacao_tarefa"])
    # var_dump(GFinalizadoComSucesso)

    if (int(tarefa["codigo_situacao_tarefa"]) == GFinalizadoComSucesso):
        # Isto aqui não deveria acontecer nunca...mas para garantir...
        print("Cancelado: Tarefa já foi finalizada com sucesso.")
        print()
        print("Caso seja necessário refazer esta tarefa, utilize a opção de REINICIAR tarefa no SETEC3.")
        return


    # -----------------------------------------------------------------
    # Pasta de destino
    # -----------------------------------------------------------------

    print("1) Verificando pasta de destino")
    print("================================")

    # -----------------------------------------------------------------
    # Montagem de storage
    # -----------------------------------------------------------------

    # Confirma que tem acesso ao storage escolhido
    (sucesso, ponto_montagem, erro) = acesso_storage_windows(tarefa["dados_storage"])
    if not sucesso:
        print("Acesso ao storage [" + ponto_montagem + "] ** SEM SUCESSO **")
        print("Verifique se servidor está acessível (rede) e disponível (ativo)")
        print("Sugestão: Conecte no servidor via VNC com a conta consulta")
        print("Importante: Evite fazer uma conexão no share desta máquina com a conta de consulta, pois isto pode impedir o acesso para escrita.")
        return

    # Desmonta caminho, separando pasta de arquivo
    # prefixando com ponto de montagem
    # Para o cellebrite, que faz cópia de uma pasta inteira, isto não faz sentido
    # (caminho,nome_arquivo)=decompoe_caminho(tarefa["caminho_destino"])

    caminho_destino = ponto_montagem + tarefa["caminho_destino"]

    print("- Pasta de destino da tarefa no storage:")
    print(" ", caminho_destino)

    # Verifica se pasta de destino já existe
    # Isto não é permitido
    limpar_pasta_destino_antes_copiar = False
    if os.path.exists(caminho_destino):
        print_log("Pasta de destino '" + caminho_destino + "' contém arquivos")
        print()
        print("- IMPORTANTE: A pasta de destino JÁ EXISTE")
        print()
        print("- Não é possível iniciar a cópia nesta situação.")
        print("- Se o conteúdo atual da pasta de destino não tem utilidade,",
              "autorize a limpeza da pasta (opção abaixo).")
        print("- Se você entende que os dados na pasta de destino já estão ok (e não devem ser apagados), cancele este comando")
        print("  e em seguida utilize o comando *si para validar a pasta e atualizar a situação da tarefa.")
        print()
        prosseguir = pergunta_sim_nao(
            "< Você realmente deseja excluir a pasta de destino (assegure-se de estar tratando do item correto)?",
            default="n")
        if not prosseguir:
            # Encerra
            print("- Cancelado pelo usuário.")
            return
        print("- Ok, pasta de destino será excluída durante procedimento de cópia")
        print_log("Usuário solicitou exclusão da pasta de destino: ", caminho_destino)

        # Guarda indicativo que será necessário limpeza da pasta de destino
        limpar_pasta_destino_antes_copiar = True
    else:
        print("- Verifique se na pasta de destino exibida acima as informações relativas ao memorando e item estão ok,")
        print("  pois será assim que ficará na mídia de destino.")
        print("- IMPORTANTE: Se a estrutura não estiver ok (item errado, por exemplo), cancele comando,")
        print("  ajuste no SETEC3 e depois retome esta tarefa.")
        print()
        prosseguir = pergunta_sim_nao("< Estrutura da pasta está ok?", default="n")
        if not prosseguir:
            return

    # ------------------------------------------------------------------
    # Seleciona pasta local de relatórios
    # ------------------------------------------------------------------
    # Solicita que usuário informe a pasta local que contém
    # os relatórios do Cellebrite para o item corrente
    caminho_origem = ""

    # Loop para selecionar pasta
    while True:
        print()
        print("2) Selecionar pasta de origem (relatórios cellebrite)")
        print("=====================================================")
        print("- Na janela gráfica que foi aberta, selecione a pasta que contém os relatórios cellebrite do item.")
        print("- Os arquivos de relatórios devem estar posicionados imediatamente abaixo da pastas informada.")
        # print("<ENTER> para continuar")
        # input()

        # Solicita a pasta de origem
        # Cria janela para seleção de laudo
        root = tkinter.Tk()
        j = Janela(master=root)
        caminho_origem = j.selecionar_pasta()
        root.destroy()

        if (caminho_origem == ''):
            # Se não selecionou nada, pede novamente
            print()
            print("- Cancelado: Nenhuma pasta de origem selecionada.")
            return

        # Se existe o problema de cópia em andamento,
        # dá opção para renomear
        arquivo = "Relatório.xml_em_copia"
        if arquivo_existente(caminho_origem, arquivo):
            print()
            print_log("Detectado presença de arquivo xml_em_copia")
            print("******* ATENÇÃO *******")
            print("- Detectou-se que o procedimento de cópia desta pasta já foi iniciado anteriormente, ")
            print("  pois existe na pasta um arquivo com nome: ",arquivo)
            print("- Isto é normal se houve uma tentativa de cópia anterior que foi interrompida.")
            print("- Caso contrário, algo estranho está acontecendo. Analise cuidadosamente antes de prosseguir.")
            print("=> Tem certeza que você selecionou a A PASTA CORRETA para o item indicado???")
            print()
            print("- Se você decidir prosseguir, o arquivo xml_em_copia será renomeado para xml, para permitir o reinício.")
            print()
            prosseguir = pergunta_sim_nao("< Prosseguir?", default="n")
            if not prosseguir:
                return
            print()
            # Renomeia e prossegue
            de   = os.path.join(caminho_origem, "Relatório.xml_em_copia")
            para = os.path.join(caminho_origem, "Relatório.xml")
            print_log("Usuário indicou que arquivo xml_em_copia deve ser renomeado e cópia deve prosseguir")
            os.rename(de, para)
            print_log("Renomeado ", de, " para ", para)

        # Verificação básica da pasta, para ver se contém os arquivos típicos
        print()
        print("3) Validação da pasta de relatórios")
        print("===================================")
        (erros, avisos) = valida_pasta_relatorio_cellebrite(pasta=caminho_origem, explicar=True)
        if len(erros) == 0 and len(avisos) == 0:
            # Nenhum erro ou aviso
            print("- Pasta contém arquivos padronizados para extração Cellebrite")

        if len(erros) > 0:
            # Se ocorreu erro, aborta comando
            return

        if len(avisos) > 0:
            # Ocorreram avisos. Pede confirmação
            print()
            prosseguir = pergunta_sim_nao("< Verifique os avisos acima. Deseja realmente prosseguir?", default="n")
            if not prosseguir:
                # Encerra, pois possivelmente será necessário algum ajuste na pasta
                return
            print("- Prosseguindo após confirmação de avisos")

        # Ok, prossegue
        break

    # Verifica se o arquivo XML contido na pasta de origem está ok
    arquivo_xml = caminho_origem + "/Relatório.xml"
    print("- Validando arquivo XML: ")
    print(" ",arquivo_xml)
    print("- Isto pode demorar alguns minutos, dependendo do tamanho do arquivo. Aguarde...")
    (resultado, dados_relevantes, erros, avisos) = processar_arquivo_xml(arquivo_xml, numero_item=item["item"],
                                                                         explicar=False)
    if (not resultado):
        # A mensagem de erro já foi exibida pela própria função de validação
        for mensagem in erros:
            print("* ERRO: ", mensagem)
        return False

    print("- XML válido.")
    print()
    print("4) Conferência de dados extraídos para laudo")
    print("============================================")
    print("- Os seguintes dados foram extraídos do relatório xml e serão utilizados no laudo:")
    exibir_dados_laudo(dados_relevantes['laudo'])

    # Exibe avisos, se houver
    if len(avisos) > 0:
        print()
        print_centralizado(' AVISOS ')
        for mensagem in avisos:
            print("# Aviso: ", mensagem)
        print()
        print_centralizado('')

    print("- Verifique se os dados acima estão coerentes com o material examinado.")
    print("- Caso algum campo apresente divergência em relação aos relatórios do Cellebrite (PDF por exemplo),")
    print("  comunique o erro/sugestão de melhoria ao desenvolvedor.")
    print()
    prosseguir = pergunta_sim_nao("< Iniciar cópia? ", default="n")
    if not prosseguir:
        return
    #

    # Antes perguntava se queria fazer cópia em background ou não
    # O problema é que se for em foreground, não está mostrando nenhum acompanhamento da situação para o usuário
    # gerando ansiedade.
    # Logo, é melhor jogar sempre para background e deixar o usuário consultar a situação se quiser.
    # Vamos deixar este código aqui, caso seja necessário algum debug, pois fica mais complicado fazer debug
    # em background
    #
    # copia_background = pergunta_sim_nao("< Efetuar cópia em background? ", default="n")
    copia_background = True
    nome_arquivo_log = obter_nome_arquivo_log()

    if copia_background:
        print()
        print("- Ok, procedimento de cópia foi iniciado em background.")
        print("- Você pode continuar trabalhando, inclusive efetuar outras cópias simultaneamente.")
        print("- Para acompanhar a situação atual, utilize comando *SG")
        print("- Em caso de problema/dúvida, utilize *EL para visualizar o arquivo de log")
        print(
            "- IMPORTANTE: Não encerre este programa se houver cópias em andamentos, pois as mesmas terão de ser reiniciadas")

        # Ignora Interrupção (CTR-C) para permitir que processo filho herde esta propriedade
        #original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        original_sigint_handler = signal.signal(signal.SIGINT, intercepta_signal)
        #var_dump(original_sigint_handler)
        #die('ponto1514')

        proc = multiprocessing.Process(
            target=efetuar_copia,
            args=(caminho_origem, caminho_destino, codigo_tarefa, dados_relevantes, limpar_pasta_destino_antes_copiar,
                  copia_background, nome_arquivo_log))
        proc.start()
        # Inicia cópia em background
        # O fluxo retona imediatamente para cá, e voltamos para à rotina principal
        # permitindo que usuário efetue outras operações
        # Ao término, o usuário será avisado

        # Retorna tratamento para CTR-C original
        signal.signal(signal.SIGINT, original_sigint_handler)

        print()
    else:
        # Não é em background
        print("- Cópia EM FOREGROUND (DEPRECATED). Isto pode demorar...Aguarde....")
        # Inicia cópia e aguarda o término
        # Neste caso, o usuário terá que aguardar até o término da cópia
        efetuar_copia(caminho_origem, caminho_destino, codigo_tarefa, dados_relevantes,
                      limpar_pasta_destino_antes_copiar, copia_background, nome_arquivo_log)

    return


# Efetua a cópia de uma pasta
def efetuar_copia(caminho_origem, caminho_destino, codigo_tarefa, dados_relevantes, limpar_pasta_destino_antes_copiar,
                  copia_background, nome_arquivo_log):

    # Impede interrupção por sigint
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Inicializa sapilib, pois pode estar sendo executando em background (outro processo)
    # Será utilizado o mesmo arquivo de log da thread pai
    sapisrv_inicializar(Gprograma, Gversao, nome_arquivo_log=nome_arquivo_log)

    # Define qual o tipo de saída das mensagens de processamento
    somente_log = 'log'
    tela_log = 'tela log'
    if copia_background:
        # Guarda apenas em log
        tipo_print = somente_log
    else:
        # Se não estiver em background,
        # exibe na tela e no log
        tipo_print = tela_log

    # Registra que está copiando em background
    if copia_background:
        print_var(tipo_print, "Iniciando cópia em background (pid=", os.getpid(), ")")

    # ------------------------------------------------------------------
    # Conceito:
    # ------------------------------------------------------------------
    # Utiliza xml como sinalizador de cópia concluída.
    # Incialmente ele é renomeado.
    # Quando a cópia for concluída ele volta ao nome original.
    # Esta operação visa garantir que outras checagens de estado
    # (por exemplo o comando *si) entenda que a cópia ainda não acabou
    # Só quando a extensão for restaurada para xml o sistema entenderá
    # que a cópia acabou

    arquivo_xml_origem = caminho_origem + "/Relatório.xml"
    arquivo_xml_origem_renomeado = arquivo_xml_origem + "_em_copia"
    p_acompanhar = None
    try:

        # 0) Limpara pasta de destino antes de iniciar
        # ------------------------------------------------------------------
        if limpar_pasta_destino_antes_copiar:
            texto_status = "Excluindo pasta de destino '" + caminho_destino + "'"
            atualizar_status_tarefa_andamento(codigo_tarefa, texto_status)
            print_var(tipo_print,
                      "- Excluindo pasta de destino conforme ordenado '" + caminho_destino )
            shutil.rmtree(caminho_destino, ignore_errors=True)
            texto_status = "Pasta de destino excluída"
            atualizar_status_tarefa_andamento(codigo_tarefa, texto_status)
            print_var(tipo_print,
                  "- Excluído com sucesso.")

        # 1) Renomear o arquivo XML na pasta de origem (nome temporário)
        # ------------------------------------------------------------------
        print_var(tipo_print,
                  "Renomeando arquivo ", arquivo_xml_origem, " para " + arquivo_xml_origem_renomeado + ".")
        print_var(tipo_print,"No final da cópia o nome original será restaurado.")
        os.rename(arquivo_xml_origem, arquivo_xml_origem_renomeado)
        print_var(tipo_print, "Renomeado com sucesso")

        # 2) Inicia processo para acompanhar a cópia
        # Se a cópia não for em background, não tem este acompanhamento
        if copia_background:
            texto_status = "Calculando tamanho da pasta de origem"
            atualizar_status_tarefa_andamento(codigo_tarefa, texto_status)

            tam_pasta_origem=tamanho_pasta(caminho_origem)
            texto_status = "Pasta de origem com " + converte_bytes_humano(tam_pasta_origem)
            atualizar_status_tarefa_andamento(codigo_tarefa, texto_status)

            p_acompanhar = multiprocessing.Process(target=acompanhar_copia,
                                                   args=(tipo_print, codigo_tarefa, caminho_destino, tam_pasta_origem, nome_arquivo_log))
            p_acompanhar.start()


        # 2) Efetuar a cópia
        # ------------------------------------------------------------------
        texto_status = "Iniciando cópia de '" + caminho_origem + "' para '" + caminho_destino + "'"
        atualizar_status_tarefa_andamento(codigo_tarefa, texto_status)
        shutil.copytree(caminho_origem, caminho_destino)
        texto_status = "Comando de cópia concluído"
        atualizar_status_tarefa_andamento(codigo_tarefa, texto_status)

        # 3) Confere se cópia foi efetuada com sucesso
        # ------------------------------------------------------------------
        # TODO: Como garantir que a cópia foi efetuada com sucesso?
        # Armazenar e checar hashes?

        # 4) Restaura o nome do arquivo XML na pasta destino
        # ------------------------------------------------------------------
        arquivo_xml_destino = caminho_destino + "/Relatório.xml_em_copia"
        arquivo_xml_destino_renomeado = caminho_destino + "/Relatório.xml"
        print_var(tipo_print, "Restaurado nome de arquivo '" +
                  arquivo_xml_destino + "' para '" + arquivo_xml_destino_renomeado + "'")
        os.rename(arquivo_xml_destino, arquivo_xml_destino_renomeado)
        print_var(tipo_print, "Renomeado com sucesso na pasta de destino")

        # 5) Restaura o nome do arquivo XML na pasta origem
        # ------------------------------------------------------------------
        arquivo_xml_origem = caminho_origem + "/Relatório.xml_em_copia"
        arquivo_xml_origem_renomeado = caminho_origem + "/Relatório.xml"
        print_var(tipo_print, "Restaurado nome de arquivo '" +
                  arquivo_xml_origem + "' para '" + arquivo_xml_origem_renomeado + "'")
        os.rename(arquivo_xml_origem, arquivo_xml_origem_renomeado)
        print_var(tipo_print, "Renomeado com sucesso na pasta de origem")

    except BaseException as e:
        # Erro fatal: Mesmo que esteja em background, exibe na tela
        print()
        print_var(tela_log, "** ERRO em procedimento de cópia ** : " + str(e))
        print("Consulte log para mais informações")

        # Atualiza que tarefa foi abortada
        codigo_situacao_tarefa = GAbortou
        texto_status = "Cópia não foi concluída com sucesso"
        # Atualiza o status da tarefa com o resultado
        print_var(tipo_print, "Atualizando tarefa com: ", codigo_situacao_tarefa, "-", texto_status)
        (ok, msg_erro) = sapisrv_atualizar_status_tarefa(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=codigo_situacao_tarefa,
            status=texto_status
        )

        if (not ok):
            print()
            print_var(tela_log, "Não foi possível atualizar status de ABORTADA da tarefa: ", msg_erro)
            print_var(tela_log, "Isto implica que sistema pensará que tarefa ainda está em execução")
            print_var(tela_log, "Será necessário reiniciar esta tarefa")
            print()
            return

        # Finaliza tarefas em background
        if p_acompanhar is not None:
            print_var(tipo_print, "Encerrando thread de acompanhamento de copia")
            p_acompanhar.terminate()
            print_var(tipo_print, "Thread de acompanhamento de copia encerrada")

        # Encerra
        return

    # Cópia concluída
    print()
    print_var(tela_log, "Cópia da pasta ", caminho_origem, " finalizada com SUCESSO")

    # Cópia finalizada
    # Atualiza situação da tarefa
    # -----------------------------------------------------------------------------------------------------------------
    codigo_situacao_tarefa = GFinalizadoComSucesso
    texto_status = "Dados copiados com sucesso para pasta de destino"
    # Atualiza o status da tarefa com o resultado
    print_var(tipo_print, "Atualizando tarefa com: ", codigo_situacao_tarefa, "-", texto_status)
    (ok, msg_erro) = sapisrv_atualizar_status_tarefa(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=codigo_situacao_tarefa,
        status=texto_status,
        dados_relevantes=dados_relevantes
    )

    if (not ok):
        print()
        print_var(tela_log, "Não foi possível atualizar status de finalização da tarefa: ", msg_erro)
        print_var(tela_log,
                  "Após diagnosticar e resolver a causa do problema, utilize comando *SI para atualizar situação da tarefa")
        print()
        return

    # Status atualizado
    print_var(tela_log, "Tarefa ", codigo_tarefa, " atualizada para 'SUCESSO'")

    # Encerra o processo de acompanhamento de cópia
    if copia_background:
        p_acompanhar.terminate()
        print_var(tipo_print, "Encerrando processo background para acompanhamento de copia")


# Efetua a cópia de uma pasta
def acompanhar_copia(tipo_print, codigo_tarefa, caminho_destino, tam_pasta_origem, nome_arquivo_log):

    # Impede interrupção por sigint
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Inicializa sapilib, pois pode estar sendo executando em background (outro processo)
    sapisrv_inicializar(Gprograma, Gversao, nome_arquivo_log=nome_arquivo_log)

    print_var(tipo_print, "Thread de acompanhamento de tarefa ativada")
    print_var(tipo_print, "A cada ",GtempoEntreAtualizacoesStatus," segundos será atualizado o status da cópia")

    # Um pequeno delay inicial, para dar tempo da cópia começar
    time.sleep(30)

    # Fica em loop inifito. Será encerrado pelo pai (com terminate)
    while True:
        # Verifica o tamanho atual da pasta de destino
        tamanho_copiado=tamanho_pasta(caminho_destino)
        tamanho_copiado_humano = converte_bytes_humano(tamanho_copiado)

        # Atualiza status
        percentual=(tamanho_copiado/tam_pasta_origem)*100
        texto_status = tamanho_copiado_humano + " ("+str(round(percentual,1))+"%) copiados"
        print_var(tipo_print, texto_status)
        atualizar_status_tarefa_andamento(codigo_tarefa, texto_status)

        # Intervalo entre atualizações de status
        time.sleep(GtempoEntreAtualizacoesStatus)


# Explicar=True: Faz com que seja exibida (print) a explicação imediatamente
# Retorna tupla:
#   1) codigo_situacao_tarefa: Retorna o código da situação.
#      Se operação falhou, retorna -1 ou nulo
#      -1 ou nulo: Comando não foi executado
#   2) texto_situacao: Texto complementar da situação
#   3) dados_relevantes: Dados relevantes, para utilização em laudo
# ----------------------------------------------------------------------
def determinar_situacao_item_cellebrite(explicar=False):
    # Constantes de codigo_situacao
    erro_interno = -1
    erros = list()
    avisos = list()

    # Aviso de início para execução interativa
    if_print_ok(explicar, "Contactando servidor. Aguarde...")

    # Recupera tarefa
    (tarefa, item) = obter_tarefa_item_corrente()

    # Recupera dados atuais da tarefa do servidor,
    codigo_tarefa = tarefa["codigo_tarefa"]
    (sucesso, msg_erro, tarefa) = sapisrv_chamar_programa(
        "sapisrv_consultar_tarefa.php",
        {'codigo_tarefa': codigo_tarefa},
        abortar_insucesso=True
    )

    # Insucesso. Provavelmente a tarefa não foi encontrada
    if (not sucesso):
        # Continua no loop
        if_print_ok(explicar, "Erro: ", msg_erro)
        if_print_ok(explicar, "Efetue refresh na lista de tarefa")
        return (erro_interno, "", {}, erros, avisos)

    # var_dump(item["item"])

    # xxx
    # ------------------------------------------------------------------
    # Exibe dados do item para usuário confirmar
    # se escolheu o item correto
    # ------------------------------------------------------------------
    print()
    print_centralizado("")
    print("Tarefa: ", tarefa["codigo_tarefa"])
    print("Situação no servidor: ", tarefa['descricao_situacao_tarefa'])
    print("Item: ", tarefa["dados_item"]["item_apreensao"])
    print("Material: ", tarefa["dados_item"]["material"])
    print("Descrição: ", tarefa["dados_item"]["descricao"])
    print_centralizado("")
    print()

    # ------------------------------------------------------------------
    # Verifica se tarefa tem o tipo certo
    # ------------------------------------------------------------------
    if (not tarefa["tipo"] == "extracao"):
        # Isto aqui não deveria acontecer nunca...mas para garantir...
        print("Tarefa do tipo [", tarefa["tipo"], "] não pode ser tratada por sapi_cellebrite")
        return (erro_interno, "", {}, erros, avisos)

    # -----------------------------------------------------------------
    # Pasta de armazenamento do item no Storage
    # -----------------------------------------------------------------

    # Confirma que tem acesso ao storage escolhido
    (sucesso, ponto_montagem, erro) = acesso_storage_windows(tarefa["dados_storage"])
    if not sucesso:
        erro = "Acesso ao storage [" + ponto_montagem + "] falhou"
        if_print_ok(explicar, erro)
        return (erro_interno, "", {}, erros, avisos)

    caminho_destino = ponto_montagem + tarefa["caminho_destino"]
    if_print_ok(explicar, "- Pasta de destino da tarefa:", caminho_destino)

    # Verifica se pasta de destino já existe
    if not os.path.exists(caminho_destino):
        status = "Não iniciado (sem pasta)"
        if_print_ok(explicar, "- Pasta de destino ainda não foi criada.")
        return (GSemPastaNaoIniciado, status, {}, erros, avisos)  # Não iniciado

    if_print_ok(explicar, "- Pasta de destino existente.")

    # Default, para algo que iniciou.
    # Mas irá verificar mais adiante, se está em estágio mais avançado
    # codigo_status = GPastaDestinoCriada
    # status = "Pasta criada"

    # Verificação básica da pasta, para ver se contém os arquivos típicos
    (erros, avisos) = valida_pasta_relatorio_cellebrite(pasta=caminho_destino, explicar=explicar)
    if len(erros) > 0:
        status = "Existem arquivos básicos faltando."
        codigo_status = GEmAndamento
        if_print_ok(explicar, status)
        return (codigo_status, status, {}, erros, avisos)

    # Ok, já tem todos os arquivos básicos
    status = "- Pasta contém todos os arquivos básicos."
    if_print_ok(explicar, status)

    # Valida arquivo xml
    if_print_ok(explicar,
                "- Validando Relatório.XML. Isto pode demorar, dependendo do tamanho do arquivo. Aguarde...")
    arquivo_xml = caminho_destino + "/Relatório.xml"
    (resultado, dados_relevantes, erros, avisos) = processar_arquivo_xml(arquivo_xml, numero_item=item["item"],
                                                                         explicar=True)
    if (not resultado):
        status = "Arquivo XML inconsistente"
        codigo_status = GAbortou
        if_print_ok(explicar, status)
        return (codigo_status, status, {}, erros, avisos)

    # Se está tudo certo, exibe o resultado dos dados coletados para laudo
    # se estiver no modo de explicação
    if_print_ok(explicar, "- XML válido.")
    if (explicar):
        print("- Os seguintes dados foram selecionados para utilização em laudo:")
        # Exibe dados do laudo
        exibir_dados_laudo(dados_relevantes['laudo'])

    # Sucesso
    status = "Relatório Cellebrite armazenado com sucesso"
    codigo_status = GFinalizadoComSucesso
    return (codigo_status, status, dados_relevantes, erros, avisos)

# Exibe situação do item
# ----------------------------------------------------------------------------------------------------------------------
def exibir_situacao_item():
    console_executar_tratar_ctrc(funcao=_exibir_situacao_item)

def _exibir_situacao_item():

    # Cabeçalho
    print()
    print_centralizado(" Verificando situação da tarefa corrente ")

    (codigo_situacao_tarefa, texto_status, dados_relevantes, erros, avisos) = determinar_situacao_item_cellebrite(explicar=True)
    print()
    print("- Situação observada no storage         : ", str(codigo_situacao_tarefa), "-", texto_status)

    # Se falhou, não tem o que fazer
    if (codigo_situacao_tarefa == -1):
        print("Não foi possível determinar a situação do item. Verifique a conectividade com o storage")
        return

    # Recupera tarefa
    (tarefa, item) = obter_tarefa_item_corrente()

    # Recupera dados atuais da tarefa do servidor,
    codigo_tarefa = tarefa["codigo_tarefa"]
    (sucesso, msg_erro, tarefa_servidor) = sapisrv_chamar_programa(
        "sapisrv_consultar_tarefa.php",
        {'codigo_tarefa': codigo_tarefa},
        abortar_insucesso=True
    )

    # Insucesso
    if (not sucesso):
        # Continua no loop
        print("Falha na busca da tarefa no servidor: ", msg_erro)
        return

    # Exibe o status da tarefa no servidor
    print("- Situação no servidor SAPI(SETEC3)     : ",
                tarefa_servidor["codigo_situacao_tarefa"],
          "-",
          tarefa_servidor["descricao_situacao_tarefa"])

    # Se a situação é mesma, está tudo certo
    if (codigo_situacao_tarefa == int(tarefa_servidor["codigo_situacao_tarefa"])):
        print()
        print("- Situação observada na pasta de destino está coerente com a situação do servidor.")
        return

    # Se a situação é mesma, está tudo certo
    if (codigo_situacao_tarefa < int(tarefa_servidor["codigo_situacao_tarefa"])):
        print()
        print("Situação observada é divergente da situação reportada pelo servidor.")
        print("Reporte esta situação ao desenvolvedor.")
        return

    # Se houver divergência entre situação atual e situação no servidor
    # pergunta se deve atualizar
    print()
    print('ATENÇÃO: A situação da tarefa no servidor (SAPI/SETEC3) não está coerente com a situação observada na pasta de destino do storage.')
    print('- Isto pode ocorrer caso tenha havido alguma falha no procedimento')
    print('  de atualização da situação após a cópia no sapi_cellebrite, ou caso tenha sido feita uma cópia manual.')
    print('- Em caso de dúvida, consulte o log sapi_log.txt.')
    print()
    print('- Caso você tenha certeza que os dados armazenados no servidor estão ok,')
    print('  basta efetuar a atualização do situação (respondendo S na próxima pergunta)')
    print('- Caso contrário, refaça a cópia (comando *CR)')
    print()
    atualizar = pergunta_sim_nao("< Atualizar servidor SAPI com a situação observada? ", default="n")
    if (not atualizar):
        return

    # var_dump(dados_relevantes)
    # die('ponto1597')

    # Atualiza situação observada no servidor
    (ok, msg_erro) = sapisrv_atualizar_status_tarefa(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=codigo_situacao_tarefa,
        status=texto_status,
        dados_relevantes=dados_relevantes
    )

    if (not ok):
        print()
        print("ATENÇÃO: Não foi possível atualizar a situação no servidor: ", msg_erro)
        print()
    else:
        print()
        print("Tarefa atualizada com sucesso no servidor")
        print()
        print("Exibindo nova situação das tarefas")
        refresh_tarefas()
        exibir_situacao()

    return


# Exibe lista de tarefas
# ----------------------------------------------------------------------
def exibir_situacao():

    # Cabeçalho da lista de elementos
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

    # Lista elementos
    # ----------------------------------------------------------------------------------
    q = 0
    for dado in Gtarefas:
        q += 1
        t = dado.get("tarefa")
        i = dado.get("item")

        # Sinalizador de Corrente
        corrente = "  "
        if (q == Gicor):
            corrente = '=>'

        # Situacao
        situacao = t["estado_descricao"]
        # Se está em andamento, mostra o último status, se houver
        if int(t['codigo_situacao_tarefa']) == int(GEmAndamento) and t['status_ultimo'] is not None:
            situacao = t['status_ultimo']

        # var_dump(i)

        # Calcula largura da última coluna, que é variável (item : Descrição)
        # Esta constantes de 60 é a soma de todos os campos e espaços antes do campo "Item : Descrição"
        lid = Glargura_tela - 58
        lid_formatado = "%-" + str(lid) + "." + str(lid) + "s"

        string_formatacao = '%2s %2s %6s %-30.30s %-13s ' + lid_formatado
        # var_dump(string_formatacao)
        # die('ponto1811')

        # cabecalho
        if (q == 1):
            # print('%2s %2s %6s %-30.30s %15s %-69.69s' % (
            #    " ", "Sq", "tarefa", "Situação", "Material", "Item : Descrição"))
            print(string_formatacao % (
                " ", "Sq", "tarefa", "Situação", "Material", "Item : Descrição"))
            print_centralizado()
        # Tarefa
        item_descricao = t["item"] + " : " + i["descricao"]
        #        print('%2s %2s %6s %-30.30s %15s %-69.69s' % (
        #            corrente, q, t["codigo_tarefa"], situacao, i["material"], item_descricao))
        print(string_formatacao % (
            corrente, q, t["codigo_tarefa"], situacao, i["material"], item_descricao))

        if (q == Gicor):
            #print('    ' + "'"*59)
            #print('    ' + "^")
            print_centralizado()

    print()
    print("Dica: Para recuperar a situação atualizada do servidor (Refresh), utilize comando *SG")

    return

def print_cabecalho_programa():

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


# Exibe conteúdo do arquivo de log
# ----------------------------------------------------------------------
def exibir_log():

    # Limpa tela e imprime cabeçalho do programa
    # --------------------------------------------------------------------------------
    cls()
    print_cabecalho_programa()
    print("Arquivo de log: ",obter_nome_arquivo_log())
    print_centralizado()

    arquivo_log=obter_nome_arquivo_log()

    #arquivo_log=Gparini.get('log',None)
    #if arquivo_log is None:
    #    arquivo_log="sapi_log.txt"

    with codecs.open(arquivo_log, 'r', "utf-8") as sapi_log:
        print(sapi_log.read())

    sapi_log.close()

    return



# Salva situação atual para arquivo
# ----------------------------------------------------------------------
def salvar_estado():
    # Monta dicionario de estado
    estado = dict()
    estado["Gtarefas"] = Gtarefas
    estado["GdadosGerais"] = GdadosGerais

    # Abre arquivo de estado para gravação
    nome_arquivo = Garquivo_estado
    arquivo_estado = open(nome_arquivo, "w")

    # Grava e encerra
    json.dump(estado, arquivo_estado, indent=4)
    arquivo_estado.close()


# Carrega situação de arquivo
# ----------------------------------------------------------------------
def carregar_estado():
    # Irá atualizar as duas variáveis relacionadas com estado
    global Gtarefas
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
    Gtarefas = estado["Gtarefas"]
    GdadosGerais = estado["GdadosGerais"]


# Avisa que dados vieram do estado
# print("Dados carregados do estado.sapi")
# sprint("Isto so deve acontecer em ambiente de desenvolvimento")


# Recupera memorando, tratando CTR-C
# ----------------------------------------------------------------------
def obter_memorando_tarefas_ok():
    try:
        return obter_memorando_tarefas()
    except KeyboardInterrupt:
        print()
        print("Operação interrompida pelo usuário")
        return False


# Carrega situação de arquivo
# ----------------------------------------------------------------------
def obter_memorando_tarefas():
    # Irá atualizar a variáel global de tarefas
    global Gtarefas

    # Cabeçalho
    print()
    print("Seleção de Memorando")
    print_centralizado("-")
    print("Dica: Para interromper, utilize CTR-C")
    print("")

    # Solicita que o usuário se identifique através da matricula
    # ----------------------------------------------------------
    lista_solicitacoes = None
    while True:

        matricula = input("Entre com sua matrícula: ")
        matricula = matricula.replace(".", "")
        matricula = matricula.lower().strip()

        if not matricula.isdigit():
            continue

        print()
        print("- Consultando servidor (SETEC3), aguarde...")
        print_log("Recuperando solicitações de exame para matrícula: ", matricula)
        (sucesso, msg_erro, lista_solicitacoes) = sapisrv_chamar_programa(
            "sapisrv_obter_pendencias_pcf.php",
            {'matricula': matricula},
            abortar_insucesso=True,
        )

        # Insucesso....normalmente matricula incorreta
        if (not sucesso):
            # Continua no loop
            print_tela_log("Erro: ", msg_erro)
            continue

        # Matricula ok, vamos ver se tem solicitacoes de exame
        if (len(lista_solicitacoes) == 0):
            print_tela_log(
                "Não existe nenhuma solicitacao de exame com tarefas SAPI para esta matrícula. Verifique no setec3")
            continue

        # Tudo certo, encerra loop
        break

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
    print("- Estas são as solicitações de exames que foram iniciadas no SAPI.")
    print("- Se a solicitação de exame que você procura não está na lista, confira situação no SETEC3 => Perícia => SAPI.")
    # print("type(lista_solicitacoes)=",type(lista_solicitacoes))

    # Usuário escolhe a solicitação de exame de interesse
    # --------------------------------------------------------
    tarefas = None
    while True:
        #
        print()
        num_solicitacao = input(
            "Selecione a solicitação de exame, indicando o número de sequencia (Sq) na lista acima: ")
        num_solicitacao = num_solicitacao.strip()
        if not num_solicitacao.isdigit():
            print("Entre com o numero da solicitacao")
            continue

        # Verifica se existe na lista
        num_solicitacao = int(num_solicitacao)
        if not (1 <= num_solicitacao <= len(lista_solicitacoes)):
            # Número não é válido
            print("Entre com o numero da solicitacao, entre 1 e ", str(len(lista_solicitacoes)))
            continue

        ix_solicitacao = int(num_solicitacao) - 1

        # Ok, selecionado
        print()
        solicitacao = lista_solicitacoes[ix_solicitacao]
        GdadosGerais["identificacaoSolicitacao"] = (
            solicitacao["identificacao"] +
            " Protocolo: " +
            solicitacao["numero_protocolo"] + "/" + solicitacao["ano_protocolo"])
        # Para utilização em diveros lugares padronizados
        GdadosGerais["identificacaoObjeto"] = GdadosGerais["identificacaoSolicitacao"]
        print_log("Usuário escolheu ",GdadosGerais["identificacaoObjeto"])

        # print("Selecionado:",solicitacao["identificacao"])
        print("Consultando tarefas para", GdadosGerais["identificacaoSolicitacao"], ". Aguarde...")

        # Carrega as tarefas de extração da solicitação selecionada
        # --------------------------------------------------------
        codigo_solicitacao_exame_siscrim = solicitacao["codigo_documento_externo"]
        GdadosGerais["codigo_solicitacao_exame_siscrim"] = codigo_solicitacao_exame_siscrim

        (sucesso, msg_erro, tarefas) = sapisrv_chamar_programa(
            "sapisrv_obter_tarefas.php",
            {'tipo': 'extracao', 'codigo_solicitacao_exame_siscrim': codigo_solicitacao_exame_siscrim},
            abortar_insucesso=True
        )

        # Analisa tarefas recuperadas
        if (len(tarefas) == 0):
            print()
            print()
            print("Esta solicitação de exame NÃO TEM NENHUMA TAREFA DE EXTRAÇÃO. Verifique no SETEC3.")
            print()
            continue

        # Tudo certo, interrompe loop
        break

    # Guarda data hora do último refresh de tarefas
    GdadosGerais["data_hora_ultima_atualizacao_status"] = datetime.datetime.now().strftime('%H:%M:%S')

    # Armazena tarefas
    Gtarefas = tarefas

    return True


def refresh_tarefas():
    # Irá atualizar a variáel global de tarefas
    global Gtarefas

    print("Consultando situação atualizada das tarefas do memorando em andamento no servidor (SETEC3). Aguarde...")

    codigo_solicitacao_exame_siscrim = GdadosGerais["codigo_solicitacao_exame_siscrim"]

    (sucesso, msg_erro, tarefas) = sapisrv_chamar_programa(
        "sapisrv_obter_tarefas.php",
        {'tipo': 'extracao',
         'codigo_solicitacao_exame_siscrim': codigo_solicitacao_exame_siscrim
         },
        abortar_insucesso=True
    )

    # Guarda na global de tarefas
    Gtarefas = tarefas

    # Guarda data hora do último refresh de tarefas
    GdadosGerais["data_hora_ultima_atualizacao_status"] = datetime.datetime.now().strftime('%H:%M:%S')

    return True


# Exibir informações sobre tarefa
# ----------------------------------------------------------------------
def dump_tarefa():
    print("===============================================")

    var_dump(Gtarefas[Gicor])

    print("===============================================")


# Funções relacionada com movimentação nas tarefas
# ----------------------------------------------------------------------
def avancar_item():
    global Gicor

    if (Gicor < len(Gtarefas)):
        Gicor += 1


def recuar_item():
    global Gicor

    if (Gicor > 1):
        Gicor -= 1


def posicionar_item(n):
    global Gicor

    n = int(n)

    if (1 <= n <= len(Gtarefas)):
        Gicor = n


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
    print("Aguarde conexão com servidor...")
    print()

    # Inicialização de sapilib
    # -----------------------------------------------------------------------------------------------------------------
    print_log('Iniciando ', Gprograma , ' - ', Gversao)
    sapisrv_inicializar_ok(Gprograma, Gversao, auto_atualizar=True)

    # Carrega o estado anterior
    # -----------------------------------------------------------------------------------------------------------------
    carregar_estado()
    if len(Gtarefas) > 0:
        print("Retomando execução do último memorando. Para trocar de memorando, utilize opção *tt")
        refresh_tarefas()
    else:
        # Obtem lista de tarefas, solicitando o memorando
        if not obter_memorando_tarefas_ok():
            # Se usuário interromper seleção de tarefas
            print("Execução finalizada.")
            #sys.exit()
            return

    # Salva estado atual
    salvar_estado()


    # Processamento das tarefas
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
            # Verifica se tem processos filho rodando
            lista = multiprocessing.active_children()
            if len(lista) != 0:
                #
                print("Existem ", len(lista), " processos filho (em background) rodando. ")
                print(
                    "Caso estes processos filhos estejam realizando cópia de dados, as operações de cópia serão interrompidas e as tarefas deverão ser reiniciadas.")
                prosseguir_finalizar = pergunta_sim_nao("Deseja realmente finalizar? ", default="n")
                if not prosseguir_finalizar:
                    continue

                # Eliminando processos filhos que ainda estão ativos
                print_log("Usuário foi avisado que existem processos rodando, e respondeu que desejava encerrar mesmo assim")
                lista = multiprocessing.active_children()
                for i in lista:
                    print_log("Matando processo: ", i)
                    i.terminate()

                while True:
                    # Uma pequen pausa para dar tempo dos processos finalizarem
                    time.sleep(3)
                    lista = multiprocessing.active_children()
                    qtd = len(lista)
                    if qtd == 0:
                        print_log("Todos os processos filhos foram eliminados")
                        break
                    print_tela_log("Aguardando encerramento de processos (",len(lista),")")
                    # Aguarda e repete
                    time.sleep(1)

            # Finaliza
            print()
            print_tela_log("Programa finalizado por solicitação do usuário")
            break

        # Executa os comandos
        # -----------------------
        if (comando.isdigit()):
            posicionar_item(comando)
            exibir_situacao()
        elif (comando == '+'):
            avancar_item()
            exibir_situacao()
        elif (comando == '-'):
            recuar_item()
            exibir_situacao()
        elif (comando == "*ir"):
            posicionar_item(argumento)
            exibir_situacao()

        # Comandos de item
        if (comando == '*du'):
            dump_tarefa()
            continue
        elif (comando == '*cr'):
            copia_cellebrite_ok()
            continue
        elif (comando == '*si'):
            exibir_situacao_item()
            continue
        elif (comando == '*at'):
            abortar_tarefa_item()
            continue

        # Comandos gerais
        if (comando == '*sg'):
            refresh_tarefas()
            exibir_situacao()
            continue
        elif (comando == '*el'):
            exibir_log()
            continue
        elif (comando == '*dg'):
            if modo_debug():
                desligar_modo_debug()
                print("- Modo debug foi desligado")
            else:
                ligar_modo_debug()
                print("- Modo debug foi ligado")
            continue
        elif (comando == '*tt'):
            if obter_memorando_tarefas_ok():
                # Se trocou de memorando, Inicializa indice da tarefa corrente e exibe
                Gicor = 1
                salvar_estado()
                exibir_situacao()
                continue

                # Loop de comando

    # Finaliza
    print()
    print("FIM SAPI - Cellebrite (Versão ", Gversao, ")")



if __name__ == '__main__':

    # # Teste de problema de codificação para console
    # # Não remova isto aqui, pois não tenho certeza se este assunto foi definitivamente resolvido
    # outro=dict()
    # outro["1"]=["primeiro string", "segundo string", 123]
    # outro["2"]="qualquer coisa com acentuação"
    #
    # d=dict()
    # d['comp1']='xyz'
    # d['comp2']='Tania 😉😘' #Não tem suporte para cp850
    # d['comp3']=outro
    #
    # (sanitizado, qtd_alteracoes) = sanitiza_utf8_console(d)
    # var_dump(sanitizado)
    # print(qtd_alteracoes)
    # print(exibir_dados_laudo(d))
    #
    # die('ponto2068')

    # GdadosGerais["data_hora_ultima_atualizacao_status"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # var_dump(GdadosGerais["data_hora_ultima_atualizacao_status"])
    # die('ponto2061')

    # Desvia para um certo ponto, para teste
    # --------------------------------------

    # Sintetizar arquivo
    # sintetizar_arquivo_xml("Relatório.xml", "parcial.xml")
    # die('ponto1908')

    # Desvia para um certo ponto, para teste
    # Chama validacao de xml
    # (resultado_teste, dados_teste, erros_teste, avisos_teste) = validar_arquivo_xml("parcial.xml", numero_item="12",
    #                                                                                 explicar=True)
    # print(resultado_teste)
    # exibir_dados_laudo(dados_teste['laudo'])
    # die('ponto1936')

    main()

    print("Pressione qualquer tecla para concluir, ou feche a janela")
    input()

