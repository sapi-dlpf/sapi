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
#
#
# Histórico:
#  - v1.0 : Inicial
# =======================================================================
# TODO: 
# -
# - ...
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

# Verifica se está rodando versão correta de Python
# ====================================================================================================
if sys.version_info <= (3, 0):
    sys.stdout.write("Versao do intepretador python (" + str(platform.python_version()) + ") incorreta.\n")
    sys.stdout.write("Este programa requer Python 3 (preferencialmente Python 3.5.2).\n")
    sys.exit(1)

# Interface gráfica (tk)
# Este nome de modulo só existe em Python3
# Logo, tem que ficar abaixo do teste de python3
from tkinter import Tk

# =======================================================================
# GLOBAIS
# =======================================================================
Gversao = "0.9.3"

Gdesenvolvimento = True  # Ambiente de desenvolvimento
# Gdesenvolvimento=False #Ambiente de producao

# Base de dados (globais)
GdadosGerais = {}  # Dicionário com dados gerais
Gtarefas = []  # Lista de tarefas

# Diversos sem persistência
Gicor = 1

# Controle de frequencia de atualizacao
GtempoEntreAtualizacoesStatus = 180

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
# Funções Auxiliares Ambiente W I N D O W S
# ======================================================================

def get_clipboard():
    # try:
    #     root = Tk()
    #     root.withdraw()
    #     clip = root.clipboard_get()
    # except BaseException as e:
    #     print("Nao foi possivel recuperar dados do clipboard")
    #     clip = ""

    # Vamos gerar erros, para ver qual é o tipo de exception que ocorre
    root = Tk()
    root.withdraw()
    clip = root.clipboard_get()

    return clip


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
    nome_agente = socket.gethostbyaddr(socket.gethostname())[0]

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


