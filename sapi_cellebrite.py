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
Gpfilhos = dict()  # Processos filhos

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
    '+': 'Navegar para a tarefa seguinte da lista',
    '-': 'Navegar para a tarefa anterior da lista',

    # Comandos relacionados com a tarefa corrente
    '*cr': 'Copiar a pasta de relatórios do Cellebrite para o STORAGE',
    '*ab': 'Abortar tarefa que está (ou deveria estar) em andamento',
    '*ri': 'Reiniciar tarefa que foi concluída com sucesso',
    '*cs': 'Comparar a situação da tarefa indicada no SETEC3 com a situação observada no storage, e corrige, se necessário',
    '*du': '(Dump) Mostrar todas as propriedades de uma tarefa (utilizado para Debug)',
    '*ex': 'Excluir tarefa',
    '*lo': 'Exibe log da tarefa',

    # Comandos gerais
    '*sg': 'Exibir situação atualizada das tarefas (com refresh do servidor). ',
    '*sgr': 'Exibir situação repetidamente (Loop) com refresh do servidor. ',
    '*tt': 'Trocar memorando',
    '*qq': 'Finalizar',

    # Comandos para diagnóstico de problemas
    '*lg': 'Exibir log geral desta instância do sapi_cellebrite. Utiliza argumento como filtro (exe: *EL status => Exibe apenas registros de log contendo o string "status".',
    '*db': 'Ligar/desligar modo debug. No modo debug serão geradas mensagens adicionais no log.'

}

Gmenu_comandos['cmd_exibicao'] = ["*sg", "*sgr"]
Gmenu_comandos['cmd_navegacao'] = ["+", "-"]
Gmenu_comandos['cmd_item'] = ["*cr", "*cs", "*ab", "*ri","*ex", "*lo"]
Gmenu_comandos['cmd_geral'] = ["*tt", "*qq"]
Gmenu_comandos['cmd_diagnostico'] = ["*db", "*lg"]

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

# Características de pasta
def obter_caracteristicas_pasta(start_path):
    total_size = 0
    qtd=0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
            qtd=qtd+1

    # Dicionários de retorno
    ret=dict()
    ret["quantidade_arquivos"]=qtd
    ret["tamanho_total"]=total_size

    return ret



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

    debug("Arquivo XML sintetizado gravado em ", caminho_arquivo_temporario)

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
        if_print(explicar, mensagem)
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
        if_print(explicar, "#", mensagem)
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
    #     if_print(explicar, "#", mensagem)

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
        mensagem = ("Não foi encontrada nenhuma extração com características de ser um aparelho celular." +
                    " O material não tem aparelho?")
        avisos += [mensagem]
        if_print(explicar, "#", mensagem)

    if (qtd_extracao_sim == 0):
        mensagem = ("Não foi encontrada nenhuma extração com características de cartão 'SIM'." +
                    "Realmente não tem SIM Card?. ")
        avisos += [mensagem]
        if_print(explicar, "#", mensagem)

    if (qtd_extracao_sd > 0):
        mensagem = ("Sistema ainda não é capaz de inserir dados do cartão automaticamente no laudo.")
        avisos += [mensagem]
        if_print(explicar, "#", mensagem)

    if (qtd_extracao_backup > 0):
        mensagem = (
            "Sistema ainda não preparado para tratar relatório de processamento de Backup. Consulte desenvolvedor.")
        avisos += [mensagem]
        if_print(explicar, "#", mensagem)

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
                nome = field.get('name', None)

                # <value type="String"><![CDATA[MSISDN 1]]></value>
                # <value type="String"><![CDATA[99192334]]></value>
                for value in field:
                    valor = value.text
                    m[nome] = valor

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

            # Insere contas na lista de contas da respectiva extração
            user_account = 'UserAccount'
            # Se campo entrada no dicionário, não existe, cria
            if dext[extraction_id].get(user_account, None) is None:
                dext[extraction_id][user_account] = list()
            dext[extraction_id][user_account].append(conta_formatada)


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
            if_print(explicar, "#", mensagem)

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
        if_print(explicar)
        if_print(explicar, "- ERRO: Pasta informada não localizada")
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



def print_centralizado(texto='', tamanho=Glargura_tela, preenchimento='-'):
    direita = (tamanho - len(texto)) // 2
    esquerda = tamanho - len(texto) - direita
    print(preenchimento * direita + texto + preenchimento * esquerda)


# Remove decimal dos segundos
# 00:02:25.583054 => 00:02:25
def remove_decimos_segundo(tempo):
    tempo = str(tempo)
    # Separa e descartar após decimal
    tempo_str, lixo = tempo.split(".")
    return tempo_str


# Exibe dados gerais da tarefa e item, para conferência do usuário
def exibe_dados_tarefa(tarefa):
    print()
    print_centralizado("")
    print("Código da tarefa   : ", tarefa["codigo_tarefa"])
    print("Storage            : ", tarefa['dados_storage']['maquina_netbios'])
    print("Pasta armazenamento: ", tarefa['caminho_destino'])
    print("Situação           : ", tarefa["codigo_situacao_tarefa"],"-", tarefa['descricao_situacao_tarefa'])
    if obter_dict_string_ok(tarefa, 'status_ultimo') != '':
        tempo_str = remove_decimos_segundo(obter_dict_string_ok(tarefa, 'tempo_desde_ultimo_status'))
        print_centralizado("")
        print("Último status   : ", obter_dict_string_ok(tarefa, 'status_ultimo'))
        print("Atualizado em   : ",
              remove_decimos_segundo(obter_dict_string_ok(tarefa, 'status_ultimo_data_hora_atualizacao')))
        print("Tempo decorrido desde última atualização de status: ", tempo_str)
    print_centralizado("")
    print("Item     : ", tarefa["dados_item"]["item_apreensao"])
    print("Material : ", tarefa["dados_item"]["material"])
    print("Descrição: ", tarefa["dados_item"]["descricao"])
    print_centralizado("")
    print()


# Recupera dados do sevidor relativo à tarefa marcada como corrente (selecionada pelo usuário)
def recupera_tarefa_do_setec3(codigo_tarefa):

    tarefa=None
    try:
        # Recupera dados atuais da tarefa do servidor,
        (sucesso, msg_erro, tarefa) = sapisrv_chamar_programa(
            "sapisrv_consultar_tarefa.php",
            {'codigo_tarefa': codigo_tarefa}
        )

        # Insucesso. Provavelmente a tarefa não foi encontrada
        if (not sucesso):
            # Sem sucesso
            print_tela_log("[1073] Recuperação de dados atualizados do SETEC da tarefa",codigo_tarefa,"FALHOU: ", msg_erro)
            return None

    except BaseException as e:
        print_tela_log("[1077] Recuperação de dados atualizados do SETEC da tarefa", codigo_tarefa, "FALHOU: ", str(e))
        return None

    return tarefa



def print_atencao():
    # Na tela sai legal...aqui está distorcido, provavelmente em função da largura dos caracteres
    # teria que ter uma fonte com largura fixa
    print("┌─────────────────┐")
    print("│  A T E N Ç Ã O  │")
    print("└─────────────────┘")


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
    print("- Consulte o log para entender melhor o problema(*EL)")
    print("- Se você suspeita de falha de comunicação (rede), ")
    print("  tente acessar o SETEC3 utilizando um browser computador para conferira se a conexão está ok")

def print_comando_cancelado():
    print("- Comando cancelado")
    print()

# ----------------------------------------------------------------------------------------------------------------------
# @*ab - Aborta execução de tarefa
# ----------------------------------------------------------------------------------------------------------------------
def abortar_tarefa():
    console_executar_tratar_ctrc(funcao=_abortar_tarefa)

# Retorna True se tarefa pode ser abortada
def pode_abortar(tarefa):

    # Verifica se tarefa pode ser abortada
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]
    codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])

    if codigo_situacao_tarefa != GEmAndamento:
        # Tarefas com outras situações não são permitidas
        print("- Tarefa com situação ", codigo_situacao_tarefa, "-",
              tarefa['descricao_situacao_tarefa'] + " NÃO pode ser abortada")
        print("- Apenas tarefas EM ANDAMENTO podem ser abortadas")
        print("- Se você quer reexecutar esta tarefa, utilize o comando *RI")
        print("- Em caso de divergência, efetue em Refresh na lista de tarefas (*SG)")
        print("- Comando cancelado.")
        return False

    # ------------------------------------------------------------------------------------------------------------------
    # Está executando neste momento?
    # ------------------------------------------------------------------------------------------------------------------
    nome_processo="executar:"+str(codigo_tarefa)
    processo=Gpfilhos.get(nome_processo, None)
    if processo is not None and processo.is_alive():
        # Ok, tarefa está sendo executada
        print_log("Encontrado processo da tarefa a ser abortada em execução")
        return True

    # ------------------------------------------------------------------------------------------------------------------
    # O status foi atualizado recentemente
    # ------------------------------------------------------------------------------------------------------------------
    tempo_ultimo_status_segundos = int(tarefa['tempo_ultimo_status_segundos'])
    # Considerando que o tempo normal entre atualizações de status é de 3 minutos
    # vamos bloquear se estiver a menos tempo que isto
    minimo_minutos = 3  # minutos
    if tempo_ultimo_status_segundos > 0 and tempo_ultimo_status_segundos < (minimo_minutos * 60):
        print()
        print_atencao()
        print("- Esta tarefa foi atualizada faz apenas ", tempo_ultimo_status_segundos, "segundos.")
        print("- Como o ciclo de atualização é a cada 180 segundos, é possível que ainda haja um processo rodando.")
        print("- Se o programa que executava a tarefa foi encerrado anormalmente,")
        print("  ou seja foi fechado sem sair via *qq, e isto aconteceu faz pouco tempo, tudo bem, bastará aguardar.")
        print("- Caso contrário, assegure-se que não existe outra instância do sapi_cellebrite rodando, ")
        print("  talvez em outro computador.")
        print("  Dicas:")
        print("  - Consultando o log da tarefa no SETEC3 você poderá determinar o IP do computador que está atualizando a tarefa.")
        print("  - Conecte no storage de destino via VNC e ")
        print("    verifique se a pasta de destino da tarefa está realmente recebendo novos arquivos.")
        print("  - Se você não localizar uma instância do sapi_cellebrite rodando, e suspeita que haja um processo orfão,")
        print("    rodando, abra o gerenciador de tarefas e procure por 'python'.")
        print("- De qualquer forma, para garantir, você terá que aguardar mais um pouco! ")
        print("- Tente novamente daqui a 3 minutos.")
        print()
        return False

    # ------------------------------------------------------------------------------------------------------------------
    # Ok, está em andamento, e sem status recente
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print_atencao()
    print("- Esta tarefa está a bastante tempo sem atualização do status, indicando que o seu processamento")
    print("  deve ter sido interrompido ou estar travado (congelado).")
    print("- Contudo, isto nem sempre isto é verdade.")
    print("  Se por algum motivo o processo que está executando a tarefa perdeu contato com o SETEC3, ")
    print("  o status da tarefa não será atualizado, mas o processo pode ainda estar rodando,")
    print("  uma vez que os agentes python do SAPI são tolerantes a falhas de comunição com o servidor.")
    print("- Antes de abortar a tarefa, assegure-se que a tarefa realmente NÃO ESTÁ sendo processada.")
    print("- Dicas:")
    print("  - Conecte no storage de destino via VNC e verifique se a pasta da tarefa não está sendo alterada")
    print("  - Se a máquina em que está rodando o sapi_cellebrite para a tarefa utiliza Windows 10, ")
    print("    verifique se a console não está travada em modo de seleção: Aparece no cabeçalho o texto SELECT.")
    print("    Se for este o caso, um simples <ENTER> fará com o que o processo continue.")
    print("    Depois disso, consulte o Wiki para ver como configurar o prompt para evitar a repetição do problema")
    print("  - Se a tarefa estava sendo processada neste mesma instância do sapi_cellebrite:")
    print("    - Consulte o log com a opção *EL (talvez esta máquina tenha perdido conexão com o SETEC3)")
    print("    - Dê o comando *qq, para verificar quais processos estão rodando em background.")
    print("  - Em caso de dúvida, AGUARDE para ver se ocorre alguma evolução.")
    # Ok, vamos abortar
    return True

