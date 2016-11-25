﻿# -*- coding: utf-8 -*-
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
#
#
# Histórico:
#  - v1.0 : Inicial
# =======================================================================
# TODO: Como garantir que a cópia foi efetuada com sucesso? Hashes?
# TODO: XML está quase do tamanho do PDF (em alguns casos, fica bem grande).
#       Criar opção para excluir do destino? Excluir sempre?
# =======================================================================


# Módulos utilizados
# ====================================================================================================
# Baseado no PEP8, os imports tem que estar todos no ínicio do arquivo
# No entanto, neste caso, o if acima serve para testar se existe alguma incompatibilidade de versão
# E isto tem que ser feito bem no início, antes de qualquer outra coisa, inclusive dos imports,
# caso contrário pode ocorrer erro de runtime de um import que não existe no python2.7, por exemplo
from __future__ import print_function
import platform
import sys
import socket
import time
import xml.etree.ElementTree as ElementTree
import shutil
import tempfile
import multiprocessing

# Verifica se está rodando versão correta de Python
# ====================================================================================================
if sys.version_info <= (3, 0):
    sys.stdout.write("Versao do intepretador python (" + str(platform.python_version()) + ") incorreta.\n")
    sys.stdout.write("Este programa requer Python 3 (preferencialmente Python 3.5.2).\n")
    sys.exit(1)

# =======================================================================
# GLOBAIS
# =======================================================================

Gversao = "1.0"

Gdesenvolvimento = True  # Ambiente de desenvolvimento
# Gdesenvolvimento=False #Ambiente de producao

Gdebug = False

# Base de dados (globais)
GdadosGerais = {}  # Dicionário com dados gerais
Gtarefas = []  # Lista de tarefas

# Diversos sem persistência
Gicor = 1

# Controle de frequencia de atualizacao
# GtempoEntreAtualizacoesStatus = 180 # Tempo normal de produção
GtempoEntreAtualizacoesStatus = 10  # Debug: Gerar bastante log

# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi_lib_xxx.py, para evitar dependência
from sapilib_0_5_4 import *

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
def atualizar_status_tarefa(codigo_tarefa, codigo_situacao_tarefa, status, dados_relevantes=None):
    # Define nome do agente
    # xxxx@yyyy, onde xxx é o nome do programa e yyyy é o hostname
    nome_agente = os.path.basename(sys.argv[0]) + "@" + socket.gethostbyaddr(socket.gethostname())[0]

    # Parâmetros
    param = {'codigo_tarefa': codigo_tarefa,
             'codigo_situacao_tarefa': codigo_situacao_tarefa,
             'status': status,
             'execucao_nome_agente': nome_agente
             }
    if (dados_relevantes is not None):
        dados_relevantes_json = json.dumps(dados_relevantes, sort_keys=True)
        param['dados_relevantes_json'] = dados_relevantes_json

    # Invoca sapi_srv
    (sucesso, msg_erro, resultado) = sapisrv_chamar_programa(
        "sapisrv_atualizar_tarefa.php", param)

    # Retorna resultado
    if (sucesso):
        return (True, '')
    else:
        return (False, msg_erro)