# Validar arquivo XML do cellebrite
# ----------------------------------------------------------------------
def validar_arquivo_xml(arquivo, item, explicar=True):
    # Dados para retorno
    # ------------------------------------------------------------------
    dados = {}

    # mensagens=[]

    # Armazenamento de dados de resultado
    dext = {}  # Dicionário com dados de cada extração

    # Indice do componente
    quantidade_componentes = 0

    # dicionários para montagem de dados para laudo
    d_aquis_geral = {}  # Dados gerais da aquisição

    # Abre arquivo XML e faz parse
    # ------------------------------------------------------------------
    tree = ElementTree.parse(arquivo)
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
        if_print_ok(explicar, "XML com raiz inesperada: ", root.tag, "Deveria iniciar por <project ...>")
        return (False, dados)

    # Extrai componente fixo do tag (namespace), removendo a constante "project"
    # O tag da raiz é algo como
    # {http://pa.cellebrite.com/report/2.0}project
    # O componente fixo (namespace) é o que está entre colchetes
    ns = root.tag.replace('project', '')

    # Verifica atributos do projeto
    # ------------------------------------------------------------------
    a = root.attrib
    # var_dump(a)

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
        if_print_ok(explicar, "Aviso: Relatório com esta versão (", report_version,
                    ") não foi testada com este validador. Pode haver incompatibilidade")
    d_aquis_geral['reportVersion'] = report_version

    # Nome do projeto
    name = a.get('name', None)
    if (item not in name):
        if_print_ok(explicar, "ERRO: Nome do projeto (", name,
                    ") inválido. O nome do projeto deve conter o item de apreensão. Sugestão: ( Item", item, ")")
        return (False, dados)
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
    erro_extracao = False
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
            if_print_ok(explicar, "Erro: ", nome_extracao,
                        "com nome fora do padrão, pois não contém nenhum dos termos esperados (",
                        ",".join(termos_nome_extracao), ")")
            erro_extracao = True

    # Acho que não vai precisar disto...pode contar pelo tipo
    # d_aquis_geral['qtd_extracao_aparelho']=qtd_extracao_aparelho
    # d_aquis_geral['qtd_extracao_sim']=qtd_extracao_sim
    # d_aquis_geral['qtd_extracao_sd']=qtd_extracao_sd
    # d_aquis_geral['qtd_extracao_backup']=qtd_extracao_backup

    # Verifica conjunto de extrações
    # ------------------------------------------------------------------

    # Se tem algum erro na seção de extração, não tem como prosseguir.
    if (erro_extracao):
        return (False, dados)

    # Verifica quantidade de extrações
    if (qtd_extracao_aparelho == 0):
        if_print_ok(explicar,
                    "Aviso: Não foi encontrada nenhuma extração com nome contendo a palavra 'Aparelho'.",
                    "Isto é incomum. Assegure-se que está correto.")

    if (qtd_extracao_sim == 0):
        if_print_ok(explicar,
                    "Aviso: Não foi encontrada nenhuma extração com nome contendo a palavra 'SIM'.",
                    "Isto é incomum. Assegure-se que isto está correto.")

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
    # Prepara propriedades para laudo
    # ------------------------------------------------------------------

    dlaudo = {}

    '''
    'extractionInfo_name', 				# Nome da extração escolhida pelo PCF (Ex: 'Aparelho - Lógica')

    # Com influência do PCF
    # Para efetuar o exame, o PCF escolhe manualmente o fabricante/modelo,
    # que nem sempre é exatamente o mesmo do aparelho a ser examinado
    # Iremos armazenar isto para 'Base de conhecimento'.
    # Se alguém quiser saber como fazer o exame de um certo dispositivo,
    # basta consultar estes dados
    'DeviceInfoSelectedManufacturer', 	#Fabricante selecionado pelo PCF
    'DeviceInfoSelectedDeviceName', 	#Modelo selecionado pelo PCF


    # Dados gerais
    'DeviceInfoDetectedManufacturer', 	# Fabricante do aparelho detectado durante exame
    'DeviceInfoDetectedModel', 			# Modelo do aparelho detectado durante exame
    #'DeviceInfoReportType', 			# Tipo de relatório: 'Telefone', 'SIM' => Não tem para todas os tipos de extração....
    'DeviceInfoRevision', 				# Versão do sistema operacional '5.1.1 LMY48B G531BTVJU0AOL1',
    #'DeviceInfoTimeZone', 				# No formato 'America/Sao_Paulo'. Uso Futuro?
    #'DeviceInfoUnitVersion', 			# Versão da unidade (Ex: '5.2.0.689'), provavelmente do hardware de touch
    'ExtractionType', 					# Descrição do método de extração (ex: 'Lógico [ Android Backup ]')
    #'extractionInfo_IsPartialData', 	# O que são dados parciais? Extração parcial? Relatório parcial? Uso futuro!?
    #'extractionInfo_type', 				# Tipo de extração (Ex: 'Logical') => ExtractionType está em português
    #'ufedExtractionApkDowngradeTitle',  # Uma explicação do próprio UFED sobre o download de APK. => bonitinho...


    # Exclusivos de aparelhos
    'IMEI', 							# IMEI do aparelho (Ex: '351972070993501')

    # Exclusivos de SIM Card
    'ACC',								# Algo como o tipo de cartão SIM. Uso Futuro!?
    'ICCID', 							# Ex: '89550317001039126416'
    'IMSI', 							# Ex: '724044440381414'
    'SPN' 								# Operadora. (Ex: 'TIM')
    '''

    # Revisar a incluir novamente propriedades, a medida que for
    # examinando novos modelos

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
    }

    proplaudo_sim = {
        # Ex: '89550317001039126416'
        'ICCID': 'sapiSimICCID',
        # Ex: '724044440381414'
        'IMSI': 'sapiSimIMSI',
        # Operadora. (Ex: 'TIM')
        'SPN': 'sapiSimOperadora',
        # Descrição do método de extração do SIM
        'ExtractionType': 'sapiExtracoes'
    }

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

    return (True, dados)

    '''
    # Este teste vai ser feito apenas no momento de geração do laudo
    # Não há necessidade de se preocupar com isto agora

            # Se propriedade não é conhecida, avisa...pode ter algo útil
            if (name not in prop_conhecidas):
                msg=("Propriedade desconhecida("+name+") "+
                     "pode eventualmente conter dados relevante para laudo. "+
                     "Na extração '"+dext[sourceExtraction]["extractionInfo_name"]+"' "+
                     name+"="+dext[sourceExtraction][name])
                if_print_ok(explicar,msg)


    # ------------------------------------------------------------------
    # Se surgir alguma nova propriedade, aponta para a possível
    # utilidade da mesma
    # Isto é importante, pois a tendência é que os relatórios do
    # Cellebrite fiquem cada vez mais completos
    # ------------------------------------------------------------------

    prop_conhecidas=[
        'ACC',
        'Client Used for Extraction',
        'DeviceInfoAndroidID',
        'DeviceInfoConnectionType',
        'DeviceInfoDetectedManufacturer',
        'DeviceInfoDetectedModel',
        'DeviceInfoExtractionEndDateTime',
        'DeviceInfoExtractionStartDateTime',
        'DeviceInfoInternalVersion',
        'DeviceInfoPhoneDateTime',
        'DeviceInfoReportType',
        'DeviceInfoRevision',
        'DeviceInfoSelectedDeviceName',
        'DeviceInfoSelectedManufacturer',
        'DeviceInfoTimeZone',
        'DeviceInfoUnitIdentifier',
        'DeviceInfoUnitVersion',
        'ExtractionType',
        'ICCID',
        'IMEI',
        'IMSI',
        'ProjectStateExtractionId',
        'SPN',
        'extractionInfo_IsPartialData',
        'extractionInfo_name',
        'extractionInfo_type',
        'ufedExtractionApkDowngradeTitle'
        ]


    '''