def _abortar_tarefa():
    print()
    print("- Abortar tarefa.")

    # Carrega situação atualizada da tarefa
    # ----------------------------------------
    tarefa = carrega_exibe_tarefa_corrente()
    if tarefa is None:
        return False
    codigo_tarefa = tarefa["codigo_tarefa"]

    # Label para log
    definir_label_log('*ab:'+codigo_tarefa)

    # Verifica se tarefa pode ser abortada
    #-----------------------------------------
    abortar=pode_abortar(tarefa)

    # Alguma situação impede (ou o usuário desistiu de abortar)
    # Retorna ao menu de comandos
    if not abortar:
        print()
        return

    # Confirmação final
    # ---------------------
    print()
    print("- Abortar uma tarefa é um procedimento irreversível, e implica em refazer a cópia desde o início")
    print()
    prosseguir = pergunta_sim_nao("< Deseja realmente abortar esta tarefa?", default="n")
    if not prosseguir:
        print("- Cancelado pelo usuário.")
        return False


    # ------------------------------------------------------------------------------------------------------------------
    # Aborta tarefa
    # ------------------------------------------------------------------------------------------------------------------
    print("- Abortando tarefa. Aguarde...")

    print_log("Abortando tarefa ",codigo_tarefa, " por solicitação do usuário (*AB)")

    # Mata qualquer processo relacionado com esta tarefa
    for ix in sorted(Gpfilhos):

        if codigo_tarefa not in ix:
            # Não é processo desta tarefa
            continue

        if Gpfilhos[ix].is_alive():
            # Se está rodando, finaliza
            Gpfilhos[ix].terminate()
            print_log("Finalizado processo", ix, "[", Gpfilhos[ix].pid, "]")

    # Troca situação da tarefa
    # ------------------------
    if not troca_situacao_tarefa_ok(codigo_tarefa=codigo_tarefa,
                                    codigo_nova_situacao=GAbortou,
                                    texto_status="Abortada por comando do usuário (*AB)"
                                    ):
        # Se falhar, encerra. Mensagens já foram dadas na função chamada
        return


    # Sucesso comando (*AB)
    print()
    print("- Situação da tarefa alterada para'Abortada'")
    print("- Esta tarefa está disponível para ser refeita.")
    exibir_situacao_apos_comando()
    return


# ----------------------------------------------------------------------------------------------------------------------
# @*ri - Reinicia execução de tarefa
# ----------------------------------------------------------------------------------------------------------------------
def reiniciar_tarefa():
    console_executar_tratar_ctrc(funcao=_reiniciar_tarefa)

# Retorna True se tarefa pode ser reiniciada
def pode_reiniciar(tarefa):

    # Verifica se tarefa pode ser reiniciada
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]
    codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])

    if codigo_situacao_tarefa != GFinalizadoComSucesso:
        # Tarefas com outras situações não são permitidas
        print("- Tarefa com situação ", codigo_situacao_tarefa, "-",
              tarefa['descricao_situacao_tarefa'] + " NÃO pode ser reiniciada")
        print("- Apenas tarefas FINALIZADA COM SUCESSO podem ser reiniciadas")
        print("- Em caso de divergência, efetue em Refresh na lista de tarefas (*SG)")
        return False

    # ------------------------------------------------------------------------------------------------------------------
    # Verifica se tarefa possui filhas já iniciadas
    # ------------------------------------------------------------------------------------------------------------------
    qtd=int(tarefa["quantidade_tarefas_filhas_iniciadas"])
    if qtd>0:
        print("- Esta tarefa possui ", qtd, " tarefa(s) filha(s) já iniciada(s)")
        print("- Desta forma, não é possível reinicializá-la.")
        print("- Se você realmente quer reiniciar, exclua primeiro a(s) tarefa(s) filhas")
        print("  Dica: Consulte cada tarefa filha no SETEC3, para obter instrução de como efetuar a exclusão.")
        return False

    # Ok, pode reiniciar
    return True

def _reiniciar_tarefa():
    print()
    print("- Reiniciar tarefa")

    # Carrega situação atualizada da tarefa
    # -----------------------------------------
    tarefa = carrega_exibe_tarefa_corrente()
    if tarefa is None:
        return False

    codigo_tarefa = tarefa["codigo_tarefa"]

    # Label para log
    definir_label_log('*ri:'+codigo_tarefa)

    # Verifica se pode reiniciar
    # ----------------------------------------
    reiniciar=pode_reiniciar(tarefa)

    # Alguma situação impede (ou o usuário desistiu de reiniciar)
    # Retorna ao menu de comandos
    if not reiniciar:
        print()
        return

    # ------------------------------------------------------------------------------------------------------------------
    # Confirmação final
    # ------------------------------------------------------------------------------------------------------------------
    print()
    prosseguir = pergunta_sim_nao("< Deseja realmente reiniciar esta tarefa?", default="n")
    if not prosseguir:
        print("- Cancelado pelo usuário.")
        return False

    # ------------------------------------------------------------------------------------------------------------------
    # Reinicia tarefa
    # ------------------------------------------------------------------------------------------------------------------
    print("- Reiniciando tarefa. Aguarde...")

    # Troca situação da tarefa
    # ------------------------
    if not troca_situacao_tarefa_ok(codigo_tarefa=codigo_tarefa,
                                    codigo_nova_situacao=GAguardandoPCF,
                                    texto_status="Reiniciada por comando do usuário(*RI)"
                                    ):
        # Se falhar, encerra. Mensagens já foram dadas na função chamada
        return


    # Sucesso comando (*RI)
    print()
    print_tela_log("- Situação da tarefa alterada para 'Aguardando PCF'")
    print("- Tarefa está pronta para ser refeita")
    exibir_situacao_apos_comando()
    return


# ----------------------------------------------------------------------------------------------------------------------
# @*lo - Exibir log de tarefa
# ----------------------------------------------------------------------------------------------------------------------

def exibir_log_tarefa(filtro_usuario):

    (tarefa, item) = obter_tarefa_item_corrente()
    codigo_tarefa = tarefa["codigo_tarefa"]

    print()
    print("- Exibir log da tarefa", codigo_tarefa)

    filtro_base=":"+codigo_tarefa+"]"
    exibir_log(comando='*lo',filtro_base=filtro_base, filtro_usuario=filtro_usuario, limpar_tela=False)

    return





# ----------------------------------------------------------------------------------------------------------------------
# @*ri - Reinicia execução de tarefa
# ----------------------------------------------------------------------------------------------------------------------
def reiniciar_tarefa():
    console_executar_tratar_ctrc(funcao=_reiniciar_tarefa)

# Retorna True se tarefa pode ser reiniciada
def pode_reiniciar(tarefa):

    # Verifica se tarefa pode ser reiniciada
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]
    codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])

    if codigo_situacao_tarefa != GFinalizadoComSucesso:
        # Tarefas com outras situações não são permitidas
        print("- Tarefa com situação ", codigo_situacao_tarefa, "-",
              tarefa['descricao_situacao_tarefa'] + " NÃO pode ser reiniciada")
        print("- Apenas tarefas FINALIZADA COM SUCESSO podem ser reiniciadas")
        print("- Em caso de divergência, efetue em Refresh na lista de tarefas (*SG)")
        return False

    # ------------------------------------------------------------------------------------------------------------------
    # Verifica se tarefa possui filhas já iniciadas
    # ------------------------------------------------------------------------------------------------------------------
    qtd=int(tarefa["quantidade_tarefas_filhas_iniciadas"])
    if qtd>0:
        print("- Esta tarefa possui ", qtd, " tarefa(s) filha(s) já iniciada(s)")
        print("- Desta forma, não é possível reinicializá-la.")
        print("- Se você realmente quer reiniciar, exclua primeiro a(s) tarefa(s) filhas")
        print("  Dica: Consulte cada tarefa filha no SETEC3, para obter instrução de como efetuar a exclusão.")
        return False

    # Ok, pode reiniciar
    return True

def _reiniciar_tarefa():
    print()
    print("- Reiniciar tarefa")

    # Carrega situação atualizada da tarefa
    # -----------------------------------------
    tarefa = carrega_exibe_tarefa_corrente()
    if tarefa is None:
        return False

    # Verifica se pode reiniciar
    # ----------------------------------------
    reiniciar=pode_reiniciar(tarefa)

    # Alguma situação impede (ou o usuário desistiu de reiniciar)
    # Retorna ao menu de comandos
    if not reiniciar:
        print()
        return

    # ------------------------------------------------------------------------------------------------------------------
    # Confirmação final
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("- Confira se você selecionou a tarefa correta a ser reiniciada.")
    print()
    prosseguir = pergunta_sim_nao("< Deseja realmente reiniciar esta tarefa?", default="n")
    if not prosseguir:
        print("- Cancelado pelo usuário.")
        return False

    # ------------------------------------------------------------------------------------------------------------------
    # Reinicia tarefa
    # ------------------------------------------------------------------------------------------------------------------
    print("- Reiniciando tarefa. Aguarde...")

    codigo_tarefa = tarefa["codigo_tarefa"]

    # Troca situação da tarefa
    # ------------------------
    if not troca_situacao_tarefa_ok(codigo_tarefa=codigo_tarefa,
                                    codigo_nova_situacao=GAguardandoPCF,
                                    texto_status="Reiniciada por comando do usuário(*RI)"
                                    ):
        # Se falhar, encerra. Mensagens já foram dadas na função chamada
        return


    # Sucesso comando (*RI)
    print()
    print("- Situação da tarefa alterada para 'Aguardando PCF'")
    print("- Tarefa está pronta para ser refeita")
    exibir_situacao_apos_comando()
    return