# Atualiza status da tarefa em andamento
# Não efetua verificação de erro, afinal este status é apenas informativo
def atualizar_status_tarefa_andamento(codigo_tarefa, texto_status):
    codigo_situacao_tarefa = GEmAndamento
    print_log("Atualizando tarefa ", codigo_tarefa, "em andamento com status: ", texto_status)
    (ok, msg_erro) = atualizar_status_tarefa(
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
        if_print_ok(explicar, mensagem)
    d_aquis_geral['reportVersion'] = report_version

    # Nome do projeto
    name = a.get('name', None)
    if (numero_item not in name):
        # Se o nome do projeto está fora do padrão, emite apenas um aviso
        mensagem = ("Nome do projeto (" + name + ") não contém referência ao item de exame. "
                    + "Para evitar confusão, recomenda-se que o nome do projeto contenha no seu nome o item de apreensão, "
                    + "algo como: 'Item" + numero_item + "'")
        avisos += [mensagem]
        if_print_ok(explicar, mensagem)
        # return (False, dados)
    d_aquis_geral['project_name'] = name

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
    qtd_extracao_aparelho = 0
    qtd_extracao_sim = 0
    qtd_extracao_sd = 0
    qtd_extracao_backup = 0
    qtd_extracao_total = 0
    for extractionInfo in root.iter(tag=ns + 'extractionInfo'):
        id_extracao = extractionInfo.get('id', None)
        dext[id_extracao] = {}

        nome_extracao = extractionInfo.get('name', None)
        dext[id_extracao]['extractionInfo_name'] = nome_extracao
        dext[id_extracao]['extractionInfo_type'] = extractionInfo.get('type', None)
        dext[id_extracao]['extractionInfo_IsPartialData'] = extractionInfo.get('IsPartialData', None)

        # Verifica se extração contém uma das palavras chaves
        termos_nome_extracao = ['aparelho', 'sim', 'sd', 'backup']
        achou = False
        for t in termos_nome_extracao:
            if (t not in nome_extracao.lower()):
                continue

            # Achou um dos termos
            achou = True
            qtd_extracao_total += 1

            # Aparelho
            if (t == 'aparelho'):
                qtd_extracao_aparelho += 1
                dext[id_extracao]['sapiAparelho'] = True
            # SIM
            if (t == 'sim'):
                qtd_extracao_sim += 1
                dext[id_extracao]['sapiSIM'] = True
            # Cartão de memória SD
            if (t == 'sd'):
                qtd_extracao_sd += 1
                dext[id_extracao]['sapiSD'] = True
            # Backup
            if (t == 'backup'):
                qtd_extracao_backup += 1
                dext[id_extracao]['sapiBackup'] = True

        # Extração com nome fora do padrão
        if (not achou):
            mensagem = ("Extração '" + nome_extracao +
                        "' com nome fora do padrão, pois não contém nenhum dos termos esperados (" +
                        ",".join(termos_nome_extracao) +
                        ")")
            avisos += [mensagem]
            if_print_ok(explicar, mensagem)

    # Acho que não vai precisar disto...pode contar pelo tipo
    # d_aquis_geral['qtd_extracao_aparelho']=qtd_extracao_aparelho
    # d_aquis_geral['qtd_extracao_sim']=qtd_extracao_sim
    # d_aquis_geral['qtd_extracao_sd']=qtd_extracao_sd
    # d_aquis_geral['qtd_extracao_backup']=qtd_extracao_backup


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
    # p = ns + "metadata/" + ns + "item" + "[@name='UFED_PA_Version']"
    # ufed_pa_version = None
    # if (root.find(p) is not None):
    #     ufed_pa_version = root.find(p).text

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
    # SIM Card => Sim Card
    # Mass Storage Device => SD
    # ?? Como fica para Backup...tem que aguardar ter um para ver
    # * (o restante) => Aparelho
    for i in dext:
        for n in dext[i]:
            die('ponto579')



    # Verifica conjunto de extrações
    # ------------------------------------------------------------------

    # Se tem algum erro na seção de extração, não tem como prosseguir.
    #if len(erros) > 0:
    #    return (False, dados, erros, avisos)

    # Verifica quantidade de extrações e emite avisos para situações incomuns
    if (qtd_extracao_aparelho == 0):
        mensagem = ("Não foi encontrada nenhuma extração com nome contendo a palavra 'Aparelho'." +
                    " O material não tem aparelho? Assegure-se que está correto.")
        avisos += [mensagem]
        if_print_ok(explicar, mensagem)

    if (qtd_extracao_sim == 0):
        mensagem = ("Não foi encontrada nenhuma extração com nome contendo a palavra 'SIM'." +
                    "Realmente não tem SIM Card?. Assegure-se que isto está correto.")
        avisos += [mensagem]
        if_print_ok(explicar, mensagem)

    if (qtd_extracao_sd > 0):
        mensagem = ("Sistema ainda não preparado para tratar cartão SD. Consulte desenvolvedor.")
        avisos += [mensagem]
        if_print_ok(explicar, mensagem)

    if (qtd_extracao_backup > 0):
        mensagem = (
            "Sistema ainda não preparado para tratar relatório de processamento de Backup. Consulte desenvolvedor.")
        avisos += [mensagem]
        if_print_ok(explicar, mensagem)



    die('ponto583')

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

    # Localiza a seção <metadata section="Extraction Data">
    p = ns + 'modelType' + '[@type="SIMData"]'
    model_type = root.find(p)
    # var_dump(model_type)
    # die('ponto642')
    # <model type="SIMData" id="fe5bdfe1-2e9c-47de-a9b5-3ec3d418446e" deleted_state="Intact"
    # decoding_confidence="High" isrelated="False" extractionId="1">
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

    # var_dump(dext)
    # die('ponto660')


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
        'IMEI': 'sapiAparelhoIMEI'
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
        # Número telefonico associado ao SimCard
        'MSISDN': 'sapiSimMSISDN'
    }

    # Dicionário para armazenamento de dados para laudo
    dlaudo = {}

    # Processa as extrações do aparelho, separando o que é relevante para laudo
    # -------------------------------------------------------------------------
    if (qtd_extracao_aparelho > 0):
        dcomp = {}
        lista_extracoes = []
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
                else:
                    # Armazena valor da propriedade
                    dcomp[proplaudo_aparelho[j]] = dext[i][j]

        # Verifica se localizou IMEI do dispositivo
        if dcomp.get('sapiAparelhoIMEI', None) is None:
            mensagem = (
                "Não foi detectado IMEI para aparelho. Dica: Normalmente o IMEI é recuperado em extração lógica.")
            avisos += [mensagem]
            if_print_ok(explicar, mensagem)

        # Dados do aparelho
        dcomp['sapiTipoComponente'] = 'aparelho'
        dcomp['sapiNomeComponente'] = 'Aparelho'
        dcomp['sapiExtracoes'] = ', '.join(lista_extracoes)

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
    dlaudo["sapiTipoComponenteAquisicao"] = "extracao"
    dlaudo["sapiSoftwareVersao"] = "UFED/cellebrite"

    dados['laudo'] = dlaudo

    # Estamos guardando os dados gerais da extração para algum uso futuro....
    # ...talvez uma base de conhecimento, estatíticas, buscas técnicas
    # No momento, nem precisaria
    dados['tecnicos'] = {}
    dados['tecnicos']['extracoes'] = dext

    # var_dump(dados)
    # die('ponto1044')

    # Ok, validado, mas pode conter avisos
    return (True, dados, erros, avisos)