def exibir_dados_laudo(d):
    print("-" * 20 + " Dados para laudo " + "-" * 20)

    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(d)

    print("-" * 60)

    return

    ''' Acho que não vale a pena tentar deixar isto muito bonito
    # Os dados para laudo estão estruturados em três níveis
    q=0
    # Nível de categoria: Ex: 10-identificacao
    for i in sorted(d):
        q=q+1
        # Pula linha
        if (q>1):
            print()
        print(str(q)+")",i)
        for j in sorted(d[i]):
            print("  ",d[i][j])

            for k in sorted(d[i][j]):

                # Descarta campos internos
                if (k in ['tipo']):
                    continue

                # Exibe campo para usuário
                print('    %12s : %s' % (j, d[i][j]))

    print("-"*60)

    return
    '''


# Valida pasta de relatório do cellebrite
# Se o parâmetro explicar=True, irá detalhar os problemas encontrados
# Retorna: True/False
def valida_pasta_relatorio_cellebrite(pasta, explicar=False):
    # Verifica se pasta informada existe
    if not os.path.exists(pasta):
        if_print_ok(explicar)
        if_print_ok(explicar, "* ERRO: Pasta informada não localizada")
        return False

    # Verifica se todos os arquivos necessários estão na pasta
    lista_arquivos_obrigatorios = ["Relatório.html", "Relatório.pdf", "Relatório.ufdr", "Relatório.xlsx",
                                   "Relatório.xml", "UFEDReader.exe"]
    erro = False
    for a in lista_arquivos_obrigatorios:
        caminho_arquivo = pasta + "/" + a
        if not os.path.isfile(caminho_arquivo):
            if_print_ok(explicar)
            if_print_ok(explicar, "* ERRO: Arquivo [" + a + "] não localizado na pasta.")
            erro = True

    if erro:
        return False

    # Tudo certo
    return True


# Chama copia e intercepta/trata erros
def copia_cellebrite_ok():
    try:
        copia_cellebrite()
    except KeyboardInterrupt:
        print("Operação interrompida pelo usuário")
        return