# ----------------------------------------------------------------------------------------------------------------------
# @*ex - Excluir tarefa
# ----------------------------------------------------------------------------------------------------------------------
def excluir_tarefa():
    console_executar_tratar_ctrc(funcao=_excluir_tarefa)

# Retorna True se tarefa pode ser excluida
def pode_excluir(tarefa):

    # Verifica se tarefa pode ser excluida
    # ------------------------------------------------------------------
    codigo_tarefa = tarefa["codigo_tarefa"]
    codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])

    # Label para diferenciar mensagens de log
    definir_label_log('*ex:'+codigo_tarefa)

    # Não pode estar em Em Andamento (no SETEC3)
    # ------------------------------------------
    if codigo_situacao_tarefa == GEmAndamento:
        # Tarefas com outras situações não são permitidas
        print("- Tarefa NÃO pode ser excluída, pois está em andamento. Apenas tarefas 'paradas' podem ser excluídas")
        print("- Utilize comando *AB (abortar tarefa) para interromper execução e depois reaplique comando *EX")
        return False


    # Não pode ter algum processo em backgroud executando a tarefa
    # ------------------------------------------------------------
    for ix in sorted(Gpfilhos):
        if Gpfilhos[ix].is_alive() and "executar":
            dummy, codigo_tarefa_execucao = ix.split(':')
            if int(codigo_tarefa_execucao)==codigo_tarefa:
                print("- Tarefa",codigo_tarefa, "está rodando em background (",ix,Gpfilhos[ix].pid,")")
                print("- Antes de excluir a tarefa, é necessário abortar a execução. Utilize comando *AB")
                return False


    # Não pode ter alguma tarefa filha já iniciada
    # --------------------------------------------
    qtd=int(tarefa["quantidade_tarefas_filhas_iniciadas"])
    if qtd>0:
        print("- Esta tarefa possui ", qtd, " tarefa(s) filha(s) já iniciada(s)")
        print("- Desta forma, não é possível excluí-la.")
        print("- Se você realmente quer excluir esta tarefa, exclua primeiro a(s) tarefa(s) filhas")
        print("  Dica: Consulte cada tarefa filha no SETEC3, para obter instrução de como efetuar a exclusão.")
        return False

    # Ok, pode excluir
    return True


def _excluir_tarefa():
    print()
    print("- Excluir tarefa")

    # Carrega situação atualizada da tarefa
    # -----------------------------------------
    tarefa = carrega_exibe_tarefa_corrente()
    if tarefa is None:
        return False
    codigo_tarefa = tarefa["codigo_tarefa"]

    # Verifica se pode excluir
    # ----------------------------------------
    excluir=pode_excluir(tarefa)

    # Alguma situação impede (ou o usuário desistiu de excluir)
    # Retorna ao menu de comandos
    if not excluir:
        print("- Comando cancelado")
        return

    # -----------------------------------------------------------------
    # Pasta de destino
    # -----------------------------------------------------------------
    print()
    print("Verificando pasta de destino")
    print("=============================")

    print("- Storage da tarefa: ", tarefa["dados_storage"]["maquina_netbios"])

    # Montagem de storage
    # -------------------
    # Confirma que tem acesso ao storage escolhido
    # print("- Verificando conexão com storage de destino. Aguarde...")
    ponto_montagem = conectar_ponto_montagem_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return

    caminho_destino = ponto_montagem + tarefa["caminho_destino"]

    print("- Pasta de destino no storage:")
    print(" ", tarefa["caminho_destino"])

    # Verifica se pasta de destino já existe
    limpar_pasta_destino = False
    if os.path.exists(caminho_destino):
        print_atencao()
        print()
        print("- A pasta de destino da tarefa já existe.")
        print("- A exclusão da tarefa irá apagar definitivamente todos os dados desta pasta.")
        print("- Se você precisa dos dados da pasta, conecte no servidor e efetue uma cópia dos dados antes de prosseguir.")
        print()
        prosseguir = pergunta_sim_nao(
            "< Você concorda que a pasta de destino da tarefa seja excluída?",
            default="n")
        if not prosseguir:
            # Encerra
            print("- Cancelado pelo usuário.")
            return
        print_log("Usuário solicitou exclusão da pasta de destino: ", caminho_destino)
        limpar_pasta_destino = True
    else:
        print("- Não existe pasta de destino (Não foi criado nada no storage para esta tarefa)")
        print()

    # ------------------------------------------------------------------------------------------------------------------
    # Efetuar exclusão da tarefa
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("Efetuar exclusão")
    print("================")
    print()
    print("- A exclusão de uma tarefa é um procedimento IRREVERSÍVEL.")
    print("- Sugestão: Confira pela última vez se você selecionou a tarefa correta!!!")
    print()
    print("- Está tudo pronto para excluir tarefa.")
    prosseguir = pergunta_sim_nao("< Prosseguir? ", default="n")
    if not prosseguir:
        return

    # Decide o método a utilizar.
    # Se houver pasta da tarefa, efetua exclusão em background. Caso contrário, faz exclusão em foreground
    if limpar_pasta_destino:
        efetuar_exclusao_background(codigo_tarefa, caminho_destino, )
        return

    # Efetua exclusão em foreground
    # ------------------------------------------------------
    try:
        # Exclui tarefa no SETEC3
        # -----------------------
        sapisrv_excluir_tarefa(codigo_tarefa=codigo_tarefa)
        print_log("Tarefa excluida com sucesso")
    except BaseException as e:
        print_tela_log("- Não foi possível excluir tarefa: ", str(e))
        print_falha_comunicacao()
        return

    # Ok, exclusão finalizada
    return



def efetuar_exclusao_background(codigo_tarefa, caminho_destino):
    # Troca situação da tarefa
    # ------------------------
    texto_status = "Excluindo tarefa"
    if not troca_situacao_tarefa_ok(codigo_tarefa=codigo_tarefa,
                                    codigo_nova_situacao=GEmExclusao,
                                    texto_status=texto_status
                                    ):
        # Se falhar, encerra. Mensagens já foram dadas na função chamada
        return

    # ------------------------------------
    # Inicia procedimentos em background
    # ------------------------------------
    print_log("Iniciando exclusão em background")
    # Os processo filhos irão atualizar o mesmo arquivo log do processo pai
    nome_arquivo_log_para_processos_filhos = obter_nome_arquivo_log()

    # Inicia processo filho para excluir tarefa
    # ------------------------------------------------------------------------------------------------------------------
    label_processo = "executar:" + str(codigo_tarefa)
    dados_pai_para_filho=obter_dados_para_processo_filho()
    p_executar = multiprocessing.Process(
        target=background_executar_exclusao,
        args=(codigo_tarefa, caminho_destino,
              nome_arquivo_log_para_processos_filhos, label_processo, dados_pai_para_filho)
    )
    p_executar.start()

    registra_processo_filho(label_processo, p_executar)

    # Inicia processo filho para acompanhar exclusão
    # ------------------------------------------------------------------------------------------------------------------
    label_processo = "acompanhar:" + str(codigo_tarefa)
    p_acompanhar = multiprocessing.Process(
        target=background_acompanhar_exclusao,
        args=(codigo_tarefa, caminho_destino, nome_arquivo_log_para_processos_filhos, label_processo))
    p_acompanhar.start()

    registra_processo_filho(label_processo, p_acompanhar)

    # Tudo certo, agora é só aguardar
    print()
    print("- Ok, procedimento de exclusão foi iniciado em background.")
    print("- Você pode continuar trabalhando, inclusive efetuar outras tarefas simultaneamente.")
    print("- Para acompanhar a situação da exclusão, utilize o comando *SG, ou então *SGR (repetitivo)")
    print("- Também é possível acompanhar a situação através do SETEC3")
    print("- Em caso de problema/dúvida, utilize *EL para visualizar o log")
    print("- IMPORTANTE: Não encerre este programa enquanto houver tarefas em andamento, ")
    print("  pois as mesmas serão interrompidas e terão que ser reprocessadas")
    print("- Quando a exclusão for finalizada, a tarefa desaparecerá da lista de tarefas")

    exibir_situacao_apos_comando()

    return