# Exibe dados para laudo, com uma pequena formatação para facilitar a visualização
# --------------------------------------------------------------------------------
def exibir_dados_laudo(d):
    print_centralizado(" Dados para laudo ")

    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(d)

    print_centralizado("")

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


def print_centralizado(texto='', tamanho=129, preenchimento='-'):
    direita = (tamanho - len(texto)) // 2
    esquerda = tamanho - len(texto) - direita
    print(preenchimento * direita + texto + preenchimento * esquerda)


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
        {'codigo_tarefa': codigo_tarefa})

    # Insucesso. Provavelmente a tarefa não foi encontrada
    if (not sucesso):
        # Continua no loop
        print("Erro: ", msg_erro)
        print("Efetue refresh na lista de tarefa")
        return False

    # var_dump(item["item"])

    # ------------------------------------------------------------------
    # Exibe dados do item para usuário confirmar
    # se escolheu o item correto
    # ------------------------------------------------------------------
    print()
    print("-" * 129)
    print("Item: ", tarefa["dados_item"]["item_apreensao"])
    print("Material: ", tarefa["dados_item"]["material"])
    print("Descrição: ", tarefa["dados_item"]["descricao"])
    print("-" * 129)
    print()
    # prosseguir=pergunta_sim_nao("Prosseguir para este item? ",default="n")
    # if (not prosseguir):
    #    return

    # ------------------------------------------------------------------
    # Verifica se tarefa tem o tipo certo
    # ------------------------------------------------------------------
    if (not tarefa["tipo"] == "extracao"):
        # Isto aqui não deveria acontecer nunca...mas para garantir...
        print("Tarefa do tipo [", tarefa["tipo"], "] não pode ser resolvida por sapi_cellebrite")
        return

    # Verifica se tarefa possui situação coerente para execução
    codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
    if not (codigo_situacao_tarefa == GAguardandoPCF or codigo_situacao_tarefa == GAbortou):
        # Tarefas com outras situações não são permitidas
        print("Tarefa com situação ", codigo_situacao_tarefa, "-",
              tarefa['descricao_situacao_tarefa'] + " => Não pode ser processada")
        print("Apenas tarefas com situação 'Aguardando ação PCF' ou 'Abortada' podem ser processadas")
        print("Em caso de divergência, efetue em Refresh na lista de tarefas (*SG)")
        print("Para modificar manualmente a situação da tarefa, consulte tarefa no SETEC3")
        return

    # var_dump(tarefa)
    # var_dump(tarefa['codigo_situacao_tarefa'])
    # die('ponto944')

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
    # Montagem de storage
    # -----------------------------------------------------------------

    # Confirma que tem acesso ao storage escolhido
    (sucesso, ponto_montagem, erro) = acesso_storage_windows(tarefa["dados_storage"])
    if not sucesso:
        erro = "Acesso ao storage [" + ponto_montagem + "] falhou"
        print(erro)
        return

    # Desmonta caminho, separando pasta de arquivo
    # prefixando com ponto de montagem
    # Para o cellebrite, que faz cópia de uma pasta inteira, isto não faz sentido
    # (caminho,nome_arquivo)=decompoe_caminho(tarefa["caminho_destino"])

    caminho_destino = ponto_montagem + tarefa["caminho_destino"]

    print("- Este comando irá efetuar validação e cópia da pasta de relatórios do Cellebrite/UFED para o storage.")
    print()
    print("- Pasta de destino: ", caminho_destino)

    # Verifica se pasta de destino já existe
    # Isto não é permitido
    limpar_pasta_destino_antes_copiar = False
    if os.path.exists(caminho_destino):
        print_log("Pasta de destino '" + caminho_destino + "' contém arquivos")
        print()
        print("- IMPORTANTE: A pasta de destino JÁ EXISTE")
        print()
        print("- Não é possível iniciar cópia de relatório nesta situação.")
        print("- Se o conteúdo atual da pasta de destino não tem utilidade, ",
              "autorize a limpeza da pasta (opção abaixo).")
        print("- Caso contrário, ou seja, se os dados na pasta de destino estão ok (foram copiados anteriormente), ",
              "cancele a cópia (responda N na próxima pergunta) e em seguida utilize o comando *si para validar a pasta. ",
              "Após a validação com sucesso, o sistema atualizará a situação da tarefa para 'concluído'")

        print()
        prosseguir = pergunta_sim_nao(
            "< Você realmente deseja excluir a pasta de destino (assegure-se de estar tratando do item correto)?",
            default="n")
        if not prosseguir:
            # Encerra
            print("- Cancelado: Não é possível executar cópia para pasta de destino existente.")
            return
        print("- Ok, pasta de destino será excluída durante procedimento de cópia")
        print_log("Usuário solicitou exclusão da pasta de destino: ", caminho_destino)

        # Guarda indicativo que será necessário limpeza da pasta de destino
        limpar_pasta_destino_antes_copiar = True

    # ------------------------------------------------------------------
    # Seleciona pasta local de relatórios
    # ------------------------------------------------------------------
    # Solicita que usuário informe a pasta local que contém
    # os relatórios do Cellebrite para o item corrente
    caminho_origem = ""

    # Loop para selecionar pasta
    while True:
        print()
        print("Selecionar pasta de Origem")
        print("==========================")
        print("- Na janela gráfica que foi aberta, selecione a pasta de origem.")
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

        print("- Pasta de origem selecionada: ", caminho_origem)

        # Verificação básica da pasta, para ver se contém os arquivos típicos
        print()
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
            print("- Prosseguindo, após confirmação de avisos")

        # Ok, prossegue
        break

    # Verifica se o arquivo XML contido na pasta de origem está ok
    print("- Iniciando validação de XML. Isto pode demorar, dependendo do tamanho do arquivo. Aguarde...")
    arquivo_xml = caminho_origem + "/Relatório.xml"
    (resultado, dados_relevantes, erros, avisos) = processar_arquivo_xml(arquivo_xml, numero_item=item["item"],
                                                                         explicar=False)
    if (not resultado):
        # A mensagem de erro já foi exibida pela própria função de validação
        for mensagem in erros:
            print("* ERRO: ", mensagem)
        return False

    print("- XML válido")
    print("- Os seguintes dados foram selecionados para utilização em laudo:")
    print()
    exibir_dados_laudo(dados_relevantes['laudo'])

    # Exibe avisos, se houver
    if len(avisos) > 0:
        print()
        print_centralizado(' AVISOS ')
        for mensagem in avisos:
            print("# Aviso: ", mensagem)
        print()
        print_centralizado('')

    print()
    print("- Verifique os dados acima, e se estiver tudo certo confirme para iniciar a cópia")
    prosseguir = pergunta_sim_nao("< Dados acima correspondem ao exame efetuado? ", default="n")
    if not prosseguir:
        return
    #
    copia_background = pergunta_sim_nao("< Efetuar cópia em background? ", default="n")
    if copia_background:
        proc = multiprocessing.Process(
            target=efetuar_copia,
            args=(caminho_origem, caminho_destino, codigo_tarefa, dados_relevantes, limpar_pasta_destino_antes_copiar,
                  copia_background))
        proc.start()
        # Inicia cópia em background
        # O fluxo retona imediatamente para cá, e voltamos para à rotina principal
        # permitindo que usuário efetue outras operações
        # Ao término, o usuário será avisado
        print()
        print("- Cópia iniciada em background. Você será avisado ao término do processamento.")
        print()
    else:
        # Não é em background
        print("- Cópia iniciada. Isto pode demorar...Aguarde....")
        # Inicia cópia e aguarda o término
        # Neste caso, o usuário terá que aguardar até o término da cópia
        efetuar_copia(caminho_origem, caminho_destino, codigo_tarefa, dados_relevantes,
                      limpar_pasta_destino_antes_copiar, copia_background)

    return