# Valida e copia relatórios do UFED/Cellebrite
# ----------------------------------------------------------------------
def copia_cellebrite():
    print()
    print("Cópia de relatório para storage")
    print("Contactando servidor. Aguarde...")

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

    # TODO: Se tarefa tiver sido finalizada com sucesso, avisar também

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

    # TODO: Se tarefa tiver sido finalizada com sucesso, avisar também

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

    print("Este comando irá efetuar a cópia da pasta de relatórios gerados pelo Cellebrite para o storage.")
    print("A cópia será antecedida por uma validação nos relatórios.")
    print()
    print("1) Pasta de destino: ", caminho_destino)

    # Verifica se pasta de destino já existe
    # Isto não é permitido
    if os.path.exists(caminho_destino):
        print()
        print("Cancelado: A pasta de destino JÁ EXISTE")
        print()
        print("Não é possível iniciar cópia de relatório nesta situação.")
        print("Se nada nesta pasta de destino já existente tem utilidade, ",
              "limpe a pasta e execute novamente este comando.")
        print("Se os dados na pasta de destino estão ok, utilize o comando *si para validar a pasta. ",
              "Após a validação, o sistema possibilitará a atualização da situação da tarefa para 'concluído'")
        return ()

    # ------------------------------------------------------------------
    # Seleciona pasta local de relatórios
    # ------------------------------------------------------------------
    # Solicita que usuário informe a pasta local que contém
    # os relatórios do Cellebrite para o item corrente
    caminho_origem = ""
    while True:

        # Loop para selecionar pasta
        selecionada_pasta = False
        while not selecionada_pasta:
            print()
            print("2) Pasta de Origem")
            print("Siga o procedimento abaixo para informar a pasta de origem:")
            print("- Com o file explorer, localize a pasta que contém o relatório.")
            print("- Na barra de exibição do nome completo da pasta, de um CTRL-C para copiar para o clipboard.")
            print(
                "- O sistema irá pegar o que estiver no clipboard, exibir, e solicitar confirmação para prosseguir.")
            print("<ENTER> para continuar")
            input()

            # Exibe a pasta obtida do clipboard, para usuário conferir
            caminho_origem = get_clipboard()
            print("Pasta de origem (clipboard): ", caminho_origem)
            print()
            selecionada_pasta = pergunta_sim_nao("Prosseguir para pasta exibida acima? ", default="n")

        # Verificação básica da pasta, para ver se contém os arquivos típicos
        if not valida_pasta_relatorio_cellebrite(pasta=caminho_origem, explicar=True):
            # Pede novamente a pasta
            continue

        # Ok, tudo certo
        print()
        print("Pasta de origem contém arquivos típicos de uma extração do Cellebrite.")
        break

    # Verifica se o arquivo XML contido na pasta de origem está ok
    print("Iniciando validação de XML. Isto pode demorar, dependendo do tamanho do arquivo. Aguarde...")
    arquivo_xml = caminho_origem + "/Relatório.xml"
    (resultado, dados) = validar_arquivo_xml(arquivo_xml, item=item["item"], explicar=True)
    if (not resultado):
        return False

    # Confira se
    print()
    print("XML válido. Os seguintes dados foram selecionados para utilização em laudo:")
    print()
    exibir_dados_laudo(dados['laudo'])

    print()
    print("Confira os dados acima, e prossiga se estiver ok.")
    prosseguir = pergunta_sim_nao("Copiar pasta de origem para storage? ", default="n")
    if not prosseguir:
        return

    # ==== Jogar para background ============
    # Por enquanto vamos fazer tudo em foreground...depois transferir
    # este código para o processo filho

    # **** Depois que jogar para backgroud, revisar para deixar apenas o
    # que é essencial com saída na console

    # Aqui tem que abrir mais um fork, para ir acompanhando a cópia
    # Medindo o avanço....

    # ------------------------------------------------------------------
    # Renomear o arquivo XML na pasta de origem (nome temporário)
    # ------------------------------------------------------------------
    # Utilizar xml como sinalizador de cópia concluída.
    # Incialmente ele é renomeado.
    # Quando a cópia for concluída ele volta ao nome original.
    # Esta operação visa garantir que outras checagens de estado
    # (por exemplo o comando *si) entenda que a cópia ainda não acabou
    # Só quando a extensão for restaurada para xml o sistema entenderá
    # que a cópia acabou
    arquivo_xml_origem = caminho_origem + "/Relatório.xml"
    arquivo_xml_origem_renomeado = arquivo_xml_origem + "_em_copia"
    print_log("Renomeando arquivo [" + arquivo_xml_origem + "] para [" + arquivo_xml_origem_renomeado + "].",
              "No final da cópia o nome original será restaurado")
    try:
        os.rename(arquivo_xml_origem, arquivo_xml_origem_renomeado)
    except BaseException as e:
        # Erro fatal
        print_log_dual("Rename falhou: ", str(e))
        print()
        sys.exit()
    print_log("Renomeado com sucesso")

    # ------------------------------------------------------------------
    # Efetua a cópia
    # ------------------------------------------------------------------
    print_log_dual("Iniciando cópia de:[", caminho_origem, "] para:[", caminho_destino, "]")
    try:
        shutil.copytree(caminho_origem, caminho_destino)
    except BaseException as e:
        # Erro fatal: Guarda no log e exibe na tela
        print("\n", "**** ERRO ****")
        print_log_dual("Erro na Cópia da pasta: ", str(e))
        print()
        sys.exit()
    print_log_dual("Cópia concluída com sucesso")

    # ------------------------------------------------------------------
    # Restaura o nome do arquivo XML na pasta destino
    # ------------------------------------------------------------------
    arquivo_xml_destino = caminho_destino + "/Relatório.xml_em_copia"
    arquivo_xml_destino_renomeado = caminho_destino + "/Relatório.xml"
    print_log("Restaurado nome de quivo [" + arquivo_xml_destino + "] para [" + arquivo_xml_destino_renomeado + "]")
    try:
        os.rename(arquivo_xml_destino, arquivo_xml_destino_renomeado)
    except BaseException as e:
        # Erro fatal
        print_log_dual("Rename falhou: ", str(e))
        print()
        sys.exit()
    print_log("Renomeado com sucesso")

    # ------------------------------------------------------------------
    # Valida pasta de destino, após copia
    # Não deveria ocorrer nenhum erro,
    # afinal a origem já foi validada.
    # ------------------------------------------------------------------

    (codigo_situacao_tarefa, texto_status, dados_relevantes) = determinar_situacao_item_cellebrite(explicar=True)

    # Atualiza o status da tarefa com o resultado
    print_log("Fork: Atualizando tarefa com: ", codigo_situacao_tarefa, "-", texto_status)
    (ok, erro) = atualizar_status_tarefa(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=codigo_situacao_tarefa,
        status=texto_status,
        dados_relevantes=dados_relevantes
    )
    if (not ok):
        print_log("Fork: Não foi possível atualizar tarefa: ", msg_erro)
        # Encerra a thread
        sys.exit()

    # Se foi concluído com sucesso, encerra fork
    if (codigo_situacao_tarefa == GFinalizadoComSucesso):
        # Encerra a thread
        print_log("Fork: Concluído em condições normais: situacao[", str(codigo_situacao_tarefa), "]")
        sys.exit()

    # Se abortou, também encerra
    if (codigo_situacao_tarefa == GAbortou):
        # Encerra a thread
        print_log("Fork: Encerrando pois abortou: situacao[", str(codigo_situacao_tarefa), "]")
        sys.exit()

    # Qualquer outro código, também encerra...
    # Não deveria acontecer nunca isto aqui
    print_log("Fork: Resultado de determinarSituacaoItemCellebrite é inesperado: ", str(codigo_situacao_tarefa), "]")
    print_log("Fork: Encerrando")
    sys.exit()

    # ==== FIM Jogar para background ============

    # ------------------------------------------------------------------
    # Faz um fork, para iniciar copia e liberar programa para continuar
    # ------------------------------------------------------------------
    pai = os.fork()
    if pai != 0:
        # Se é o processo pai, retorna para receber novo comando
        print("Cópia iniciada em background. Ao término, você será notificado através de mensagem na console")
        print()
        return

    # ------------------------------------------------------------------
    # PROCESSO FILHO
    # O processo pai já encerrou com return.
    #
    # Para encerrar o filho, utilizar exit.
    # Gravar andamento em logo.
    # Se quiser imprimir na tela, tudo bem, vai ficar meio confuso
    # mas funciona. Utilizar apenas em situações realmente necessárias.
    # ------------------------------------------------------------------

    pid_filho = os.getpid()
    print_log("Fork criado para efetuar copia e conferir resultado: ", pid_filho)

    # **** Continuar a parti daqui....
    # **** Fazer a cópia + atualizar status regularmente
    # **** Conferir resultado
    # **** Status de finalizado

    # Efetua cópia da pasta de origem dos relatórios para storage
    comando_sis = 'guymager cfg="' + caminho_arquivo_configuracao_local + '" log="' + caminho_arquivo_log + '"'

    # Problema: Quando mata o processo principal, os filhos também morrem
    # inclusive o guymager
    # Tentei varias opções, mas nada deu muito resultado
    # pid = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    # A opção abaixo também não funcionou....mata o guyimager quando interrompe o pai
    # pid = subprocess.Popen(comando, shell=True)

    # Faz mais um fork, para deixar o guyimager rodando independente
    # O processo pai executa o guymager, fica esperando, e depois encerra
    # quando o usuário abando o guymager
    # O filho (neto neste caso) fica acompanhando o andamento
    pai = os.fork()
    if pai != 0:
        print_log("invocado guymager: " + comando_sis)
        # Executa o guymager e fica esperando o resultado
        os.system(comando_sis)  # Se mata o pai, morre também...melhorar isto
        print_log("Retornou de guyimager. Encerrando pid")
        # Se terminou o guymager, encerra este processo
        sys.exit()
        return

    # ------------------------------------------------------------------
    # Acompanha o andamento da imagem, atualizando o status no servidor
    # ------------------------------------------------------------------

    pid_neto = os.getpid()
    print_log("Fork criado para controlar estado com pid = ", pid_neto)

    # Controlar a evolução e encerrar apenas quando houver finalização
    # Isto aqui é nova thread. Logo, para encerrar, sair com exit

    tempo_ultima_atualizacao = None
    while (True):
        # Pausa entre verificações de mudança de estado (segundos)
        time.sleep(30)

        # print()
        # print("Fork: Acordeix : %s" % time.ctime())

        # Verificar no log do guymager se usuário encerrou
        # Se não tem log do guymager, tem algo errado
        # Verifica no log da imagem, como está a situação
        # Se não tem log de imagem, aguarda
        # a) Em andamento
        # b) Concluída: Sucesso
        # c) Concluída: Abortada

        # Recupera situação do item
        (codigo_situacao_tarefa, texto_status) = determinarSituacaoItem(explicar=False)
        # print()
        # print("Situacao Atual: ",str(codigo_situacao_tarefa)," - ",texto_status)
        # print()

        # Atualiza status se estiver em andamento
        if (codigo_situacao_tarefa >= GEmAndamento):

            # Determina se deve atualizar o status baseado no tempo
            atualizar_agora = True
            if (tempo_ultima_atualizacao is not None):
                # Calcula o tempo desde a ultima atualizacao
                tempo = time.time() - tempo_ultima_atualizacao  # segundos
                # print_log("Debug: tempo = ", tempo)
                if (tempo < GtempoEntreAtualizacoesStatus):
                    # Espera um tempo antes de atualizar, para
                    # não sobrecarregar servidor com informação inútil
                    atualizar_agora = False
            # print_log("Debug: atualizar_agora=",atualizar_agora)

            # Se está andamento, atualiza com frequencia baixa
            # Caso contrário, atualiza imediatamente
            if (codigo_situacao_tarefa > GEmAndamento or atualizar_agora):
                print_log("Atualizando tarefa com: ", codigo_situacao_tarefa, "-", texto_status)
                (ok, erro) = atualizar_status_tarefa(
                    codigo_tarefa=codigo_tarefa,
                    codigo_situacao_tarefa=codigo_situacao_tarefa,
                    status=texto_status
                )
                if (not ok):
                    print_log("Fork: Não foi possível atualizar tarefa: ", msg_erro)
                    # Encerra a thread
                    sys.exit()

                tempo_ultima_atualizacao = time.time()

        # Se foi concluído com sucesso, encerrra fork
        if (codigo_situacao_tarefa == GFinalizadoComSucesso):
            # Encerra a thread
            print_log("Fork: Encerrando em condições normais: situacao[", str(codigo_situacao_tarefa), "]")
            sys.exit()

        # Se abortou, também encerra
        if (codigo_situacao_tarefa == GAbortou):
            # Encerra a thread
            print_log("Fork: Encerrando pois abortou: situacao[", str(codigo_situacao_tarefa), "]")
            sys.exit()