# Efetua a exclusão da tarefa, incluindo sua pasta de destino
def background_executar_exclusao(codigo_tarefa, caminho_destino,
                                 nome_arquivo_log, label_processo, dados_pai_para_filho):

    # Impede interrupção por sigint
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Inicializa sapilib
    # Será utilizado o mesmo arquivo de log do processo pai
    sapisrv_inicializar(Gprograma, Gversao, nome_arquivo_log=nome_arquivo_log, label_processo=label_processo)

    # Restaura dados herdados do processo pai
    restaura_dados_no_processo_filho(dados_pai_para_filho)


    # ------------------------------------------------------------------
    # Conceito:
    # ------------------------------------------------------------------
    sucesso=False
    try:
        # 1) Marca início em background
        print_log("Início da exclusão em background para tarefa", codigo_tarefa)

        # 2) Exclui pasta de destino
        # ---------------------------
        texto_status = "Excluindo pasta de destino"
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)
        # Exclui pasta de destino
        shutil.rmtree(caminho_destino, ignore_errors=True)
        # Ok, exclusão concluída
        texto_status = "Pasta de destino excluída"
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)

        # Se chegou aqui, sucesso
        print_log("Exclusão de pasta da tarefa efetuada com sucesso")
        sucesso=True

    except BaseException as e:
        # Erro fatal: Mesmo estando em background, exibe na tela
        erro_resultado=str(e)
        print_tela_log("- [1673] ** ERRO na tarefa",codigo_tarefa, "durante exclusão:" + erro_resultado)
        print("- Consulte log para mais informações")
        sucesso=False

    # -----------------------------------------------------------------------------------------------------------------
    # EXCLUSÃO COM ERRO
    # -----------------------------------------------------------------------------------------------------------------
    if not sucesso:
        try:
            # Troca para situação Abortada
            # -----------------------------------
            sapisrv_troca_situacao_tarefa_obrigatorio(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=GAbortou,
                texto_status="Exclusão falhou")
        except BaseException as e:
            # Se não conseguiu trocar a situação, avisa que usuário terá que abortar manualmente
            print()
            print_tela_log("- [1826] Não foi possível abortar a tarefa",codigo_tarefa, "automaticamente")
            print_tela_log("- Exclusão falhou, e além disso, quando o sistema tentou atualizar situação para 'Abortada', isto também falhou")
            print_tela_log("- Tarefa está em situação inconsistente, como se estive sendo excluída, mas na realidade já foi abortada")
            print_tela_log("- Será necessário abortar manualmente (comando *AB)")
            print_falha_comunicacao()
            # Prossegue por gravidade, pois está em background e irá encerrar logo em seguida

        # Encerra
        sys.exit(0)

    # -----------------------------------------------------------------------------------------------------------------
    # Exclusão finalizada com sucesso
    # -----------------------------------------------------------------------------------------------------------------
    try:
        # Exclui tarefa no SETEC3
        # -----------------------------------
        sapisrv_excluir_tarefa(codigo_tarefa=codigo_tarefa)
        print_log("Tarefa excluida com sucesso")
    except BaseException as e:
        print()
        print_tela_log("- Exclusão da pasta da tarefa", codigo_tarefa,"foi concluída")
        print_tela_log("- Contudo, NÃO FOI POSSÍVEL possível excluir a tarefa no SETEC3")
        print_tela_log("- Esta tarefa ficará em estado inconsistente, pois para o sistema ainda está sendo excluída")
        print("- Após sanar o problema (rede?), execute novamente o comando para concluir a exclusão")
        print_falha_comunicacao()
        sys.exit(0)

    # Tudo certo
    print()
    print_tela_log("- Tarefa", codigo_tarefa, "excluída com sucesso")
    print("- Utilize comando *SG para conferir a situação atual da lista de tarefas")
    print("- Esta tarefa não aparecerá mais na lista de tarefas")

    print_log("Fim da exclusão em background para tarefa", codigo_tarefa)
    sys.exit(0)

# Acompanhamento de copia em background
def background_acompanhar_exclusao(codigo_tarefa, caminho_destino, nome_arquivo_log, label_processo):

    # Impede interrupção por sigint
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Inicializa sapilib, compartilhando o arquivo de log do processo principal
    sapisrv_inicializar(Gprograma, Gversao, nome_arquivo_log=nome_arquivo_log, label_processo=label_processo)
    print_log("Processo de acompanhamento de cópia iniciado")

    # Executa, e se houver algum erro, registra em log
    try:

        # simula erro
        #i=5/0

        _background_acompanhar_exclusao(codigo_tarefa, caminho_destino)

    except BaseException as e:
        # Erro fatal: Mesmo que esteja em background, exibe na tela
        print()
        print("*** Acompanhamento de exclusão falhou, consulte log para mais informações ***")
        print_log("*** Erro *** em acompanhamento de exclusão: ", str(e))

    # Encerra normalmente
    print_log("Processo de acompanhamento de exclusão finalizado")
    sys.exit(0)


# Processo em background para efetuar o acompanhamento da cópia
def _background_acompanhar_exclusao(codigo_tarefa, caminho_destino):

    # intervalo entre as atualizações
    pausa=15

    # Recupera características da pasta de destino
    r=obter_caracteristicas_pasta(caminho_destino)
    tam_pasta_destino = r.get("tamanho_total", None)
    if tam_pasta_destino is None:
        # Se não tem conteúdo, encerrra....Não deveria acontecer nunca
        raise("[2027] Falha na obtençao do tamanho da pasta de destino")

    # Avisa que vai começar
    print_log("A cada ", GtempoEntreAtualizacoesStatus, "segundos será atualizado o status da exclusão")

    # Fica em loop enquanto tarefa estiver em situação EmExclusao
    tamanho_anterior=-1
    while True:

        # Intervalo entre atualizações de status
        time.sleep(pausa)

        # Verifica se tarefa ainda está em estado de Exclusao
        tarefa=recupera_tarefa_do_setec3(codigo_tarefa)
        if tarefa is not None:
            codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
            if codigo_situacao_tarefa != GEmExclusao:
                print_log("Verificado que situação da tarefa",codigo_tarefa,"foi modificada para",codigo_situacao_tarefa,". Encerrando acompanhamento de exclusão.")
                return

        # Aumenta o tempo de pausa a cada atualização de status
        # sem ultrapassar o máximo
        pausa = round(pausa * 1.2)
        if pausa > GtempoEntreAtualizacoesStatus:
            # Pausa nunca será maior que o limite estabelecido
            pausa = GtempoEntreAtualizacoesStatus

        debug("Novo ciclo de acompanhamento de exclusão de tarefa")

        # Verifica o tamanho atual da pasta de destino
        try:
            tamanho_atual = tamanho_pasta(caminho_destino)
        except OSError as e:
            # Quando a pasta está sendo excluída, é comum que o procedimento
            # de verificação de tamanho falhe,
            # pois quando ele vai pegar as propriedades de um arquivo, o mesmo foi excluído pelo outro processo
            debug("[1800] Ignorando erro: ",str(e))
            # Não tem o que fazer...Tentar novamente
            continue

        # Atualiza tamanho atual da pasta
        tamanho_atual_humano = converte_bytes_humano(tamanho_atual)

        # Atualiza status
        percentual = (tamanho_atual / tam_pasta_destino) * 100
        texto_status = "Falta excluir " + tamanho_atual_humano + " (" + str(round(percentual, 1)) + "%)"
        print_log(texto_status)
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)

        if percentual>=100:
            print_log("Encerrando acompanhamento de exclusão, pois foi excluido 100% da pasta da tarefa")
            return


# @*ex - FIM ----------------------------------------------------------------------------------------------------------



# ---------------------------------------------------------------------------------------------------------------------
# Diversas funções de apoio
# ---------------------------------------------------------------------------------------------------------------------
def carrega_exibe_tarefa_corrente():

    # Recupera tarefa corrente
    (tarefa, item) = obter_tarefa_item_corrente()
    codigo_tarefa = tarefa["codigo_tarefa"]

    print("- Contactando SETEC3 para obter dados atualizados da tarefa",codigo_tarefa,": Aguarde...")

    tarefa=recupera_tarefa_do_setec3(codigo_tarefa)

    # Se não encontrar a tarefa
    # -------------------------
    if tarefa is None:
        # Tarefa não foi recuperada
        print_tela_log("- Não foi possível recuperar dados do servidor para tarefa",codigo_tarefa)
        print("- Talvez esta tarefa tenha sido excluída.")
        print("- Utilize *SG para atualizar a lista de tarefas.")
        print("- Consulte o log (*EL) em caso de dúvida.")
        return None

    # Ok, tarefa recuperada
    # ------------------------------------------------------------------
    exibe_dados_tarefa(tarefa)
    return tarefa

# Efetua conexão no ponto de montagem, dando tratamento em caso de problemas
def conectar_ponto_montagem_storage_ok(dados_storage):

    nome_storage = dados_storage['maquina_netbios']
    print("- Verificando conexão com storage",nome_storage,": Aguarde...")

    (sucesso, ponto_montagem, erro) = acesso_storage_windows(dados_storage)
    if not sucesso:
        print("- Acesso ao storage " + nome_storage + " falhou")
        print("- Verifique se servidor de storage está ativo e acessível (rede)")
        print("- Sugestão: Conecte no servidor via VNC com a conta consulta")
        return None

    # Ok, tudo certo
    print("- Acesso ao storage confirmado")
    return ponto_montagem


def troca_situacao_tarefa_ok(codigo_tarefa, codigo_nova_situacao, texto_status='', dados_relevantes=None):
    # Troca situação da tarefa
    # ------------------------
    try:
        sapisrv_troca_situacao_tarefa_obrigatorio(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=codigo_nova_situacao,
            texto_status=texto_status,
            dados_relevantes=dados_relevantes)
    except BaseException as e:
        print("- Não foi possível atualizar situação da tarefa")
        print_falha_comunicacao()
        print_comando_cancelado()
        return False

    # Tudo certo
    return True


def registra_processo_filho(ix, proc):
    global Gpfilhos

    # Armazena processo na lista processos filhos
    Gpfilhos[ix] = proc


# ======================================================================================================================
# @*cr - Copia relatórios do UFED/Cellebrite para storage
# ======================================================================================================================
# Chama copia e intercepta/trata ctr-c
def copiar_relatorio_cellebrite():
    console_executar_tratar_ctrc(funcao=_copiar_relatorio_cellebrite)

def _copiar_relatorio_cellebrite():
    print()
    print("- Cópia de relatório Cellebrite para storage.")

    # Carrega situação atualizada da tarefa
    # -----------------------------------------------------------------------------------------------------------------
    tarefa = carrega_exibe_tarefa_corrente()
    if tarefa is None:
        return False

    # Verificações preliminares
    # -----------------------------
    codigo_tarefa = tarefa['codigo_tarefa']
    item = tarefa['dados_item']


    # Verifica se tarefa tem o tipo certo
    # ------------------------------------
    if (not tarefa["tipo"] == "extracao"):
        # Isto aqui não deveria acontecer nunca...mas para garantir...
        print("Tarefa do tipo [", tarefa["tipo"], "] não pode ser resolvida por sapi_cellebrite")
        return

    # Verifica se tarefa possui situação coerente para execução
    # ---------------------------------------------------------
    codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
    if (codigo_situacao_tarefa == GAguardandoPCF or codigo_situacao_tarefa == GAbortou):
        # Tudo bem, prossegue
        prosseguir = True
    elif codigo_situacao_tarefa == GEmAndamento:
        print()
        print_atencao()
        print("- Esta tarefa está em andamento.")
        print()
        print(
            "- Se você deseja realmente deseja reiniciar esta tarefa, primeiramente será necessário abortar a mesma (comando *AB).")
        print()
        prosseguir = pergunta_sim_nao(
            "< Você deseja abortar esta tarefa (para em seguida reiniciar)?",
            default="n")
        if not prosseguir:
            return

        # Invoca rotina para abortar tarefa
        abortar_tarefa()

        return
    else:
        # Tarefas com outras situações não são permitidas
        print("- Tarefa com situação ", codigo_situacao_tarefa, "-",
              tarefa['descricao_situacao_tarefa'] + " NÃO pode ser processada")
        print("- Apenas tarefas com situação 'Aguardando ação PCF' ou 'Abortada' podem ser processadas")
        print("- Se você quer reexecutar esta tarefa, utilize o comando *RI")
        print("- Em caso de divergência, efetue em Refresh na lista de tarefas (*SG)")
        return

    # ------------------------------------------------------------------
    # Verifica se tarefa está com o status correto
    # ------------------------------------------------------------------
    if (int(tarefa["codigo_situacao_tarefa"]) == GFinalizadoComSucesso):
        # Isto aqui não deveria acontecer nunca...mas para garantir...
        print("Cancelado: Tarefa já foi finalizada com sucesso.")
        print()
        print("Caso seja necessário refazer esta tarefa, utilize a opção de *RI.")
        return

    # Divisão em dua partes, pois depois do tinker
    # tem que "renovar" o try para capturar o keyboarInterrupt
    caminho_origem = _copia_cellebrite_parte1()
    if (caminho_origem == ''):
        # Se não selecionou nada, pede novamente
        print()
        print("- Cancelado: Nenhuma pasta de origem selecionada.")
        return

    # Chama segunda parte, recapturando o CTR-C
    try:
        return _copia_cellebrite_parte2(tarefa, caminho_origem)
    except KeyboardInterrupt:
        print()
        print("Operação interrompida pelo usuário com <CTR>-<C>")
        return False