# Efetua a cópia de uma pasta
def efetuar_copia(caminho_origem, caminho_destino, codigo_tarefa, dados_relevantes, limpar_pasta_destino_antes_copiar,
                  copia_background):
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
            print_var(tipo_print,
                      "Exclusão de conteúdo atual da pasta de destino '" + caminho_destino + "' em andamento.")
            shutil.rmtree(caminho_destino, ignore_errors=True)
            texto_status = "Pasta de destino excluída '" + caminho_destino + "'"
            atualizar_status_tarefa_andamento(codigo_tarefa, texto_status)

        # 1) Renomear o arquivo XML na pasta de origem (nome temporário)
        # ------------------------------------------------------------------
        print_var(tipo_print,
                  "Renomeando arquivo ", arquivo_xml_origem, " para " + arquivo_xml_origem_renomeado + ".",
                  "No final da cópia o nome original será restaurado")
        os.rename(arquivo_xml_origem, arquivo_xml_origem_renomeado)
        print_var(tipo_print, "Renomeado com sucesso")

        # 2) Inicia processo para acompanhar a cópia
        # Se a cópia não for em background, não tem este acompanhamento
        if copia_background:
            p_acompanhar = multiprocessing.Process(target=acompanhar_copia,
                                                   args=(tipo_print, codigo_tarefa, caminho_destino))
            p_acompanhar.start()
            print_var(tipo_print, "Iniciando processo background para acompanhamento de copia")
            print_var(tipo_print, "Para acompanhar a situação, utilize o comando *SG")

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
        (ok, msg_erro) = atualizar_status_tarefa(
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
            p_acompanhar.terminate()
            print_var(tipo_print, "Encerrando processo background para acompanhamento de copia")

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
    (ok, msg_erro) = atualizar_status_tarefa(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=codigo_situacao_tarefa,
        status=texto_status,
        dados_relevantes=dados_relevantes
    )

    if (not ok):
        print()
        print_var(tela_log, "Não foi possível atualizar status de finalização da tarefa: ", msg_erro)
        print_var(tela_log,
                  "Após diagnosticar e resolver a causa do problema,  utilize comando *SI para atualizar situação da tarefa")
        print()
        return

    # Status atualizado
    print_var(tela_log, "Tarefa ", codigo_tarefa, " atualizada para 'SUCESSO'")

    # Encerra o processo de acompanhamento de cópia
    if copia_background:
        p_acompanhar.terminate()
        print_var(tipo_print, "Encerrando processo background para acompanhamento de copia")


# Efetua a cópia de uma pasta
def acompanhar_copia(tipo_print, codigo_tarefa, caminho_destino):
    print_var(tipo_print, "Processo de acompanhamento de tarefa: Vivo")

    # Um delay inicial, para dar tempo da cópia começar
    time.sleep(GtempoEntreAtualizacoesStatus)

    # Fica em loop inifito. Será encerrado pelo pai (com terminate)
    while True:
        # Verifica o tamanho atual da pasta de destino
        tamanho = converte_bytes_humano(tamanho_pasta(caminho_destino))

        # Atualiza status
        texto_status = tamanho + " copiados"
        print_var(tipo_print, texto_status)
        atualizar_status_tarefa_andamento(codigo_tarefa, texto_status)

        # Intervalo entre atualizações de status
        time.sleep(GtempoEntreAtualizacoesStatus)


# Explicar=True: Faz com que seja exibida (print) a explicação
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

    # var_dump(item)
    # var_dump(tarefa)
    # die('ponto1294')

    # Recupera dados atuais da tarefa do servidor,
    codigo_tarefa = tarefa["codigo_tarefa"]
    (sucesso, msg_erro, tarefa) = sapisrv_chamar_programa(
        "sapisrv_consultar_tarefa.php",
        {'codigo_tarefa': codigo_tarefa})

    # Insucesso. Provavelmente a tarefa não foi encontrada
    if (not sucesso):
        # Continua no loop
        if_print_ok(explicar, "Erro: ", msg_erro)
        if_print_ok(explicar, "Efetue refresh na lista de tarefa")
        return (erro_interno, "", {}, erros, avisos)

    # var_dump(item["item"])

    # ------------------------------------------------------------------
    # Exibe dados do item para usuário
    # ------------------------------------------------------------------
    print()
    print("-" * 129)
    print("Item: ", tarefa["dados_item"]["item_apreensao"])
    print("Material: ", tarefa["dados_item"]["material"])
    print("Descrição: ", tarefa["dados_item"]["descricao"])
    print("-" * 129)

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
    if_print_ok(explicar, "- Pasta de destino definida para este item no storage: ", caminho_destino)

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
        status = "Existem arquivos básicos faltando"
        codigo_status = GEmAndamento
        if_print_ok(explicar, status)
        return (codigo_status, status, {})

    # Ok, já tem todos os arquivos básicos
    status = "- Pasta contém todos os arquivos básicos"
    if_print_ok(explicar, status)

    # Valida arquivo xml
    if_print_ok(explicar,
                "- Iniciando validação de XML. Isto pode demorar, dependendo do tamanho do arquivo. Aguarde...")
    arquivo_xml = caminho_destino + "/Relatório.xml"
    (resultado, dados_relevantes, erros, avisos) = processar_arquivo_xml(arquivo_xml, numero_item=item["item"],
                                                                         explicar=explicar)
    if (not resultado):
        status = "Arquivo XML inconsistente"
        codigo_status = GAbortou
        if_print_ok(explicar, status)
        return (codigo_status, status, {})

    # Se está tudo certo, exibe o resultado dos dados coletados para laudo
    # se estiver no modo de explicação
    if_print_ok(explicar, "- XML válido")
    if (explicar):
        print("- Os seguintes dados foram selecionados para utilização em laudo:")
        # Exibe dados do laudo
        exibir_dados_laudo(dados_relevantes['laudo'])

    # Sucesso
    status = "Relatório Cellebrite armazenado com sucesso"
    codigo_status = GFinalizadoComSucesso
    return (codigo_status, status, dados_relevantes)


# Exibe situação do item
def exibir_situacao_item():
    print()
    print("Verificação da situação da tarefa corrente")

    (codigo_situacao_tarefa, texto_status, dados_relevantes) = determinar_situacao_item_cellebrite(explicar=True)
    print()
    print("- Situacao conforme pasta de destino: ", str(codigo_situacao_tarefa), "-", texto_status)

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
        {'codigo_tarefa': codigo_tarefa})

    # Insucesso
    if (not sucesso):
        # Continua no loop
        print("Falha na busca da tarefa no servidor: ", msg_erro)
        return

    # Exibe o status da tarefa no servidor
    print("- Situação reportada pelo servidor  : ",
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
    mensagem = ('\n'
                'ATENÇÃO: A situação da tarefa no servidor não está coerente com a situação '
                'observada na pasta de destino.\n'
                'Isto ocorre quando o usuário faz uma cópia manual dos dados diretamente para o servidor, '
                'sem utilizar o agente sapi_cellebrite.\n'
                'Também pode ocorrer esta situação caso tenha havido alguma falha no procedimento '
                'de atualização automática após a cópia no sapi_cellebrite '
                '(Em caso de dúvida, consulte o log local, e alerte o desenvolvedor).\n'
                'No caso desta tarefa em particular, para sanar o problema basta efetuar a atualização manual '
                '(respondendo S na próxima pergunta)\n'
                )
    print()
    print(mensagem)
    print()
    atualizar = pergunta_sim_nao("< Atualizar servidor com o status observado? ", default="n")
    if (not atualizar):
        return

    # Atualiza situação observada no servidor
    (ok, msg_erro) = atualizar_status_tarefa(
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

    return


# Chama função e intercepta CTR-C
# =============================================================
def receber_comando_ok():
    try:
        return receber_comando()
    except KeyboardInterrupt:
        # TODO: Verificar se tem algum processo filho rodando
        # Se não tiver, finaliza normalmente
        # Caso contrário, não permitie
        # Por enquanto, simplesmente ignora o CTR-C
        print("Para encerrar, utilize comando *qq")
        return ("", "")


# Recebe e confere a validade de um comando de usuário
# =============================================================
def receber_comando():
    comandos = {
        # Comandos de navegacao
        '+': 'Navega para a tarefa seguinte da lista',
        '-': 'Navega para a tarefa anterior da lista',
        '*ir': 'Posiciona na tarefa com sequencial(Sq) indicado (ex: *ir 4, pula para a quarta tarefa da lista).' +
               '\nPara simplificar, pode-se digitar apenas o sequencial (ex: 4)',

        # Comandos relacionados com um item
        '*cr': 'Copia pasta de relatórios (Cellebrite) do computador local para storage, concluindo a tarefa corrente',
        '*si': 'Verifica situação da tarefa corrente, comparando-a com a situação no servidor',
        '*du': 'Dump: Mostra todas as propriedades de uma tarefa (utilizado para Debug)',

        # Comandos gerais
        '*sg': 'Exibe situação atual das tarefas. ' +
               'Será feita uma recuperação da situação atual das tarefas do servidor (refresh).',
        '*tm': 'Troca memorando',
        '*qq': 'Finaliza'

    }

    cmd_navegacao = ["+", "-", "*ir"]
    cmd_item = ["*cr", "*si"]
    cmd_geral = ["*sg", "*tm", "*qq"]

    comando_ok = False
    comando_recebido = ""
    argumento_recebido = ""
    while not comando_ok:
        print()
        entrada = input("Comando (?=ajuda): ")
        entrada = entrada.lower().strip()
        lista_partes_comando = entrada.split(" ", 2)
        comando_recebido = ""
        if (len(lista_partes_comando) >= 1):
            comando_recebido = lista_partes_comando[0]
        argumento_recebido = ""
        if (len(lista_partes_comando) >= 2):
            argumento_recebido = lista_partes_comando[1]

        if comando_recebido in comandos:
            # Se está na lista de comandos, ok
            comando_ok = True
        elif comando_recebido.isdigit():
            # um número é um comando válido
            comando_ok = True
        elif (comando_recebido == "H" or comando_recebido == "?"):
            # Exibe ajuda para comando
            print()
            print("Navegacao:")
            for key in cmd_navegacao:
                print(key, " : ", comandos[key])
            print()
            print("Processamento da tarefa corrente (marcada com =>):")
            for key in cmd_item:
                print(key, " : ", comandos[key])
            print()
            print("Comandos gerais:")
            for key in cmd_geral:
                print(key, " : ", comandos[key])
        elif (comando_recebido == ""):
            print("Para ajuda, digitar comando 'h' ou '?'")
        else:
            if (comando_recebido != ""):
                print("Comando (" + comando_recebido + ") inválido")

    return (comando_recebido, argumento_recebido)


# Exibe lista de tarefas
# ----------------------------------------------------------------------
def exibir_situacao():
    cls()

    # Exibe cabecalho (Memorando/protocolo)
    print(GdadosGerais["identificacaoSolicitacao"])
    print_centralizado()

    # Lista de tarefas
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
        # cabecalho
        if (q == 1):
            print('%2s %2s %6s %-30.30s %15s %-69.69s' % (
                " ", "Sq", "tarefa", "Situação", "Material", "Item : Descrição"))
            print_centralizado()
        # Tarefa
        item_descricao = t["item"] + " : " + i["descricao"]
        print('%2s %2s %6s %-30.30s %15s %-69.69s' % (
            corrente, q, t["codigo_tarefa"], situacao, i["material"], item_descricao))

        if (q == Gicor):
            print_centralizado()

    return


# Salva situação atual para arquivo
# ----------------------------------------------------------------------
def salvar_estado():
    # Monta dicionario de estado
    estado = dict()
    estado["Gtarefas"] = Gtarefas
    estado["GdadosGerais"] = GdadosGerais

    # Abre arquivo de estado para gravação
    nome_arquivo = "estado.sapi"
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

    # Não tem arquivo de estado
    if (not os.path.isfile("estado.sapi")):
        return

    # Le dados do arquivo e fecha
    arq_estado = open("estado.sapi", "r")
    estado = json.load(arq_estado)
    arq_estado.close()

    # Recupera variaveis do estado
    Gtarefas = estado["Gtarefas"]
    GdadosGerais = estado["GdadosGerais"]


# Avisa que dados vieram do estado
# print("Dados carregados do estado.sapi")
# sprint("Isto so deve acontecer em ambiente de desenvolvimento")


# Carrega situação de arquivo
# ----------------------------------------------------------------------
def obter_memorando_tarefas():
    print()

    # Solicita que o usuário se identifique através da matricula
    # ----------------------------------------------------------
    lista_solicitacoes = None
    while True:
        matricula = input("Entre com sua matricula: ")
        matricula = matricula.lower().strip()

        (sucesso, msg_erro, lista_solicitacoes) = sapisrv_chamar_programa(
            "sapisrv_obter_pendencias_pcf.php",
            {'matricula': matricula})

        # Insucesso....normalmente matricula incorreta
        if (not sucesso):
            # Continua no loop
            print("Erro: ", msg_erro)
            continue

        # Matricula ok, vamos ver se tem solicitacoes de exame
        if (len(lista_solicitacoes) == 0):
            print(
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
            print('%2s  %10s  %s' % ("N.", "Protocolo", "Documento"))
        protocolo_ano = d["numero_protocolo"] + "/" + d["ano_protocolo"]
        print('%2d  %10s  %s' % (q, protocolo_ano, d["identificacao"]))

    # print("type(lista_solicitacoes)=",type(lista_solicitacoes))

    # Usuário escolhe a solicitação de exame de interesse
    # --------------------------------------------------------
    tarefas = None
    while True:
        #
        print()
        num_solicitacao = input(
            "Selecione a solicitação de exame, indicando o número de sequencia (N.) na lista acima: ")
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
        # print("Selecionado:",solicitacao["identificacao"])
        sys.stdout.write("Buscando tarefas de imagem para " + GdadosGerais["identificacaoSolicitacao"] + "...")

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
        else:
            # Ok, tudo certo
            sys.stdout.write("OK")
            break

    # Retorna tarefas do memorando selecionado
    return tarefas


def refresh_tarefas():
    # Irá atualizar a variáel global de tarefas
    global Gtarefas

    print("Buscando situação atualizada no servidor (SETEC3). Aguarde...")

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
# Código para teste
# ======================================================================

# d={}
# d['chave1']=10
# d['chave2']=['abc','def']
# d['chave3']={'c31': 12.5, 'c32': ['xyz', 'def']}


# d_json=json.dumps(d,sort_keys=True)
# print(d_json)
# die('ponto2031')


# import pyperclip # The name you have the file
# x = pyperclip.paste()
# print(x)

# start_time=time.time()
# time.sleep(5)
# tempo=time.time()-start_time
#
# print("tempo = ", tempo)
# #print("tempo = ", str(tempo))
# die('ponto1345')
# var_dump(tempo)

# pasta='c:/tempr'
# tamanho=tamanho_pasta(pasta)
# print(pasta,tamanho, converte_bytes_humano(tamanho))
#
# pasta='c:/teste_iped'
# tamanho=tamanho_pasta(pasta)
# print(pasta,tamanho, converte_bytes_humano(tamanho))
#
# die('ponto1174')

# from teste_modulo import *
#
# class teste:
# 	def f1():
# 		print("Ok, chamou f1")
#
# teste.f1()
# sys.exit()

# ======================================================================
# Rotina Principal 
# ======================================================================

if __name__ == '__main__':

    # Desvia para um certo ponto, para teste
    # --------------------------------------

    # Sintetizar arquivo
    #sintetizar_arquivo_xml("Relatório.xml", "parcial.xml")
    #die('ponto1908')

    # Desvia para um certo ponto, para teste
    # Chama validacao de xml
    (resultado_teste, dados_teste, erros_teste, avisos_teste) = validar_arquivo_xml("parcial.xml", numero_item="12",
                                                                                      explicar=True)
    print(resultado_teste)
    exibir_dados_laudo(dados_teste['laudo'])
    die('ponto1936')

    # Iniciando
    # ---------
    print()
    print("SAPI - Cellebrite (Versao " + Gversao + ")")
    print("=========================================")
    print()
    print(
        "- Dica: Para uma visualização adequada, configure o buffer de tela e tamanho de janela com largura de 130 caracteres")
    print()
    print()
    print_log('Iniciando sapi_cellebrite - ', Gversao)

    # Testa comunicação com servidor SAPI
    # -----------------------------------
    # Em desenvolvimento não executa, para ganhar tempo
    if not Gdesenvolvimento:
        assegura_comunicacao_servidor_sapi()

    # Obtem lista de tarefas a serem processadas
    # ------------------------------------------

    # Para desenvolvimento...recupera tarefas de arquivo
    # Para versão produtiva, ajustar valor da global
    if Gdesenvolvimento:
        carregar_estado()
    if (len(Gtarefas) == 0):
        Gtarefas = obter_memorando_tarefas()
    if Gdesenvolvimento:
        salvar_estado()

    # Processamento das tarefas
    # ---------------------------
    refresh_tarefas()
    exibir_situacao()

    # Recebe comandos
    while (True):
        (comando, argumento) = receber_comando_ok()
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

            # Finaliza
            print()
            print("Programa finalizado por solicitação do usuário")
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

        # Comandos gerais
        if (comando == '*sg'):
            refresh_tarefas()
            exibir_situacao()
            continue
        elif (comando == '*tm'):
            Gtarefas = obter_memorando_tarefas()
            if (len(Gtarefas) > 0):
                Gicor = 1  # Inicializa indice da tarefa corrente
                exibir_situacao()
            continue

            # Loop de comando

    # Finaliza
    print()
    print("FIM SAPI - Cellebrite (Versão ", Gversao, ")")