# Explicar=True: Faz com que seja exibida (print) a explicação
# Retorna tupla:
#   1) codigo_situacao_tarefa: Retorna o código da situação.
#      Se operação falhour, retorna -1 ou nulo
#      -1 ou nulo: Comando não foi executado
#   2) texto_situacao: Texto complementar da situação
#   3) dados_relevantes: Dados relevantes, para utilização em laudo
# ----------------------------------------------------------------------
def determinar_situacao_item_cellebrite(explicar=False):
    # Constantes de codigo_situacao
    erro_interno = -1

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
        print("Erro: ", msg_erro)
        print("Efetue refresh na lista de tarefa")
        return (erro_interno, "", {})

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
        return (erro_interno, "", {})

    # -----------------------------------------------------------------
    # Pasta de armazenamento do item no Storage
    # -----------------------------------------------------------------

    # Confirma que tem acesso ao storage escolhido
    (sucesso, ponto_montagem, erro) = acesso_storage_windows(tarefa["dados_storage"])
    if not sucesso:
        erro = "Acesso ao storage [" + ponto_montagem + "] falhou"
        print(erro)
        return (erro_interno, "", {})

    caminho_destino = ponto_montagem + tarefa["caminho_destino"]
    if_print_ok(explicar, "- Pasta de destino definida para este item no storage: ", caminho_destino)

    # Verifica se pasta de destino já existe
    if not os.path.exists(caminho_destino):
        status = "Não iniciado (sem pasta)"
        if_print_ok(explicar, "- Pasta de destino ainda não foi criada.")
        return (GSemPastaNaoIniciado, status, {})  # Não iniciado

    if_print_ok(explicar, "- Pasta de destino existente.")

    # Default, para algo que iniciou.
    # Mas irá verificar mais adiante, se está em estágio mais avançado
    # codigo_status = GPastaDestinoCriada
    # status = "Pasta criada"

    # Verificação básica da pasta, para ver se contém os arquivos típicos
    if not valida_pasta_relatorio_cellebrite(pasta=caminho_destino, explicar=explicar):
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
    (resultado, dados_relevantes) = validar_arquivo_xml(arquivo_xml, item=item["item"], explicar=explicar)
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
    atualizar = pergunta_sim_nao("Atualizar servidor com o status observado? ", default="n")
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
        '*ir': 'Pula para a tarefa com sequencial(Sq) indicado (ex: *ir 4, pula para a quarta tarefa da lista)',

        # Comandos relacionados com um item
        '*cr': 'Copia pasta de relatórios (Cellebrite) do computador local para storage, concluindo a tarefa corrente',
        '*si': 'Verifica situação da tarefa corrente, comparando situação real com a situação no servidor',
        '*du': 'Dump: Mostra todas as propriedades de uma tarefa (utilizado para Debug)',

        # Comandos gerais
        '*sg': 'Exibir situação atual das tarefas, conforme mantidas pelo servidor',
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
        l = entrada.split(" ", 2)
        comando_recebido = ""
        if (len(l) >= 1):
            comando_recebido = l[0]
        argumento_recebido = ""
        if (len(l) >= 2):
            argumento_recebido = l[1]

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
    print('-' * 129)

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

        # var_dump(i)
        # cabecalho
        if (q == 1):
            print('%2s %2s %6s %-30.30s %15s %-69.69s' % (
                " ", "Sq", "tarefa", "Situação", "Material", "Item : Descrição"))
            print('-' * 129)
        # Tarefa
        item_descricao = t["item"] + " : " + i["descricao"]
        print('%2s %2s %6s %-30.30s %15s %-69.69s' % (
            corrente, q, t["codigo_tarefa"], t["estado_descricao"], i["material"], item_descricao))

        if (q == Gicor):
            print('-' * 129)

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

# Iniciando
# ---------
print()
print("SAPI - Cellebrite (Versao " + Gversao + ")")
print("=========================================")
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
        print("Finalizado por comando do usuario")
        break

    # Executa os comandos
    # -----------------------

    # Comandos de navegação
    if (comando == '+'):
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