def _copia_cellebrite_parte1():
    # ------------------------------------------------------------------
    # Seleciona e valida pasta local de relatórios
    # ------------------------------------------------------------------
    # Solicita que usuário informe a pasta local que contém
    # os relatórios do Cellebrite para o item corrente
    caminho_origem = ""

    print()
    print("1) Pasta de relatórios cellebrite")
    print("=================================")
    print(
        "- Na janela gráfica que foi aberta, selecione a pasta que contém os relatórios cellebrite relativos ao item desta tarefa.")
    print("- Os arquivos de relatórios devem estar posicionados imediatamente abaixo da pastas informada.")

    # Solicita a pasta de origem
    # Cria janela para seleção de laudo
    root = tkinter.Tk()
    j = Janela(master=root)
    caminho_origem = j.selecionar_pasta()
    root.quit()
    root.destroy()

    return caminho_origem


# Segunda parte
def _copia_cellebrite_parte2(tarefa, caminho_origem):

    codigo_tarefa = tarefa['codigo_tarefa']
    item = tarefa['dados_item']

    # Se existe o problema de cópia em andamento,
    # dá opção para renomear
    arquivo = "Relatório.xml_em_copia"
    if arquivo_existente(caminho_origem, arquivo):
        print()
        print_log("Detectado presença de arquivo xml_em_copia")
        print_atencao()
        print("- Detectou-se que o procedimento de cópia desta pasta já foi iniciado anteriormente, ")
        print("  pois existe na pasta um arquivo com nome: ", arquivo)
        print("- Isto é normal se houve uma tentativa de cópia anterior que foi interrompida.")
        print("- Caso contrário, algo estranho está acontecendo. ")
        print("- Identifique a causa desta anomalia antes de prosseguir.")
        print("- Dica:")
        print("  => Tem certeza que você selecionou a A PASTA CORRETA para o item indicado ?")
        print()
        print(
            "- Se você decidir prosseguir, o arquivo xml_em_copia será renomeado para xml, para permitir o reinício.")
        print()
        prosseguir = pergunta_sim_nao("< Prosseguir?", default="n")
        if not prosseguir:
            return
        print()
        # Renomeia e prossegue
        de = os.path.join(caminho_origem, "Relatório.xml_em_copia")
        para = os.path.join(caminho_origem, "Relatório.xml")
        print_log("Usuário indicou que arquivo xml_em_copia deve ser renomeado e cópia deve prosseguir")
        os.rename(de, para)
        print_log("Renomeado ", de, " para ", para)

    # Verificação básica da pasta, para ver se contém os arquivos típicos
    print()

    print("2) Validação da pasta de relatórios")
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


    # Verifica se o arquivo XML contido na pasta de origem está ok
    arquivo_xml = caminho_origem + "/Relatório.xml"
    print("- Validando arquivo XML: ")
    print(" ", arquivo_xml)
    print("- Isto pode demorar alguns minutos, dependendo do tamanho do arquivo. Aguarde...")
    (resultado, dados_relevantes, erros, avisos) = processar_arquivo_xml(
        arquivo=arquivo_xml,
        numero_item=item["item"],
        explicar=False
    )
    if (not resultado):
        # A mensagem de erro já foi exibida pela própria função de validação
        for mensagem in erros:
            print("* ERRO: ", mensagem)
        return False

    print("- XML válido.")
    print()

    # ------------------------------------------------------------------------------------------------------------------
    # Conferência de dados
    # ------------------------------------------------------------------------------------------------------------------
    print("3) Conferência de dados extraídos para laudo")
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
    prosseguir = pergunta_sim_nao("< Dados ok? ", default="n")
    if not prosseguir:
        return

    # -----------------------------------------------------------------
    # Pasta de destino
    # -----------------------------------------------------------------
    print()
    print("4) Verificando pasta de destino")
    print("================================")

    print("- Storage da tarefa: ", tarefa["dados_storage"]["maquina_netbios"])

    # Montagem de storage
    # -------------------
    # Confirma que tem acesso ao storage escolhido
    # print("- Verificando conexão com storage de destino. Aguarde...")
    ponto_montagem = conectar_ponto_montagem_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return

    caminho_destino = ponto_montagem + tarefa["caminho_destino"]

    print("- Pasta de destino no storage:")
    print(" ", tarefa["caminho_destino"])

    # Verifica se pasta de destino já existe
    limpar_pasta_destino_antes_copiar = False
    if os.path.exists(caminho_destino):
        print_log("Pasta de destino contém arquivos")
        print()
        print("- IMPORTANTE: A pasta de destino JÁ EXISTE")
        print()
        print("- Não é possível iniciar a cópia nesta situação.")
        print("- Se o conteúdo atual da pasta de destino não tem utilidade,",
              "autorize a limpeza da pasta (opção abaixo).")
        print(
            "- Se você entende que os dados na pasta de destino já estão ok (e não devem ser apagados), cancele este comando")
        print("  e em seguida utilize o comando *cs para validar a pasta e atualizar a situação da tarefa.")
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
        print()
        print("- Confira se a pasta de destino está bem formada, ou seja, se o memorando e o item estão ok,")
        print("  pois será assim que ficará na mídia de destino.")
        print("- IMPORTANTE: Se a estrutura não estiver ok (por exemplo, o item está errado), cancele comando,")
        print("  ajuste no SETEC3 e depois retome esta tarefa.")
        print()
        prosseguir = pergunta_sim_nao("< Estrutura da pasta está ok?", default="n")
        if not prosseguir:
            return

    # ------------------------------------------------------------------------------------------------------------------
    # Efetuar cópia
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("5) Efetuar cópia")
    print("================")
    print()
    print("- Está tudo pronto para iniciar cópia.")
    prosseguir = pergunta_sim_nao("< Prosseguir? ", default="n")
    if not prosseguir:
        return

    # Troca situação da tarefa
    # ------------------------
    texto_status = "Preparando para copiar " + caminho_origem + " para " + caminho_destino
    if not troca_situacao_tarefa_ok(codigo_tarefa=codigo_tarefa,
                                    codigo_nova_situacao=GEmAndamento,
                                    texto_status=texto_status
                                    ):
        # Se falhar, encerra. Mensagens já foram dadas na função chamada
        return

    # ------------------------------------
    # Inicia procedimentos em background
    # ------------------------------------
    print_log("Iniciando cópia em background")
    # Os processo filhos irão atualizar o mesmo arquivo log do processo pai
    nome_arquivo_log_para_processos_filhos = obter_nome_arquivo_log()

    # Inicia processo filho para execução da cópia
    # ------------------------------------------------------------------------------------------------------------------
    label_processo = "executar:" + str(codigo_tarefa)
    dados_pai_para_filho=obter_dados_para_processo_filho()
    p_executar = multiprocessing.Process(
        target=background_executar_copia,
        args=(codigo_tarefa, caminho_origem, caminho_destino,
              dados_relevantes, limpar_pasta_destino_antes_copiar,
              nome_arquivo_log_para_processos_filhos, label_processo,
              dados_pai_para_filho)
    )
    p_executar.start()

    registra_processo_filho(label_processo, p_executar)

    # Inicia processo filho para acompanhamento da cópia
    # ------------------------------------------------------------------------------------------------------------------
    label_processo = "acompanhar:" + str(codigo_tarefa)
    p_acompanhar = multiprocessing.Process(
        target=background_acompanhar_copia,
        args=(codigo_tarefa, caminho_origem, caminho_destino, nome_arquivo_log_para_processos_filhos, label_processo))
    p_acompanhar.start()

    registra_processo_filho(label_processo, p_acompanhar)

    # Tudo certo, agora é só aguardar
    print()
    print("- Ok, procedimento de cópia foi iniciado em background.")
    print("- Você pode continuar trabalhando, inclusive efetuar outras cópias simultaneamente.")
    print("- Para acompanhar a situação da cópia, utilize o comando *SG, ou então *SGR (repetitivo)")
    print("- Também é possível acompanhar a situação através do SETEC3")
    print("- Em caso de problema/dúvida, utilize *EL para visualizar o log")
    print("- IMPORTANTE: Não encerre este programa enquanto houver cópias em andamento, ")
    print("  pois as mesmas serão interrompidas e terão que ser reiniciadas")

    exibir_situacao_apos_comando()

    return


# Efetua a cópia de uma pasta
def background_executar_copia(codigo_tarefa, caminho_origem, caminho_destino,
                              dados_relevantes, limpar_pasta_destino_antes_copiar,
                              nome_arquivo_log, label_processo,
                              dados_pai_para_filho):

    # Impede interrupção por sigint
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Inicializa sapilib
    # Será utilizado o mesmo arquivo de log do processo pai
    sapisrv_inicializar(Gprograma, Gversao, nome_arquivo_log=nome_arquivo_log, label_processo=label_processo)

    # Restaura dados herdados do processo pai
    restaura_dados_no_processo_filho(dados_pai_para_filho)

    # ------------------------------------------------------------------
    # Conceito:
    # ------------------------------------------------------------------
    # Utiliza xml como sinalizador de cópia concluída.
    # Incialmente ele é renomeado.
    # Quando a cópia for concluída ele volta ao nome original.
    # Esta operação visa garantir que outras checagens de estado
    # (por exemplo o comando *cs) entenda que a cópia ainda não acabou
    # Só quando a extensão for restaurada para xml o sistema entenderá
    # que a cópia acabou

    arquivo_xml_origem = caminho_origem + "/Relatório.xml"
    arquivo_xml_origem_renomeado = arquivo_xml_origem + "_em_copia"
    sucesso=False
    try:
        # 1) Marca início em background
        print_log("Início da cópia em background para tarefa", codigo_tarefa)

        # 2) Exclui pasta de destino antes de iniciar, se necessário
        # ------------------------------------------------------------------
        if limpar_pasta_destino_antes_copiar:
            texto_status = "Excluindo pasta de destino"
            sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)
            # Exclui pasta de destino
            shutil.rmtree(caminho_destino, ignore_errors=True)
            # Ok, exclusão concluída
            texto_status = "Pasta de destino excluída"
            sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)

        # 3) Determina características da pasta de origem
        # ------------------------------------------------
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, "Calculando tamanho da pasta de origem")
        # Registra características da pasta de origem
        carac_origem = obter_caracteristicas_pasta(caminho_origem)
        tam_pasta_origem = carac_origem.get("tamanho_total", None)
        if tam_pasta_origem is None:
            # Se não tem conteúdo, aborta...
            # Isto não deveria acontecer nunca....
            raise ("Pasta de origem com tamanho indefinido")

        # Atualiza status com características da pasta de origem
        texto_status = "Pasta de origem com " + converte_bytes_humano(tam_pasta_origem) + \
                       " (" + str(carac_origem["quantidade_arquivos"]) + " arquivos)"
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)

        # 4) Renomeia o arquivo XML na pasta de origem (nome temporário)
        # ------------------------------------------------------------------
        print_log("Renomeando arquivo ", arquivo_xml_origem, " para ", arquivo_xml_origem_renomeado)
        print_log("No final da cópia o nome original será restaurado")
        os.rename(arquivo_xml_origem, arquivo_xml_origem_renomeado)
        print_log("Renomeado com sucesso")

        # 5) Executa a cópia
        # ------------------------------------------------------------------
        texto_status = "Copiando"
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)
        shutil.copytree(caminho_origem, caminho_destino)
        texto_status = "Cópia finalizada"
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)

        # 6) Restaura o nome do arquivo XML na pasta destino
        # ------------------------------------------------------------------
        arquivo_xml_destino = caminho_destino + "/Relatório.xml_em_copia"
        arquivo_xml_destino_renomeado = caminho_destino + "/Relatório.xml"
        print_log("Restaurado nome de arquivo '",
                  arquivo_xml_destino, "' para '", arquivo_xml_destino_renomeado, "'")
        os.rename(arquivo_xml_destino, arquivo_xml_destino_renomeado)
        print_log("Renomeado com sucesso na pasta de destino")

        # 7) Restaura o nome do arquivo XML na pasta origem
        # ------------------------------------------------------------------
        arquivo_xml_origem = caminho_origem + "/Relatório.xml_em_copia"
        arquivo_xml_origem_renomeado = caminho_origem + "/Relatório.xml"
        print_log("Restaurado nome de arquivo '",
                  arquivo_xml_origem, "' para '", arquivo_xml_origem_renomeado, "'")
        os.rename(arquivo_xml_origem, arquivo_xml_origem_renomeado)
        print_log("Renomeado com sucesso na pasta de origem")

        # 8) Confere se cópia foi efetuada com sucesso
        # ------------------------------------------------------------------
        # Compara tamanho total e quantidade de arquivos
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, "Conferindo cópia (tamanho e quantidade de arquivos)")

        carac_destino = obter_caracteristicas_pasta(caminho_destino)
        if carac_origem["tamanho_total"]==carac_destino["tamanho_total"]:
            print_log("Tamanho total confere")
        else:
            print("Divergência entre tamanho total de origem (",carac_origem["tamanho_total"],") e destino (",carac_origem["tamanho_total"],")")
            raise "Divergência de tamanho"

        if carac_origem["quantidade_arquivos"]==carac_destino["quantidade_arquivos"]:
            print_log("Quantidade de arquivos confere")
        else:
            print("Divergência de quantidade de arquivos entre origem (", carac_origem["quantidade_arquivos"], ") e destino (",
                  carac_origem["quantidade_arquivos"], ")")
            raise "Divergência de quantidade de arquivos"

        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, "Tamanho total e quantidade de arquivos compatíveis")

        # Se chegou aqui, sucesso
        print_log("Cópia concluída com sucesso")
        sucesso=True

    except BaseException as e:
        # Erro fatal: Mesmo estando em background, exibe na tela
        print_tela_log("- [1723] ** ERRO na tarefa",codigo_tarefa, "durante cópia:" + str(e))
        print("- Consulte log para mais informações")
        sucesso=False

    # -----------------------------------------------------------------------------------------------------------------
    # COPIA COM ERRO
    # -----------------------------------------------------------------------------------------------------------------
    if not sucesso:
        try:
            # Troca para situação Abortada
            # -----------------------------------
            sapisrv_troca_situacao_tarefa_obrigatorio(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=GAbortou,
                texto_status="Cópia falhou. NÃO foi concluída com sucesso")
        except BaseException as e:
            # Se não conseguiu trocar a situação, avisa que usuário terá que abortar manualmente
            print_tela_log("- [1826] Não foi possível abortar a tarefa",codigo_tarefa, "automaticamente")
            print_tela_log("- Cópia falhou, e além disso, quando o sistema tentou atualizar situação para 'Abortada', isto também falhou")
            print_tela_log("- Tarefa está em situação inconsistente, como se estive executando, mas na realidade já foi abortada")
            print_tela_log("- Será necessário abortar manualmente (comando *AB)")
            print_falha_comunicacao()
            # Prossegue por gravidade, pois está em background e irá encerrar logo em seguida

        # Encerra
        sys.exit(0)

    # -----------------------------------------------------------------------------------------------------------------
    # Cópia finalizada com sucesso
    # -----------------------------------------------------------------------------------------------------------------
    try:
        # Troca para situação finalizada
        # -----------------------------------
        sapisrv_troca_situacao_tarefa_obrigatorio(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=GFinalizadoComSucesso,
            texto_status="Dados copiados com sucesso para pasta de destino",
            dados_relevantes=dados_relevantes)
        print_log("Situação da tarefa atualizada com sucesso")
    except BaseException as e:
        print_tela_log("- Cópia da tarefa", codigo_tarefa,"foi concluída")
        print_tela_log("- Contudo, NÃO FOI POSSÍVEL possível atualizar situação para 'Sucesso'")
        print_tela_log("- Esta tarefa ficará em estado inconsistente, pois para o sistema ainda está em execução")
        print("- Após sanar o problema, utilize comando *cs para atualizar situação da tarefa")
        print_falha_comunicacao()
        sys.exit(0)

    # Tudo certo
    print("- Tarefa", codigo_tarefa, "finalizada com SUCESSO")
    print("- Utilize comando *SG para conferir a situação atual da tarefa")
    print_log("Fim da cópia em background para tarefa", codigo_tarefa)
    sys.exit(0)

# Acompanhamento de copia em background
def background_acompanhar_copia(codigo_tarefa, caminho_origem, caminho_destino, nome_arquivo_log, label_processo):

    # Impede interrupção por sigint
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Inicializa sapilib, compartilhando o arquivo de log do processo principal
    sapisrv_inicializar(Gprograma, Gversao, nome_arquivo_log=nome_arquivo_log, label_processo=label_processo)
    print_log("Processo de acompanhamento de cópia iniciado")

    # Executa, e se houver algum erro, registra em log
    try:

        # simula erro
        #i=5/0

        _background_acompanhar_copia(codigo_tarefa, caminho_origem, caminho_destino, nome_arquivo_log)

    except BaseException as e:
        # Erro fatal: Mesmo que esteja em background, exibe na tela
        print()
        print("*** Acompanhamento de cópia falhou, consulte log para mais informações ***")
        print_log("*** Erro *** em acompanhamento de cópia: ", str(e))

    # Encerra normalmente
    print_log("Processo de acompanhamento de cópia finalizado")
    sys.exit(0)


# Processo em background para efetuar o acompanhamento da cópia
def _background_acompanhar_copia(codigo_tarefa, caminho_origem, caminho_destino, nome_arquivo_log):

    # intervalo entre as atualizações
    pausa=15

    # Recupera características da pasta de origem
    r=obter_caracteristicas_pasta(caminho_origem)
    tam_pasta_origem = r.get("tamanho_total", None)
    if tam_pasta_origem is None:
        # Se não tem conteúdo, encerrra....Não deveria acontecer nunca
        raise("[2027] Falha na obtençao do tamanho da pasta de origem")

    # Avisa que vai começar
    print_log("A cada ", GtempoEntreAtualizacoesStatus, "segundos será atualizado o status da cópia")

    # Fica em loop enquanto tarefa estiver em situação EmAndamento
    tamanho_anterior=-1
    while True:

        # Intervalo entre atualizações de status
        time.sleep(pausa)

        # Verifica se tarefa ainda está em estado de Andamento
        tarefa=recupera_tarefa_do_setec3(codigo_tarefa)
        if tarefa is not None:
            codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
            if codigo_situacao_tarefa != GEmAndamento:
                print_log("Verificado que situação da tarefa",codigo_tarefa,"foi modificada para",codigo_situacao_tarefa,". Encerrando acompanhamento.")
                return

        # Aumenta o tempo de pausa a cada atualização de status
        # sem ultrapassar o máximo
        pausa = round(pausa * 1.2)
        if pausa > GtempoEntreAtualizacoesStatus:
            # Pausa nunca será maior que o limite estabelecido
            pausa = GtempoEntreAtualizacoesStatus

        debug("Novo ciclo de acompanhamento de tarefa")

        # Verifica o tamanho atual da pasta de destino
        try:
            tamanho_copiado = tamanho_pasta(caminho_destino)
        except OSError as e:
            # Quando a pasta está sendo excluída, é comum que o procedimento
            # de verificação de tamanho falhe,
            # pois quando ele vai pegar as propriedades de um arquivo, o mesmo foi excluído pelo outro processo
            debug("[1825] Ignorando erro: ",str(e))
            # Deve estar excluindo...Logo, vamos dar uma pausa adicional aqui, e aguardar....
            time.sleep(GtempoEntreAtualizacoesStatus)
            continue

        # Só atualiza, se já tem algo na pasta
        # e se o tamanho atual é maior que o tamanho anterior
        # Ou seja, o primeiro tamanho (da primeira iteração) não será atualizado
        # Além disso, não atualiza se o tamanho estiver diminuindo
        # Isto evita atualizar quando o tamanho está diminuindo, durante a exclusão da pasta
        if tamanho_copiado>0 and tamanho_anterior>0 and tamanho_copiado>tamanho_anterior:

            tamanho_copiado_humano = converte_bytes_humano(tamanho_copiado)

            # Atualiza status
            percentual = (tamanho_copiado / tam_pasta_origem) * 100
            texto_status = tamanho_copiado_humano + " (" + str(round(percentual, 1)) + "%)"
            print_log(texto_status)
            sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)

            if percentual>=100:
                print_log("Encerrando acompanhamento, pois foi atingido 100%")
                return

        # Guarda tamanho atual
        tamanho_anterior=tamanho_copiado

# *cr - fim ----------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# @*cs - Compara situação (servidor x storage)
# ----------------------------------------------------------------------------------------------------------------------
def comparar_sistema_com_storage():
    console_executar_tratar_ctrc(funcao=_comparar_sistema_com_storage)

# Retorna tupla:
#   1) codigo_situacao_tarefa: Retorna o código da situação.
#      Se operação falhou, retorna -1 ou nulo
#      -1 ou nulo: Comando não foi executado
#   2) texto_situacao: Texto complementar da situação
#   3) dados_relevantes: Dados relevantes, para utilização em laudo
# ----------------------------------------------------------------------
def determinar_situacao_no_storage(tarefa):
    # Constantes de codigo_situacao
    erro_interno = -1
    erros = list()
    avisos = list()
    status = ""

    # Elementos que serão utilizados posteriormente
    codigo_tarefa=tarefa['codigo_tarefa']
    item=tarefa['dados_item']

    # Montagem de storage
    # -------------------
    # Confirma que tem acesso ao storage escolhido
    ponto_montagem=conectar_ponto_montagem_storage_ok(tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return (erro_interno, status, {}, erros, avisos)


    # Verifica se pasta de destino existe
    # -----------------------------------
    caminho_destino = ponto_montagem + tarefa["caminho_destino"]
    if not os.path.exists(caminho_destino):
        status = "Não iniciado (sem pasta)"
        print("- Pasta de destino ainda não foi criada.")
        return (GSemPastaNaoIniciado, status, {}, erros, avisos)  # Não iniciado

    print("- Pasta de destino existente.")

    # Verificação básica da pasta, para ver se contém os arquivos típicos
    # --------------------------------------------------------------------
    (erros, avisos) = valida_pasta_relatorio_cellebrite(pasta=caminho_destino, explicar=True)
    if len(erros) > 0:
        status = "Na pasta de destino no storage estão faltando arquivos básicos."
        codigo_status = GEmAndamento
        print("-",status)
        return (codigo_status, status, {}, erros, avisos)

    # Ok, já tem todos os arquivos básicos
    status = "Pasta contém todos os arquivos básicos."
    print("-",status)

    # Valida arquivo xml
    print("- Validando Relatório.XML. Isto pode demorar, dependendo do tamanho do arquivo. Aguarde...")
    arquivo_xml = caminho_destino + "/Relatório.xml"
    (resultado, dados_relevantes, erros, avisos) = processar_arquivo_xml(
        arquivo=arquivo_xml,
        numero_item=item["item"],
        explicar=True
    )
    if (not resultado):
        status = "Arquivo XML inconsistente"
        codigo_status = GAbortou
        print("-",status)
        return (codigo_status, status, {}, erros, avisos)

    # Exibe o resultado dos dados coletados para laudo
    print("- XML válido.")
    print("- Os seguintes dados foram selecionados do XML armazenado armazenado no Storage e serão utilizados em laudo:")
    exibir_dados_laudo(dados_relevantes['laudo'])

    # No storage aparentemente está tudo ok
    status = "Relatório Cellebrite armazenado com sucesso"
    codigo_status = GFinalizadoComSucesso
    return (codigo_status, status, dados_relevantes, erros, avisos)


def _comparar_sistema_com_storage():

    print()
    print("- Comparar situação da tarefa, verificando compatibilidade entre Setec3 com dados no Storage")

    # Carrega situação atualizada da tarefa
    # -----------------------------------------------------------------------------------------------------------------
    tarefa = carrega_exibe_tarefa_corrente()
    if tarefa is None:
        return False

    codigo_tarefa=tarefa['codigo_tarefa']
    codigo_situacao_setec3 = int(tarefa["codigo_situacao_tarefa"])

    # Label para diferenciar mensagens de log
    definir_label_log('*cs:'+codigo_tarefa)


    # Se tarefa está sendo executada, não permite comparação
    # -------------------------------------------
    if codigo_situacao_setec3 == GEmAndamento:
        # Tarefas com outras situações não são permitidas
        print("- Esta tarefa está em execução. Desta forma, não é possível fazer a comparação de situação")
        print("- Para efetuar a comparação, será primeiro necessário abortar a tarefa (*AB).")
        print("- Comando cancelado.")
        return False

    # Determina a situação da tarefa no storage
    # -----------------------------------------
    (codigo_situacao_storage, texto_status, dados_relevantes, erros, avisos) = determinar_situacao_no_storage(tarefa)
    # Se falhou, encerra (o motivo já foi explicado no chamado)
    if (codigo_situacao_storage == -1):
        print("- Não foi possível determinar a situação da tarefa no storage")
        print("- Comando cancelado")
        return

    # Exibe situação no storage
    print()
    print("- Situação no SETEC3            : ", tarefa["codigo_situacao_tarefa"],"-", tarefa['descricao_situacao_tarefa'])
    print("- Situação observada no storage : ", str(codigo_situacao_storage), "-", texto_status)

    # Compara situação do SETEC3 com situação do storage
    # --------------------------------------------------

    # Se a situação é mesma, está tudo certo
    # --------------------------------------
    if (codigo_situacao_storage == codigo_situacao_setec3):
        print()
        print("- Situação observada na pasta de destino está coerente com a situação do servidor.")
        return

    # Se no storage está em andamento (tem alguns arquivos)
    # e no servidor está abortada, tudo bem, faz sentido
    if (    (codigo_situacao_storage == GEmAndamento)
        and (codigo_situacao_setec3 == GAbortou)):
        print()
        print("- Situação observada na pasta de destino está coerente com a situação do servidor.")
        print("- Tarefa foi abortada sem ser concluída.")
        return

    # Se no storage está em andamento (tem alguns arquivos)
    # e no servidor está aguardando PCF, talvez tenha sido reinicida, tudo bem, faz sentido
    if (    (codigo_situacao_storage == GEmAndamento)
        and (codigo_situacao_setec3 == GAguardandoPCF)):
        print()
        print("- Situação observada na pasta de destino está coerente com a situação do servidor.")
        print("- Possivelmente tarefa foi reiniciada.")
        return

    # Se a situação no storage é menor que no setec3, tem alguma inconsistência...ou falha na verificação
    if (codigo_situacao_storage < codigo_situacao_setec3):
        print()
        print("- Situação observada é divergente da situação reportada pelo servidor.")
        print("- Reporte esta situação ao desenvolvedor (ponto2184).")
        return

    # Se houver divergência entre situação atual e situação no servidor
    # pergunta se deve atualizar
    print()
    print_atencao()
    print('- A situação da tarefa no SETEC3 não está coerente com a situação observada na pasta de destino do storage.')
    print('- Isto pode ocorrer caso tenha havido alguma falha no procedimento')
    print('  de atualização da situação após a cópia no sapi_cellebrite.')
    print()
    print('- Caso você tenha certeza que os dados armazenados no servidor estão ok,')
    print('  basta efetuar a atualização do situação (respondendo S na próxima pergunta)')
    print('- Em caso de dúvida, refaça a cópia (comando *CR)')
    print()
    atualizar = pergunta_sim_nao("< Atualizar SETEC3 com a situação observada no storage? ", default="n")
    if (not atualizar):
        return

    # Troca situação da tarefa
    # ------------------------
    if not troca_situacao_tarefa_ok(codigo_tarefa=codigo_tarefa,
                                    codigo_nova_situacao=codigo_situacao_storage,
                                    texto_status="Dados confirmados no storage (PCF comando *CS)",
                                    dados_relevantes=dados_relevantes
                                    ):
        # Se falhar, encerra. Mensagens já foram dadas na função chamada
        return

    # Tudo certo
    # ----------
    print()
    print("- Tarefa atualizada com sucesso no servidor")
    exibir_situacao_apos_comando()

    return


def exibir_situacao_apos_comando():
    print()
    espera_enter("<ENTER> para prosseguir. Será exibida a situação atualizada das tarefas ")
    refresh_tarefas()
    exibir_situacao()


# Linha geral de cabeçalho
def print_linha_cabecalho():

    # ambiente de execução
    ambiente = obter_ambiente()
    if ambiente == 'PRODUCAO':
        ambiente = ''
    else:
        ambiente = "@" + ambiente
    # Dados identificadores
    print(GdadosGerais.get("identificacaoObjeto", None), "|",
          GdadosGerais.get("pcf", None), "|",
          GdadosGerais.get("data_hora_ultima_atualizacao_status", None), "|",
          Gprograma + str(Gversao),
          ambiente)
    print_centralizado()

# Exibe lista de tarefas
# ----------------------------------------------------------------------
def exibir_situacao(comando=''):

    # Cabeçalho da lista de elementos
    # --------------------------------------------------------------------------------
    cls()
    print_linha_cabecalho()

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

        # Calcula largura da última coluna, que é variável (item : Descrição)
        # Esta constantes de 60 é a soma de todos os campos e espaços antes do campo "Item : Descrição"
        lid = Glargura_tela - 58
        lid_formatado = "%-" + str(lid) + "." + str(lid) + "s"

        string_formatacao = '%2s %2s %6s %-30.30s %-13s ' + lid_formatado

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
            # print('    ' + "'"*59)
            # print('    ' + "^")
            print_centralizado()

    print()
    if comando=='':
        print("- Dica: Para recuperar a situação atualizada do servidor (Refresh), utilize os comando *SG ou *SGR (repetitivo)")

    return


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

    if filtro_usuario=="":
        print()
        print("- Dica: Para filtrar o log, forneça um string após comando.")
        print("  Exemplo: ",comando," erro => Lista apenas linhas que contém o termo 'erro'")

    return


# Salva situação atual para arquivo
# ----------------------------------------------------------------------
def salvar_estado():

    # Desabilitado...acho que não vai ser necessário
    return

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



# ----------------------------------------------------------------------
# @*TT - Usuário seleciona a solicitação de exame
# ----------------------------------------------------------------------
def obter_solicitacao_exame():
    console_executar_tratar_ctrc(funcao=_obter_solicitacao_exame)

# Carrega situação de arquivo
# ----------------------------------------------------------------------
def _obter_solicitacao_exame():
    # Irá atualizar a variáel global de tarefas
    global Gtarefas

    # Cabeçalho
    print()
    print("Seleção de solicitação de exame")
    print("======================================")
    print("Dica: Para interromper, utilize CTR-C")
    print("")

    # Solicita que o usuário se identifique através da matricula
    # ----------------------------------------------------------
    lista_solicitacoes = None
    while True:

        matricula = input("< Entre com sua matrícula: ")
        matricula = matricula.replace(".", "")
        matricula = matricula.lower().strip()

        if not matricula.isdigit():
            print("- Entre com seu número de matrícula (composto exclusivamente por dígitos)")
            continue

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
                print()
                continue

        except BaseException as e:
            # Provavel falha de comunicação
            print_falha_comunicacao()
            return False

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
    print("- Estas são as solicitações de exames que estão preparadas para serem executadas no SAPI.")
    print("- Se a solicitação de exame que você procura não está na lista, ")
    print("  vá para SETEC3 => Perícia => SAPI e prepare a solicitação, criando tarefas SAPI.")

    # Usuário escolhe a solicitação de exame de interesse
    # --------------------------------------------------------
    tarefas = None
    while True:
        #
        print()
        num_solicitacao = input(
            "< Selecione a solicitação de exame, indicando o número de sequencia (Sq) na lista acima: ")
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
        GdadosGerais["pcf"] = solicitacao["nome_curto_sujeito_posse"]

        print_log("Usuário escolheu ", GdadosGerais["identificacaoObjeto"])

        # Carrega as tarefas de extração da solicitação selecionada
        # --------------------------------------------------------
        codigo_solicitacao_exame_siscrim = solicitacao["codigo_documento_externo"]
        GdadosGerais["codigo_solicitacao_exame_siscrim"] = codigo_solicitacao_exame_siscrim

        if not refresh_tarefas():
            # Função chamada já exibiu esclarecimentos
            return False

        # Analisa as tarefas recuperadas
        # ------------------------------
        if (len(Gtarefas) == 0):
            print()
            print("- Solicitação de exame NÃO TEM NENHUMA TAREFA DE EXTRAÇÃO. Verifique no SETEC3.")
            print()
            # Continua no loop
            continue

        # Muda log para o arquivo com nome
        partes=solicitacao["identificacao"].split('-')
        nome_arquivo_log="log_sapi_cellebrite_"+partes[0]+"_"+solicitacao["codigo_documento_externo"]+".txt"
        # Sanitiza, removendo e trocando caracteres especiais
        nome_arquivo_log=nome_arquivo_log.replace('/','-')
        nome_arquivo_log=nome_arquivo_log.replace(' ','')

        definir_nome_arquivo_log(nome_arquivo_log)

        # Tudo certo, interrompe loop e retorna
        return True


def refresh_tarefas():
    # Irá atualizar a variáel global de tarefas
    global Gtarefas

    print()
    print("- Consultando situação de tarefas no SETEC3 para", GdadosGerais["identificacaoSolicitacao"], ": Aguarde...")

    codigo_solicitacao_exame_siscrim = GdadosGerais["codigo_solicitacao_exame_siscrim"]

    try:
        (sucesso, msg_erro, tarefas) = sapisrv_chamar_programa(
            "sapisrv_obter_tarefas.php",
            {'tipo': 'extracao',
             'codigo_solicitacao_exame_siscrim': codigo_solicitacao_exame_siscrim
             }
        )
    except BaseException as e:
        print_tela_log("- Não foi possível recuperar a situação atualizada das tarefas do servidor")
        return False

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


# Retorna True se realmente deve ser finalizado
def finalizar_programa():
    print()
    # Varre lista de processos filhos, e indica o que está rodando
    qtd_ativos = 0
    for ix in sorted(Gpfilhos):
        if Gpfilhos[ix].is_alive() and "executar" in ix:
            dummy, codigo_tarefa = ix.split(':')
            print("- Tarefa",codigo_tarefa, "ainda não foi concluída (está rodando em background - ",ix,Gpfilhos[ix].pid,")")
            qtd_ativos += 1

    # Se não tem nenhum programa em background
    # pode finalizar imediatamente
    if qtd_ativos == 0:
        return True

    # Pede confirmação, se realmente deve finalizar processos em background
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("- Se você finalizar o programa agora, estas tarefas serão canceladas e terão que ser reiniciadas.")
    print()
    prosseguir_finalizar = pergunta_sim_nao("< Deseja realmente finalizar programa? ", default="n")
    if not prosseguir_finalizar:
        # Não finaliza
        return False


    # Eliminando processos filhos que ainda estão ativos
    # --------------------------------------------------------------------------------------------------------------
    print_log("Usuário foi avisado que existem processos rodando, e respondeu que desejava encerrar mesmo assim")
    print("- Finalizando processos e ajustando situação de tarefas. Aguarde...")
    lista_tarefa_abortar = []
    for ix in sorted(Gpfilhos):
        if Gpfilhos[ix].is_alive():
            # Finaliza processo
            print_log("Finalizando processo ", ix, " [", Gpfilhos[ix].pid, "]")
            Gpfilhos[ix].terminate()
            # Se for uma tarefa, coloca na lista para na sequencia atualizar situação para abortada
            if "executar" in ix:
                dummy, codigo_tarefa = ix.split(':')
                lista_tarefa_abortar.append(codigo_tarefa)

    # Atualiza situação 'Abortada' para as tarefas cujos processos foram interrompidos
    # --------------------------------------------------------------------------------------------------------------
    for codigo_tarefa in lista_tarefa_abortar:
        try:
            sapisrv_troca_situacao_tarefa_obrigatorio(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=GAbortou,
                texto_status="Abortada (usuário comandou encerramento prematuro do programa)"
            )
            print_tela_log("- Tarefa", codigo_tarefa, "abortada devido a saída prematura do programa")
        except BaseException as e:
            print_tela_log("- Os processos relativos à tarefa", codigo_tarefa,"foram cancelados")
            print_tela_log("- Contudo, não foi possível atualizar a situação da tarefa ", codigo_tarefa, "para 'Abortada'")
            print_tela_log("- Tarefa", codigo_tarefa,"ficará em estado inconsistente, pois o servidor achará que ainda está rodando")
            print("- Posteriormente será necessário abortá-la manualmente (comando *AB)")

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


# ---------------------------------------------------------------------------------------------------------------------
# @*sgr - Exibição repetitiva da situação da lista de tarefas
# ---------------------------------------------------------------------------------------------------------------------
def exibir_situacao_repetir():

    print()
    print("- Entrando em modo de exibição contínua")
    try:

        intervalo = 60

        # Fica em loop, exibindo situação
        while True:
            if refresh_tarefas():
                exibir_situacao("*sgr")
                print()
                print("- Você está em modo *SGR, com refresh repetitivo da situação geral das tarefas a cada", intervalo, "segundos")
                print("- Utilize <CTR><C> para sair deste modo e voltar ao menu de comandos")
            time.sleep(intervalo)

    except KeyboardInterrupt:
        print()
        print("Saindo de modo *SGR")
        return

# ======================================================================
# Rotina Principal 
# ======================================================================


def main():

    #teste="-ABC"
    #print(ajusta_texto_saida(teste))
    #die('ponto3250')

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
    print("- Conectando com SETEC3. Aguarde...")
    print()

    # Inicialização de sapilib
    # -----------------------------------------------------------------------------------------------------------------
    nome_arquivo_log = "log_sapi_cellebrite.txt"
    sapisrv_inicializar_ok(Gprograma, Gversao, auto_atualizar=True, nome_arquivo_log=nome_arquivo_log)
    print_log('Inicializado com sucesso', Gprograma, ' - ', Gversao)

    # Teste
    #atualizar_status_tarefa_andamento(465, 'bla, bla')
    #atualizar_status_tarefa_andamento(465, 'status2')
    #die('ponto2832')

    # Carrega o estado anterior
    # -----------------------------------------------------------------------------------------------------------------
    carregar_estado()
    if len(Gtarefas) > 0:
        print("Retomando execução do último memorando. Para trocar de memorando, utilize opção *tt")
        refresh_tarefas()
    else:
        # Obtem lista de tarefas, solicitando o memorando
        if obter_solicitacao_exame():
            if len(Gtarefas)==0:
                # Se usuário interromper sem selecionar, finaliza
                print("- Execução finalizada.")
                # sys.exit()
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
            # Finaliza programa, mas antes verifica se tem algo rodando em background
            if finalizar_programa():
                # Finaliza
                print()
                print("- Finalizando por solicitação do usuário. Aguarde...")
                break
            else:
                # Continua recebendo comandos
                continue

        # Executa os comandos
        # -----------------------
        if (comando.isdigit()):
            # usuário digitou um número (do item)
            posicionar_item(comando)
            exibir_situacao()
        elif (comando == '+'):
            avancar_item()
            exibir_situacao()
        elif (comando == '-'):
            recuar_item()
            exibir_situacao()

        # Comandos de item
        if (comando == '*du'):
            dump_tarefa()
            continue
        elif (comando == '*cr'):
            copiar_relatorio_cellebrite()
            continue
        elif (comando == '*cs'):
            comparar_sistema_com_storage()
            continue
        elif (comando == '*ab'):
            abortar_tarefa()
            continue
        elif (comando == '*ri'):
            reiniciar_tarefa()
            continue
        elif (comando == '*ex'):
            excluir_tarefa()
            continue

        # Comandos gerais
        if (comando == '*sg'):
            if refresh_tarefas():
                exibir_situacao(comando)
            continue
        elif (comando == '*sgr'):
            exibir_situacao_repetir()
            continue
        elif (comando == '*lg'):
            exibir_log(comando='*lg', filtro_base='', filtro_usuario=argumento)
            continue
        elif (comando == '*lo'):
            exibir_log_tarefa(filtro_usuario=argumento)
            continue
        elif (comando == '*db'):
            if modo_debug():
                desligar_modo_debug()
                print("- Modo debug foi desligado")
            else:
                ligar_modo_debug()
                print("- Modo debug foi ligado")
            continue
        elif (comando == '*tt'):
            print_log("Usuário comandou troca de solicitação de exame (*TT)")
            if obter_solicitacao_exame():
                # Se trocou de memorando, Inicializa indice da tarefa corrente e exibe
                Gicor = 1
                salvar_estado()
                exibir_situacao()
                continue

                # Loop de comando

    # Encerrando conexão com storage
    print()
    desconectar_storage_windows()

    # Finaliza
    print()
    print("FIM SAPI Cellebrite - Versão: ", Gversao)


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
    # GdadosGerais["data_hora_ultima_atualizacao_status"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # var_dump(GdadosGerais["data_hora_ultima_atualizacao_status"])


    main()

    print()
    print("< Pressione qualquer tecla para concluir, ou feche a janela")
    espera_enter()
