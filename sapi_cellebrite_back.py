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
#  - Criação de pasta para armazenamento da extração no storage
#  - Validação dos dados do Cellebrite
#  - Cópia para pasta do storage
#  - Atualização do servidor da situação da tarefa
# Histórico:
#  - v1.0 : Inicial
#  - v1.7: Ajuste para versão de sapilib_0_7_1 que trata https
#  - v1.8: Ajustes para sapilib (controle de timeout e retentativas)
#  - v1.9: Utilização do robocopy para cópia e implementação da lixeira
#  - v2.0: Ajuste para SAPI 2.0 (multiunidades)
# ======================================================================================================================

# Módulos utilizados
# ====================================================================================================
from __future__ import print_function
import platform
import sys
import xml.etree.ElementTree as ElementTree
import multiprocessing
import signal


# Verifica se está rodando versão correta de Python
# ====================================================================================================
if sys.version_info <= (3, 0):
    sys.stdout.write("Versao do intepretador python (" + str(platform.python_version()) + ") inadequada.\n")
    sys.stdout.write("Este programa requer Python 3 (preferencialmente Python 3.5.2).\n")
    sys.exit(1)

# Roda apenas em Windows
if platform.system() != "Windows":
    sys.stdout.write("Este programa roda apenas em Windows.\n")
    sys.exit(1)

# =======================================================================
# GLOBAIS
# =======================================================================
Gprograma = "sapi_cellebrite"
Gversao = "2.0"

# Para gravação de estado
Garquivo_estado = Gprograma + "v" + Gversao.replace('.', '_') + ".sapi"

# Base de dados (globais)
GdadosGerais = dict()  # Dicionário com dados gerais
Gtarefas = list()  # Lista de tarefas


# Diversos sem persistência
Gicor = 1

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
    '*cs': 'Comparar (e ajustar) a situação da tarefa indicada no SETEC3 com a situação observada no storage',
    '*du': '(Dump) Mostrar todas as propriedades de uma tarefa (utilizado para Debug)',
    '*ex': 'Excluir tarefa',
    '*logt': 'Exibe log da tarefa',
    '*sto': 'Exibir pasta da tarefa no storage através do File Explorer',

    # Comandos exibição
    '*sg': 'Exibir situação atualizada das tarefas (com refresh do servidor). ',
    '*sgr': 'Exibir situação repetidamente (Loop) com refresh do servidor. ',

    # Comandos gerais
    '*s3': 'Abre SETEC3 na página da solicitação de exame corrente',
    '*s3g': 'Abre SETEC3 na página geral de pendências SAPI',
    '*tt': 'Trocar memorando',
    '*qq': 'Finalizar',

    # Comandos para diagnóstico de problemas
    '*log': 'Exibir log geral desta instância do sapi_cellebrite. Utiliza argumento como filtro (exe: *LG status => Exibe apenas registros de log contendo o string "status".',
    '*db': 'Ligar/desligar modo debug. No modo debug serão geradas mensagens adicionais no log.'

}

Gmenu_comandos['cmd_exibicao'] = ["*sg", "*sgr"]
Gmenu_comandos['cmd_navegacao'] = ["+", "-"]
Gmenu_comandos['cmd_item'] = ["*cr", "*sto" , "*cs", "*ab", "*ri","*ex", "*logt"]
Gmenu_comandos['cmd_geral'] = ["*s3", "*s3g", "*tt", "*qq"]
Gmenu_comandos['cmd_diagnostico'] = ["*db", "*log"]

# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi_lib_xxx.py, para evitar dependência
from sapilib_2_0 import *

# **********************************************************************
# PRODUCAO 
# **********************************************************************

# ======================================================================
# Funções Auxiliares específicas deste programa
# ======================================================================

# Recupera os componentes da tarefa correntes e retorna em tupla
# ----------------------------------------------------------------------
def obter_tarefa_item_corrente():
    # Não tem nenhuma tarefa na lista
    if len(Gtarefas)==0:
        return (None, None)

    x = Gtarefas[Gicor - 1]
    return (x.get("tarefa"), x.get("item"))


# # Retorna True se existe storage montado no ponto_montagem
# # =============================================================
# def storage_montado(ponto_montagem):
#     # Não existe ponto de montagem
#     if not os.path.exists(ponto_montagem):
#         return False
#
#     # Verifica se storage está montando
#     # Para ter certeza que o storage está montado, será verificado
#     # se o arquivo storage_sapi_nao_excluir.txt
#     # existe na pasta
#     # Todo storage do sapi deve conter este arquivo na raiz
#     arquivo_controle = ponto_montagem + 'storage_sapi_nao_excluir.txt'
#     if not os.path.isfile(arquivo_controle):
#         # Não existe arquivo de controle
#         return False
#
#     # Ok, tudo certo
#     return True


# # Separa pasta do nome do arquivo em um caminho
# # Entrada:
# #  Memorando_19317-16_Lava_Jato_RJ-12/item04Arrecadacao06/item04Arrecadacao06_imagem/item04Arrecadacao06.E01
# # Saída:
# #  - pasta: Memorando_19317-16_Lava_Jato_RJ-12/item04Arrecadacao06/item04Arrecadacao06_imagem
# #  - nome_arquivo: item04Arrecadacao06.E01
# # ----------------------------------------------------------------------
# def decompoe_caminho(caminho):
#     partes = caminho.split("/")
#
#     nome_arquivo = partes.pop()
#     pasta = "/".join(partes)
#
#     return (pasta, nome_arquivo)


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
    try:
        return _validar_arquivo_xml(caminho_arquivo, numero_item, explicar)
    except BaseException as e:
        trc_string=traceback.format_exc()
        erro=texto("[310]: Erro inesperado validação de arquivo XML. Assegure-se que o arquivo selecionado foi gerado corretamente pelo Cellebrite: ",
                   trc_string)
        print_log(erro)
        return (False, {}, [erro], [])



# Validar arquivo XML do cellebrite
# ----------------------------------------------------------------------
def _validar_arquivo_xml(caminho_arquivo, numero_item, explicar=True):
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
    versoes_homologadas=['5.2.0.0', '5.3.2.1', '5.5.2.1']
    if report_version not in versoes_homologadas:
        # Apenas um aviso. Continua
        mensagem = texto("Esta versão do relatório do cellebrite",
                    report_version,
                    "não faz parte das versões homologadas:",
                    versoes_homologadas)\
                    + "\n    Pode haver incompatibilidade e talvez alguns campos não sejam recuperados."\
                    + "\n    Se você observar que faltam campos, compare com o PDF, e se realmente estiver faltando, comunique o desenvolvedor"
        avisos += [mensagem]
        if_print(explicar, ">>> AVISO:", mensagem)
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
    #     if_print(explicar, "- AVISO: ", mensagem)

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
    if secao is None:
        mensagem=texto("Não foi encontrada seção Extraction Data.",
                       "Isto é incomum e pode ocasionar falha na recuperação de informações para o laudo. Confira se resultado está ok"
                       )
        avisos += [mensagem]
        if_print(explicar, "- AVISO: ", mensagem)
    else:
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
        if_print(explicar, "- AVISO: ", mensagem)

    if (qtd_extracao_sim == 0):
        mensagem = ("Não foi encontrada nenhuma extração com características de cartão 'SIM'." +
                    " Realmente não tem SIM Card?. ")
        avisos += [mensagem]
        if_print(explicar, "- AVISO: ", mensagem)

    if (qtd_extracao_sd > 0):
        mensagem = ("Sistema ainda não é capaz de inserir dados descritivos do cartão SD automaticamente no laudo.")
        avisos += [mensagem]
        if_print(explicar, "- AVISO: ", mensagem)

    if (qtd_extracao_backup > 0):
        mensagem = (
            "Sistema ainda não preparado para tratar relatório de processamento de Backup. Consulte desenvolvedor.")
        avisos += [mensagem]
        if_print(explicar, "- AVISO: ", mensagem)

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
    if secao is None:
        mensagem=texto("Não foi encontrada seção Device Info.",
                       "Isto significa que reconhecimento do dispositivo não foi efetuado"
                       )
        avisos += [mensagem]
        if_print(explicar, "- AVISO: ", mensagem)
    else:
        # Existe secao
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

            # MSIDN: número da linha armazenada no simcard
            # Pode ter mais de um campo com esta informação, por exemplo: MSISDN 1
            if 'MSISDN' in m['Name']:
                # Se contiver algo válido, armazena
                msisdn=m['Value']
                msisdn=msisdn.strip()
                if msisdn != 'N/A' and msisdn!="":
                    dext[extraction_id]['MSISDN'] = m['Value']
                # Valor default, caso não encontre nada
                if dext.get(extraction_id, None) is None or dext[extraction_id].get('MSISDN',None) is None:
                    dext[extraction_id]['MSISDN'] = 'Não disponível'


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
        # Dados gerais para 'reportVersion': '5.2.0.0'
        # ------------------------------------------
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
        'UserAccount': 'sapiUserAccount',
        # A princípio vamos pegar apenas o dado do SimCard...será que precisar o que está no seção do aparelho?
        # ,
        # Número telefonico associado ao aparelho (deve valer para quando tem apenas um SimCard?)
        # 'MSISDN': 'sapiMSISDN'

        # Nomes de campos para reportVersion="5.3.2.1
        # Dados da extração
        'DeviceInfoDetectedPhoneVendor':    'sapiAparelhoMarca',
        'DeviceInfoModelNumber':            'sapiAparelhoModelo',
        'DeviceInfoDetectedPhoneModel':     'sapiAparelhoModelo',
        'DeviceInfoOSType':                 'sapiAparelhoTipoSistemaOperacional',
        'DeviceInfoOSVersion':              'sapiAparelhoSistemaOperacional',
        'DeviceInfoSerial':                 'sapiAparelhoNumeroSerie',
        'DeviceInfoStorageCapacity':        'sapiAparelhoMemoriaTotal',

        # Dados sobre proprietário, mesclados em um único campo
        'DeviceInfoOwnerName':              'sapiAparelhoProprietario',
        'DeviblceInfoAppleID':              'sapiAparelhoProprietario'

        # No momento sem interesse...quem sabe no futuro
        # ----------------------------------------------

        #'DeviceInfoBackupPassword':         'sapiAparelhoSenhaBackup',
        #'DeviceInfoIsEncrypted':            'sapiAparelhoEncriptado',

        # Sobre icloud
        #'DeviceInfoiCloudAccountPresent':   'sapiAparelhoContaICloudPresente',
        #'DeviceInfoCloudBackupEnabled':     'sapiAparelhoContaBackupICloudHabilitado',
        #'DeviceInfoFindMyiPhoneEnabled':    'sapiAparelhoFindMyiPhoneEnabled'

        # 'DeviceInfoStorageAvailable':       'sapiAparelhoMemoriaLivre',
        #'Hora da última ativação':          'sapiAparelhoDataHoraUltimaAtivacao',

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
                elif 'UserAccount' in j:
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
            if_print(explicar, "- AVISO: ", mensagem)

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
    qtd = 0
    for i in dext:
        if not dext[i].get("sapiSIM", False):
            continue

        qtd = qtd + 1
        dcomp = dict()
        dcomp["sapiTipoComponente"] = "sim"
        # Ignora nome definido pelo PCF, pois normalmente é deixado apenas como "Lógica..."
        # nome = dext[i]["extractionInfo_name"]
        nome = "Cartão SIM"
        if qtd_extracao_sim>1:
            # Se tiver mais de um SIM, numera sequencialmente
            nome = "Cartão SIM " + str(qtd)

        dcomp["sapiNomeComponente"] = nome

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


# # Sanitiza strings em UTF8, substituindo caracteres não suportados pela codepage da console do Windows por '?'
# # Normalmente a codepage é a cp850 (Western Latin)
# # Retorna a string sanitizada e a quantidade de elementos que forma recodificados
# def sanitiza_utf8_console(dado):
#     #
#     codepage = sys.stdout.encoding
#
#     # String => ajusta, trocando caracteres não suportados por '?'
#     if isinstance(dado, str):
#         # Isto aqui é um truque sujo, para resolver o problema de exibir caracteres UTF8 em console do Windows
#         # com configuração cp850
#         saida = dado.encode(codepage, 'replace').decode(codepage)
#         # Verifica se a recodificação introduziu alguma diferença
#         qtd = 0
#         if saida != dado:
#             qtd = 1
#         return (saida, qtd)
#
#     # Dicionário,
#     if isinstance(dado, dict):
#         saida = dict()
#         qtd = 0
#         for k in dado:
#             (saida[k], q) = sanitiza_utf8_console(dado[k])
#             qtd += q
#         return (saida, qtd)
#
#     # Lista
#     if isinstance(dado, list):
#         saida = list()
#         qtd = 0
#         for v in dado:
#             (novo_valor, q) = sanitiza_utf8_console(v)
#             saida.append(q)
#             qtd += q
#         return (saida, qtd)
#
#     # Qualquer outro tipo de dado (numérico por exemplo), retorna o próprio valor
#     # Todo: Será que tem algum outro tipo de dado que precisa tratamento!?...esperar dar erro
#     saida = dado
#     return (saida, 0)
#

# Exibe dados para laudo, com uma pequena formatação para facilitar a visualização
# --------------------------------------------------------------------------------
def exibir_dados_laudo(d):
    print_centralizado(" Dados para laudo ")

    # Sanitiza, para exibição na console
    (d_sanitizado, qtd_alteracoes) = console_sanitiza_utf8(d)

    # Exibe formatado
    pp = pprint.PrettyPrinter(indent=4, width=Glargura_tela)
    pp.pprint(d_sanitizado)
    print_centralizado("")

    if qtd_alteracoes > 0:
        print("- AVISO: Em", qtd_alteracoes,
              "strings foi necessário substituir caracteres especiais que não podem ser exibidos na console por '?'.",
              "Isto não afetará o laudo.")

    return


def arquivo_existente(pasta, arquivo):
    caminho_arquivo = montar_caminho_longo(pasta, arquivo)
    return os.path.isfile(caminho_arquivo)


# Valida pasta de relatório do cellebrite
# Se o parâmetro explicar=True, irá detalhar os problemas encontrados
# Retorna: True/False
def valida_pasta_relatorios_cellebrite(pasta):
    # Verifica se pasta informada existe
    if not os.path.exists(pasta):
        print("- ERRO: Pasta informada não localizada")
        return False

    # Garante que existe apenas um arquivo XML na pasta
    # Não pode existir mais do que um, caso contrário procedimentos posteriores irão falhar
    qtd_arquivo_xml = 0
    for file in os.listdir(pasta):
        if file.endswith(".xml"):
            print("- Localizado arquivo XML: ",os.path.join(pasta, file))
            nome_arquivo_xml = file
            qtd_arquivo_xml=qtd_arquivo_xml+1

    if qtd_arquivo_xml>1:
        print("- ERRO: Não é permitido a existência de mais de um arquivo XML na pasta raiz do relatório do Cellebrite")
        return False

    # Listas de saída
    erros = list()
    avisos = list()

    # Remove a extensão XML, para identificar os demais arquivos com o mesmo prefixo
    # xxxx
    # PDF


    arquivo = "Relatório.pdf"
    if not arquivo_existente(pasta, arquivo):
        erros.append(texto("Não foi encontrado", arquivo, "na pasta", pasta))

    # HTML
    arquivo = "Relatório.html"
    if not arquivo_existente(pasta, arquivo):
        erros.append(texto("Não foi encontrado", arquivo, "na pasta", pasta))

    # Relatório em formato excel (pode ser xls ou xlsx)
    if not arquivo_existente(pasta, "Relatório.xlsx") and not arquivo_existente(pasta, "Relatório.xls"):
        erros.append(texto("Não foi encontrado Relatório compatível com excel (Relatório.xls ou Relatório.xlsx), na pasta", pasta))

    # XML tem que existir, para poder extrair dados para laudo
    arquivo = "Relatório.xml"
    if not arquivo_existente(pasta, arquivo):
        erros.append(texto("Não foi encontrado", arquivo, "na pasta", pasta))

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
            print("- AVISO: ", m)

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

    # Prepara campos
    situacao=str(tarefa["codigo_situacao_tarefa"])+ "-" + str(tarefa['descricao_situacao_tarefa'])

    # Exibe

    print()
    print_centralizado(" Tarefa " + str(tarefa["codigo_tarefa"]))
    # Dados gerais da tarefa
    print_formulario(label="Código da tarefa", largura_label=20, valor=tarefa["codigo_tarefa"])
    print_formulario(label="Storage", valor=tarefa['dados_storage']['maquina_netbios'])
    print_formulario(label="Pasta armazenamento", valor=tarefa['caminho_destino'])
    # -------- Material ---------
    print()
    print("──── ","Material"," ────")
    print_formulario(label="Item", valor=tarefa["dados_item"]["item_apreensao"])
    print_formulario(label="Material", valor=tarefa["dados_item"]["material"])
    print_formulario(label="Descrição", valor=tarefa["dados_item"]["descricao"])
    # Situação
    print()
    print("──── ","Situação"," ────")
    print_formulario(label="Situação", valor=situacao)
    if obter_dict_string_ok(tarefa, 'status_ultimo') != '':
        tempo_str = remove_decimos_segundo(obter_dict_string_ok(tarefa, 'tempo_desde_ultimo_status'))
        print_formulario(label="Último status", valor=obter_dict_string_ok(tarefa, 'status_ultimo'))
        print_formulario(label="Atualizado em",
              valor=remove_decimos_segundo(obter_dict_string_ok(tarefa, 'status_ultimo_data_hora_atualizacao')))
        print_formulario(label="Atualizado faz (*)", valor=tempo_str)
        print_formulario(label="", valor="(*) Tempo decorrido desde última atualização de status")
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
            print_log("[1073] Recuperação de dados atualizados do SETEC da tarefa",codigo_tarefa,"FALHOU: ", msg_erro)
            return None

    except BaseException as e:
        print_tela_log("[1077] Recuperação de dados atualizados do SETEC da tarefa", codigo_tarefa, "FALHOU: ", str(e))
        return None

    return tarefa

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
    if ambiente_desenvolvimento():
        print("- Abortando tarefa imediatamente pois está em ambiente de desenvolvimento (não precisa aguardar)")
    elif tempo_ultimo_status_segundos > 0 and tempo_ultimo_status_segundos < (minimo_minutos * 60):
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
    print("    - Consulte o log com a opção *LG (talvez esta máquina tenha perdido conexão com o SETEC3)")
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
            # Troquei por kill recursivo
            #Gpfilhos[ix].terminate()
            pid = Gpfilhos[ix].pid
            print_log("Finalizando processo", ix, "[", pid, "]")
            kill_processo_completo(pid)
            print_log("Finalizado com sucesso processo", ix, "[", pid, "]")

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

    permite_reiniciar=False
    if codigo_situacao_tarefa in (GFinalizadoComSucesso, GAbortou):
        permite_reiniciar=True

    if not permite_reiniciar:
        # Tarefas com outras situações não são permitidas
        print("- Tarefa com situação ", codigo_situacao_tarefa, "-",
              tarefa['descricao_situacao_tarefa'] + " NÃO pode ser reiniciada")
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
# @*logt - Exibir log de tarefa
# ----------------------------------------------------------------------------------------------------------------------

def exibir_log_tarefa(filtro_usuario):

    (tarefa, item) = obter_tarefa_item_corrente()
    if tarefa is None:
        print("- Não existe nenhuma tarefa corrente. Utilize *SG para dar refresh na lista de tarefas")
        return None

    codigo_tarefa = tarefa["codigo_tarefa"]

    print()
    print("- Exibir log da tarefa", codigo_tarefa)

    filtro_base=":"+codigo_tarefa+"]"
    exibir_log(comando='*logt',filtro_base=filtro_base, filtro_usuario=filtro_usuario, limpar_tela=False)

    return





# ----------------------------------------------------------------------------------------------------------------------
# @*ri - Reinicia execução de tarefa
# ----------------------------------------------------------------------------------------------------------------------
def reiniciar_tarefa():
    console_executar_tratar_ctrc(funcao=_reiniciar_tarefa)


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
        print("- Tarefa NÃO pode ser excluída, pois está em andamento.")
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
    codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])


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
    ponto_montagem = conectar_ponto_montagem_storage_ok(
        tarefa["dados_storage"],
        utilizar_ip=True,
        tipo_conexao='atualizacao')
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return

    caminho_destino = montar_caminho_longo(ponto_montagem, tarefa["caminho_destino"])

    print("- Pasta de destino no storage:")
    print(" ", tarefa["caminho_destino"])

    # Verifica se pasta de destino já existe
    limpar_pasta_destino = False
    if os.path.exists(caminho_destino):
        limpar_pasta_destino = True
        print_atencao()
        print()
        entradas = os.listdir(caminho_destino)
        print("- A pasta de destino da tarefa contém", len(entradas),"arquivos/subpastas.")
        # Vamos deixar isto aqui desabilitado,
        # pois se abrir a possibilidade dos PCFs criarem dados e deixarem dados em pastas do storage
        # em breve
        #print("- Esta pasta pode ser excluída (lixeira) ou movida para área de trabalho no storage.")
        #salvar_area_trabalho = pergunta_sim_nao("< Você gostaria de salvar esta pasta na área de trabalho? ", default="n")
        salvar_area_trabalho=False
        if not salvar_area_trabalho:
            print("- Esta pasta será movida imediatamente para a lixeira do SAPI.")
            print("- Posteriormente esta pasta será fisicamente excluída (garbage colector).")
            print()
    else:
        #print_atencao()
        print_tela_log("- Não existe pasta de destino no storage para esta tarefa")
        #print("- Se esta tarefa nunca foi iniciada, tudo bem. ")
        #print("- Isto pode acontecer se alguém com privilégio de administrador excluiu a pasta.")
        #print("- Se isto não aconteceu, então talvez o sistema de arquivos esteja corrompido ou ocorreu alguma inconsistência no SAPI.")
        #print("- Se você prosseguir, a tarefa será excluída no servidor, mas nenhuma ação será efetuada sobre a pasta 'desparecida'.")
        #prosseguir = pergunta_sim_nao("< Prosseguir? ", default="n")
        #if not prosseguir:
        #    return
        salvar_area_trabalho = False
        limpar_pasta_destino = False


    # ------------------------------------------------------------------------------------------------------------------
    # Destino na área de trabalho
    # ------------------------------------------------------------------------------------------------------------------
    pasta_trabalho_destino=None
    if salvar_area_trabalho:
        exibir_pasta_tarefa_file_explorer("trabalho")
        pasta_trabalho_destino = _selecionar_pasta_trabalho()
        if (pasta_trabalho_destino == ''):
            print("- Pasta de destino não informada.")
            print("- Comando cancelado.")
            return

    # ------------------------------------------------------------------------------------------------------------------
    # Efetuar exclusão da tarefa
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("Confirmação final")
    print("=================")
    print()
    print_atencao()
    print("- A exclusão de uma tarefa é um procedimento IRREVERSÍVEL, e afeta tanto o status da tarefa como sua pasta de destino.")
    if (codigo_situacao_tarefa==GAbortou):
        print("- Uma vez que esta tarefa está abortada, se você quiser executá-la novamente basta utilizar o comando de execução (exemplo: *CR).")
        print("- Se quiser reiniciar o status, utilize a opção *RI")

    print("- Se realmente quiser excluir, confira pela última vez se você está excluindo a tarefa desejada!!!")
    print()
    prosseguir = pergunta_sim_nao("< Excluir tarefa? ", default="n")
    if not prosseguir:
        return
    print()
    print("- Iniciando exclusão da tarefa")

    # Troca situação da tarefa
    # ------------------------
    if not troca_situacao_tarefa_ok(codigo_tarefa=codigo_tarefa,
                                    codigo_nova_situacao=GEmAndamento,
                                    texto_status="Excluindo tarefa por comando de usuário (*EX)"
                                    ):
        # Se falhar, encerra. Mensagens já foram dadas na função chamada
        return


    # Se houver pasta de dados da tarefa, efetua a exclusão
    pasta_destino = None
    if limpar_pasta_destino:
        # Move para lixeira ou pasta de trabalho de destino
        print_tela("- Excluindo pasta da tarefa. Aguarde...")
        (sucesso, pasta_destino) = _excluir_pasta_dados_tarefa(tarefa, ponto_montagem, pasta_trabalho_destino)
        if not sucesso:
            print("- Comando cancelado")
            return
        texto_status = texto("Dados da pasta movidos para lixeira:", pasta_destino)
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)

    # Ajusta no SETEC3
    try:
        # Exclui tarefa no SETEC3
        # -----------------------
        print_tela("- Excluindo tarefa no SETEC3...")
        sapisrv_excluir_tarefa(codigo_tarefa=codigo_tarefa)
    except BaseException as e:
        print_tela_log("- Não foi possível excluir tarefa: ", str(e))
        print_falha_comunicacao()
        return


    # Ok, exclusão finalizada
    print("- Tarefa excluída com sucesso")
    if pasta_destino!=None:
        print("- A pasta de dados de extração foi movida para a lixeira em", pasta_destino)
        print("- A lixeira é de uso temporário, sendo apagada (garbage coletor) quando houver necessidade de espaço.")
        print("- Desta forma, se for necessitar destes dados, utilize-os o quanto antes.")

    exibir_situacao_apos_comando()
    return



def _selecionar_pasta_trabalho():

    print()
    print("Pasta de trabalho")
    print("=================")
    print("- Na janela gráfica que foi aberta, selecione a pasta de trabalho.")
    print("- Preferencialmente selecione uma pasta que contenha o seu nome, para evitar confusão entre os diversos peritos.")

    # Solicita a pasta de origem
    root = tkinter.Tk()
    j = JanelaTk(master=root)
    pasta_trabalho = j.selecionar_pasta()
    root.quit()
    root.destroy()

    # Verifica se a pasta realmente está na área de trabalho
    #var_dump(pasta_trabalho)

    return pasta_trabalho



# Retorna True (se conseguiu excluir), False em caso contrário
def _excluir_pasta_dados_tarefa(tarefa, ponto_montagem, pasta_trabalho_destino=None):

    codigo_tarefa = tarefa["codigo_tarefa"]

    # Caminhos para cada um dos componentes
    pasta_memorando = montar_caminho_longo(ponto_montagem, tarefa["dados_solicitacao_exame"]["pasta_memorando"])
    pasta_item = montar_caminho_longo(pasta_memorando, tarefa["pasta_item"])
    pasta_tarefa = montar_caminho_longo(ponto_montagem, tarefa["caminho_destino"])

    try:

        # Move pasta da tarefa para lixeira
        # ---------------------------------
        if pasta_trabalho_destino is not None:
            pasta_destino = pasta_trabalho_destino
            os.rename(pasta_tarefa, pasta_trabalho_destino)
        else:
            (sucesso, pasta_destino, erro) = mover_lixeira_UNC(pasta_tarefa)
            if not sucesso:
                raise Exception("Movimentação da pasta da tarefa para a lixeira falhou:", erro)

        # Verifica se exclui com sucesso
        if os.path.exists(pasta_tarefa):
            print_log("Não foi possível excluir pasta da tarefa")
            raise Exception("Exclusão da pasta da tarefa falhou")

        # Exclusão da patas da tarefa efetuada com sucesso
        print("- Pasta da tarefa movida com sucesso para:", pasta_destino)
        print("- Verificando se pastas superiores devem ser excluídas. Aguarde...")

        # Se não sobrou mais nenhuma pasta abaixo da pasta do item, exclui a pasta do item também
        time.sleep(5)  # Pausa para dar tempo de excluir
        entradas = os.listdir(pasta_item)
        qtd_entradas = len(entradas)
        if (qtd_entradas == 0):
            print_log("Pasta do item", pasta_item, "também será excluída, pois já não contém mais nenhum arquivo")
            shutil.rmtree(pasta_item)
            if os.path.exists(pasta_item):
                print_log("Não foi possível excluir pasta do item")
                raise Exception("Exclusão da pasta do item falhou")
            else:
                print_log("Pasta do item excluída com sucesso")
        else:
            print_log("Pasta do item não foi excluída pois ainda contém ", qtd_entradas, "entradas: ", entradas)

        # Se não sobrou mais nenhuma pasta abaixo da pasta do memorando, exclui a pasta do memorando também
        time.sleep(5)  # Pausa para dar tempo de excluir
        entradas = os.listdir(pasta_memorando)
        qtd_entradas = len(entradas)
        if (qtd_entradas == 0):
            print_log("Pasta do memorando", pasta_memorando,
                      "também será excluída, pois não continha mais nenhuma entrada")
            shutil.rmtree(pasta_memorando)
            if os.path.exists(pasta_memorando):
                print_log("Não foi possível excluir pasta do memorando")
                raise Exception("Exclusão da pasta do memorando falhou")
            else:
                print_log("Pasta do memorando excluída com sucesso")

        # Se chegou aqui, sucesso
        return (True, pasta_destino)

    except OSError as e:
        print_tela_log("- [1750] ERRO: ", codigo_tarefa, ":" + str(e))
        return (False, "")

    except BaseException as e:
        print_tela_log("- [1751] ERRO: ", codigo_tarefa, ":" + str(e))
        return (False, "")


# @*ex - FIM ----------------------------------------------------------------------------------------------------------


# ---------------------------------------------------------------------------------------------------------------------
# Diversas funções de apoio
# ---------------------------------------------------------------------------------------------------------------------
def carrega_exibe_tarefa_corrente(exibir=True):

    # Recupera tarefa corrente
    (tarefa, item) = obter_tarefa_item_corrente()
    if tarefa is None:
        print("- Não existe nenhuma tarefa corrente. Utilize *SG para dar refresh na lista de tarefas")
        return None
    codigo_tarefa = tarefa["codigo_tarefa"]
    # Se tarefa foi excluída, não está disponível para ser utilizada
    if tarefa['excluida']=='f' is None:
        print("- Esta tarefa foi excluída. Utilize *SG para dar refresh na lista de tarefas")
        return None

    print("- Contactando SETEC3 para obter dados atualizados da tarefa",codigo_tarefa,": Aguarde...")

    tarefa=recupera_tarefa_do_setec3(codigo_tarefa)

    # Se não encontrar a tarefa
    # -------------------------
    if tarefa is None:
        # Tarefa não foi recuperada
        print_tela_log("- Não foi possível recuperar dados do servidor para tarefa",codigo_tarefa)
        print("- Talvez esta tarefa tenha sido excluída.")
        print("- Utilize *SG para atualizar a lista de tarefas.")
        print("- Consulte o log (*LG) em caso de dúvida.")
        return None

    # Ok, tarefa recuperada, exibe dados
    # ------------------------------------------------------------------
    if exibir:
        exibe_dados_tarefa(tarefa)

    # Retorna dados da tarefa
    return tarefa



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


# ======================================================================================================================
# @*sto - Exibe pasta da tarefa no storage invocando o File Explorer
# ======================================================================================================================



def exibir_pasta_tarefa_file_explorer(pasta_posicionar=None):

    print()
    print("- Exibir pasta da tarefa no storage")
    print()

    tarefa=carrega_exibe_tarefa_corrente(exibir=False)
    if tarefa is None:
        return False

    print("- Storage da tarefa: ", tarefa["dados_storage"]["maquina_netbios"])

    # Montagem de storage
    # -------------------
    # Confirma que tem acesso ao storage escolhido
    # print("- Verificando conexão com storage de destino. Aguarde...")

    ponto_montagem = conectar_storage_consulta_ok(tarefa["dados_storage"])
    #print('ponto2060')

    #ponto_montagem = conectar_ponto_montagem_storage_ok(
    #    dados_storage=tarefa["dados_storage"],
    #    utilizar_ip=False,
    #    com_letra_drive=True
    #)

    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return


    # Determina a pasta
    pasta=escolhe_pasta_para_abrir(ponto_montagem, tarefa, pasta_posicionar)

    # Abre pasta no File Explorers
    print("- Abrindo file explorer na pasta selecionada")
    os.startfile(pasta)
    print("- Pasta foi aberta no file explorer")



# Escolhe pasta para exibição, seguindo ordem: Tarefa, item, memorando, raiz do storage
def escolhe_pasta_para_abrir(ponto_montagem, tarefa, pasta_posicionar=None):


    # 0) Existe uma pasta predefinida
    if pasta_posicionar is not None:
        pasta = montar_caminho(ponto_montagem, pasta_posicionar)
        if os.path.exists(pasta):
            print("- Posicionado em pasta:", pasta_posicionar)
            return pasta

    # 1) Pasta da tarefa
    pasta_tarefa = montar_caminho(ponto_montagem, tarefa["caminho_destino"])
    print("- Pasta da tarefa:")
    print("  ", pasta_tarefa)
    if os.path.exists(pasta_tarefa):
        print("- Exibindo pasta da tarefa")
        return pasta_tarefa
    else:
        print("- Ainda não existe pasta para a tarefa")

    # 2) Pasta do item
    # Acho que aqui não faz sentido abrir como caminho longo
    pasta_item = montar_caminho(ponto_montagem,
                               tarefa["dados_solicitacao_exame"]["pasta_memorando"],
                               tarefa["pasta_item"])
    print("- Pasta do item:")
    print("  ", pasta_item)
    if os.path.exists(pasta_item):
        print("- Exibindo pasta raiz do item")
        return pasta_item
    else:
        print("- Ainda não existe pasta para o item")


    # 3) Pasta do memorando
    pasta_memorando = montar_caminho(
        ponto_montagem,
        tarefa["dados_solicitacao_exame"]["pasta_memorando"])
    print("- Pasta do exame:")
    print("  ", pasta_memorando)
    if os.path.exists(pasta_memorando):
        print("- Exibindo pasta da solicitação do exame")
        return pasta_memorando
    else:
        print("- Ainda não existe pasta para o exame")

    # Se chegou aqui, não tem jeito, tem que abrir na raiz do storage mesmo
    print("- Exibindo pasta raiz do storage")
    return ponto_montagem


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

    # Label para log
    definir_label_log('*cr:'+codigo_tarefa)

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
              tarefa['descricao_situacao_tarefa'] + " NÃO está apta para este comando.")
        print("- O comando *CR pode sera aplicado apenas para tarefas com situação 'Aguardando ação PCF' ou 'Abortada'.")
        print("- Se você precisa refazer esta tarefa (caso, por exemplo, tenha feito a cópia da pasta errada)")
        print("  utilize primeiramente o comando *RI para reiniciar a tarefa.")
        print("- Em caso de divergência, efetue em Refresh na lista de tarefas (*SG).")
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
    caminho_xml = _copia_cellebrite_parte1(tarefa)
    if (caminho_xml == ''):
        # Se não selecionou nada, pede novamente
        print()
        print("- Cancelado: Nenhum arquivo XML selecionado.")
        return

    # Chama segunda parte, recapturando o CTR-C
    try:
        return _copia_cellebrite_parte2(tarefa, caminho_xml)
    except KeyboardInterrupt:
        print()
        print("Operação interrompida pelo usuário com <CTR>-<C>")
        return False


def _copia_cellebrite_parte1(tarefa):
    # ------------------------------------------------------------------
    # Seleciona e valida pasta local de relatórios
    # ------------------------------------------------------------------
    # Solicita que usuário informe a pasta local que contém
    # os relatórios do Cellebrite para o item corrente
    caminho_origem = ""

    print()
    print("1) Arquivo em formato XML do Cellebrite")
    print("=======================================")

    # Antes de mais nada, conecta no storage
    conectar_storage_consulta_ok(dados_storage=tarefa["dados_storage"])

    print("- Na janela gráfica que foi aberta, selecione o arquivo XML")
    print("  gerado pelo cellebrite para o item desta tarefa.")
    print("- As demais saídas (XLS, PDF, HTML), se existirem, devem estar na mesma pasta deste arquivo")

    # XXXX
    # Cria janela para seleção de laudo
    root = tkinter.Tk()
    j = JanelaTk(master=root)
    caminho_xml = j.selecionar_arquivo([('XML files', '*.xml')], titulo="Selecione arquivo XML do Cellebrite")
    root.destroy()

    # Exibe arquivo selecionado
    if (caminho_xml == ""):
        print()
        print("- Nenhum arquivo XML foi selecionado.")
        print("- DICA: Utilize a geração de relatório do Cellebrite, com a opção de geração de saída em formato XML")
        return ""

    print("- Arquivo XML selecionado:", caminho_xml)

    return caminho_xml



# def _copia_cellebrite_parte1_original_deprecated(tarefa):
#     # ------------------------------------------------------------------
#     # Seleciona e valida pasta local de relatórios
#     # ------------------------------------------------------------------
#     # Solicita que usuário informe a pasta local que contém
#     # os relatórios do Cellebrite para o item corrente
#     caminho_origem = ""
#
#     print()
#     print("1) Pasta de relatórios cellebrite")
#     print("=================================")
#
#     # Antes de mais nada, conecta no storage
#     conectar_storage_consulta_ok(dados_storage=tarefa["dados_storage"])
#
#     print(
#         "- Na janela gráfica que foi aberta, selecione a pasta que contém os relatórios cellebrite relativos ao item desta tarefa.")
#     print("- Os arquivos de relatórios devem estar posicionados imediatamente abaixo da pastas informada.")
#
#     # Solicita a pasta de origem
#     root = tkinter.Tk()
#     j = JanelaTk(master=root)
#     caminho_origem = j.selecionar_pasta()
#     root.quit()
#     root.destroy()
#
#     return caminho_origem


def verifica_sapi_info(tarefa, pasta_contem_sapi_info):

    #var_dump(tarefa)
    #die('ponto2075')

    # Existe um arquivo sapi.info que contém informações sobre tarefas iniciadas para o objeto da pasta
    # Verifica se tem registro de alguma tarefa do sapi_cellebrite
    sapi_cellebrite_codigo_tarefa       = sapi_info_get(pasta_contem_sapi_info, 'sapi_cellebrite_codigo_tarefa')
    sapi_cellebrite_caminho_destino     = sapi_info_get(pasta_contem_sapi_info, 'sapi_cellebrite_caminho_destino')
    sapi_cellebrite_material            = sapi_info_get(pasta_contem_sapi_info, 'sapi_cellebrite_material')

    if (sapi_cellebrite_codigo_tarefa is None):
        # Não tem referência a nenhuma tarefa de aquisição.
        # Tudo certo, prossegue
        return True

    print_log("sapi.info contém sapi_cellebrite_codigo_tarefa com valor", sapi_cellebrite_codigo_tarefa)

    # Recupera dados da tarefa anterior
    tarefa_anterior = recupera_tarefa_do_setec3(sapi_cellebrite_codigo_tarefa)
    if tarefa_anterior is None:
        print_log("Não é possível avaliar sapi.info da tarefa indicada, pois a mesma não existe no servidor")
        print_log("Ignorando sapi.info")
        return True

    # Se a tarefa é a mesma, tudo bem
    # ---------------------------------------------------------------------------------------------------
    if (sapi_cellebrite_codigo_tarefa==tarefa['codigo_tarefa']):
        # Como é a mesma tarefa, isto indica que a tarefa está sendo reprocessada.
        # Talvez a execução anterior da tarefa tenha sido abortada
        print_log("sapi_cellebrite_codigo_tarefa igual à tarefa corrente. Tudo bem.")
        return True

    # Se a tarefa de aquisição anterior foi excluída, tudo bem
    # ---------------------------------------------------------------------------------------------------
    if tarefa_anterior["excluida"]=='t':
        # Tarefa anterior foi excluída
        # Possivelmente o usuário recriou as tarefas. Então, tudo bem
        print_log("sapi_cellebrite_codigo_tarefa é de tarefa excluída. Tudo bem.")
        return True

    # Exibe dados da tarefa de aquisição anterior
    # -------------------------------------------
    print()
    print('-------------------------------------------------------------------------')
    print("- Para esta pasta já foi anteriormente iniciada a execução de uma tarefa")
    print("- Tarefa anterior executada nesta pasta: ", sapi_cellebrite_codigo_tarefa)
    print("- Pasta de destino: ", sapi_cellebrite_caminho_destino)
    print("- Material associado: ", sapi_cellebrite_material)

    # Se tarefa de aquisição anterior foi concluída,
    # apenas emite apenas um aviso, e solicita confirmação
    # --------------------------------------------------------------------------------
    if (int(tarefa_anterior["codigo_situacao_tarefa"]) == GFinalizadoComSucesso):
        print_atencao()
        print("- A tarefa anterior de upload desta pasta foi concluída (ver dados acima).")
        print("- É INCOMUM que seja feito upload mais de uma vez da mesma pasta.")
        print("- Mais informações no arquivo sapi.info na pasta indicada.")
        print("- Assegure-se que você indicou o arquivo/pasta correto!!")
        print()
        prosseguir = pergunta_sim_nao("< Prosseguir?", default="n")
        if prosseguir:
            return True
        else:
            print("- Comando cancelado pelo usuário.")
            return False


    # Se a tarefa está executanto, bloqueia
    # ---------------------------------------------------------------------------------------------------
    if tarefa_anterior["executando"]=="t":
        print("- Para esta pasta já existe uma tarefa de upload (*CR) EM EXECUÇÃO, segundo o SETEC3.")
        print("- Não é permitido que uma mesma pasta seja copiada para duas tarefas.")
        print("- Se a cópia na prática já não está mais sendo executada (o sapi_cellebrite foi finalizado, por exemplo), ")
        print("  primeiramente aborte a tarefa que está em execução (*AB) e em seguida repita o procedimento.")
        print("- Comando cancelado")
        return False

    #var_dump(tarefa_aquisicao)
    #die('ponto2175')

    # Em outras situações, apresenta os dados e deixa o usuário decidir
    # ---------------------------------------------------------------------------------------------------
    print("- Último Status da tarefa anterior:", tarefa_anterior["status_ultimo"])
    print("- Status reportado em: ", tarefa_anterior["status_ultimo_data_hora_atualizacao"])
    print("- Baseado nos dados do SETEC3 esta tarefa não está em execução.")
    print()
    print_atencao()
    print("- Assegure-se que realmente não existe mais de um tarefa em execução para esta mesma pasta,")
    print("  pois isto pode gerar resultados inesperados.")
    print("- Em caso de dúvida, consulte o arquivo sapi.info, armazenado na pasta de origem.")
    print()
    prosseguir = pergunta_sim_nao("< Prosseguir?", default="n")
    if prosseguir:
        return True
    else:
        print("- Comando cancelado pelo usuário.")
        return False
    print()


# Segunda parte
def _copia_cellebrite_parte2(tarefa, caminho_xml):

    # Recupera pasta onde está arquivo XML
    caminho_origem = obter_pasta_pai(caminho_xml)
    print("- Pasta indicada (contém XML): ", caminho_origem)
    nome_arquivo_xml = os.path.basename(caminho_xml)

    # Remove extensão XML do arquivo
    nome_base = nome_arquivo_xml.replace(".XML","")
    nome_base = nome_base.replace(".xml","")


    # Verifica se pasta já está em processamento
    print("- Verificando situação da pasta")
    ok = verifica_sapi_info(tarefa, pasta_contem_sapi_info= caminho_origem)
    if not ok:
        # Mensagens já foram dadas durante a verificação do sapi.info
        return False

    codigo_tarefa = tarefa['codigo_tarefa']
    item = tarefa['dados_item']

    # Verificação básica da pasta, para ver se contém os arquivos típicos
    print()

    print("2) Detecção de saídas do Cellebrite")
    print("===================================")
    print("- Nome base para detecção de demais saídas:", nome_base)

    # Garante que existe apenas um arquivo XML na pasta
    # Não pode existir mais do que um, caso contrário procedimentos posteriores irão falhar
    qtd_arquivo_xml = 0
    for file in os.listdir(caminho_origem):
        # Arquivo XML na pasta
        if file.endswith(".xml"):
            # print_log("Localizado arquivo XML: ",os.path.join(caminho_origem, file))
            qtd_arquivo_xml=qtd_arquivo_xml+1
            continue

    # Se tiver mais de um XML, tem algum problema...
    if qtd_arquivo_xml>1:
        print("- ERRO: Foi encontrado mais de um arquivo com extensão .XML neste pasta. Isto NÃO é permitido.")
        return False


    # Verifica as extensões informadas
    formatos = list()
    for file in os.listdir(caminho_origem):

        # Verifica se o arquivo é outra saída do Cellebrite
        # Todas as saída do Cellebrite tem o nome base, com diferentes extensões
        nome_arquivo, extensao_arquivo = os.path.splitext(file)
        if nome_arquivo == nome_base:
            formatos.append(extensao_arquivo.replace(".",""))
            print("- Encontrado arquivo de saída:", file)

    # Se as saída mais comuns não foram geradas, solicita uma confirmação
    pedir_confirmacao_formatos = False
    if ("pdf" not in formatos):
        print("- Aviso: Formato PDF não foi encontrado")
        pedir_confirmacao_formatos = True
    if ("xls" not in formatos) and ("xlsx" not in formatos):
        print("- Aviso: Formato Excel (extensão XLS ou XLSX) não foi encontrado")
        pedir_confirmacao_formatos = True
    if ("html" not in formatos):
        print("- Aviso: Formato HTML não foi encontrado")
        pedir_confirmacao_formatos = True
    if not arquivo_existente(caminho_origem, "UFEDReader.exe"):
        print("- Aviso: Não foi encontrado UFEDReader.exe")
        pedir_confirmacao_formatos = True

    if pedir_confirmacao_formatos:
        prosseguir = pergunta_sim_nao("< Verifique se os avisos acima estão coerentes com o esperado. Prosseguir? ", default="n")
        if not prosseguir:
            return False


    print()
    print("3) Validação de arquivo XML")
    print("===========================")

    # Verifica se o arquivo XML contido na pasta de origem está ok
    print("- Validando arquivo XML: ")
    print(" ", caminho_xml)
    print("- Isto pode demorar alguns minutos, dependendo do tamanho do arquivo. Aguarde...")
    (resultado, dados_relevantes, erros, avisos) = processar_arquivo_xml(
        arquivo=caminho_xml,
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
    # Adiciona informação sobre outros tipos de saídas geradas
    # ------------------------------------------------------------------------------------------------------------------
    dados_relevantes['laudo']['sapiSaidasFormatos'] = ", ".join(formatos)
    dados_relevantes['laudo']['sapiSaidasPastaDestino'] = os.path.join(tarefa["caminho_destino"])
    dados_relevantes['laudo']['sapiSaidasNomeBase'] = os.path.join(nome_base)


    # ------------------------------------------------------------------------------------------------------------------
    # Conferência de dados
    # ------------------------------------------------------------------------------------------------------------------
    print("4) Conferência de dados extraídos para laudo")
    print("============================================")
    print("- Os seguintes dados foram extraídos para serem utilizados no laudo:")
    exibir_dados_laudo(dados_relevantes['laudo'])

    # Exibir dados
    print()
    print("──── ","Dados do material no Siscrim (para confronto)"," ────")
    print_formulario(label="Item", valor=tarefa["dados_item"]["item_apreensao"])
    print_formulario(label="Material", valor=tarefa["dados_item"]["material"])
    print_formulario(label="Descrição", valor=tarefa["dados_item"]["descricao"])

    # Exibe avisos, se houver
    if len(avisos) > 0:
        print()
        print_atencao()
        for mensagem in avisos:
            print("- AVISO: ", mensagem)

    print()
    print_centralizado('')
    print("- Verifique se os dados acima estão coerentes com o material examinado.")
    print("- Caso algum campo apresente divergência em relação aos relatórios do Cellebrite (PDF por exemplo),")
    print("  comunique o erro/sugestão de melhoria ao desenvolvedor.")
    print()
    prosseguir = pergunta_sim_nao("< Dados ok? ", default="n")
    if not prosseguir:
        return


    # ------------------------------------------------------------------------------------------------------------------
    # Método de cópia
    # ------------------------------------------------------------------------------------------------------------------
    # print()
    # print("4) Método de cópia")
    # print("==================")
    # print(" - O robocopy efetua cópia com robustez e velocidade, e permite retomada em caso de erro. ")
    # print("   Contudo, não oferece boa medição de progresso.")
    # print(" - A cópia tradicional via python/Windows é bem mais lenta e pode falhar para arquivos com nomes exóticos.")
    # print("   Porém oferece uma melhor medição de progresso.")
    # print()
    #
    # utilizar_robocopy = pergunta_sim_nao("< Utilizar robocopy para efetuar cópia? ", default="s")

    # Vamos deixar fixo...se der problema, reativar pergunta
    utilizar_robocopy=True
    # Parmetriza método de cópia
    log_copia = None
    if utilizar_robocopy:
        metodo_copia= 1
        label_metodo_copia='robocopy'
        log_copia = "sapi_log_robocopy_tarefa_" + str(codigo_tarefa) + ".txt"
    else:
        metodo_copia=2
        label_metodo_copia = 'python/windows'

    print_log("Método de cópia a ser utilizado: ", metodo_copia, label_metodo_copia)

    # -----------------------------------------------------------------
    # Pasta de destino
    # -----------------------------------------------------------------
    print()
    print("5) Confirmação final")
    print("====================")
    print("- Storage da tarefa: ", tarefa["dados_storage"]["maquina_netbios"])

    # Montagem de storage
    # -------------------
    # Confirma que tem acesso ao storage escolhido
    # print("- Verificando conexão com storage de destino. Aguarde...")
    ponto_montagem = conectar_storage_atualizacao_ok(dados_storage=tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return

    caminho_destino = montar_caminho_longo(ponto_montagem, tarefa["caminho_destino"])

    print()
    print(">>> Origem :", caminho_origem)
    print(">>> Destino:", tarefa["caminho_destino"])
    print()

    # Verifica se pasta de origem e pasta de destino estão no mesmo storage
    (caminho_origem_normalizado, origem_storage_ip, origem_pasta_storage) = normaliza_pasta_atualizacao_storage(caminho_origem)
    (caminho_destino_normalizado, destino_storage_ip, destino_pasta_storage) = normaliza_pasta_atualizacao_storage(caminho_destino)

    #var_dump(origem_storage_ip)
    #var_dump(destino_storage_ip)
    # Se estão no mesmo storage, e pasta de origem é lixeira, permite a movimentação
    # ao invés de cópia
    apenas_movimentar_pasta = False
    if origem_storage_ip == destino_storage_ip and "lixeira/" in origem_pasta_storage:
        print("- Verificou-se que pasta de origem e pasta de destino estão no mesmo storage e a pasta de origem está na lixeira.")
        print("- É possível efetuar uma cópia dos dados da pasta do origem,")
        print("  porém movimentar a pasta seria bem mais rápido")
        print()
        apenas_movimentar_pasta = pergunta_sim_nao("< Deseja simplesmente movimentar a pasta? ", default="s")

    if (apenas_movimentar_pasta):
        movimentar_pasta(codigo_tarefa, ponto_montagem, origem_pasta_storage, destino_pasta_storage, dados_relevantes)
    else:
        copiar_pasta(tarefa, codigo_tarefa, dados_relevantes, caminho_origem, caminho_destino, metodo_copia, label_metodo_copia, log_copia)

    # Fim normal
    return

def movimentar_pasta(codigo_tarefa,
                     ponto_montagem,
                     caminho_origem_normalizado,
                     caminho_destino_normalizado,
                     dados_relevantes):

    print("- Efetuando movimentação da pasta. Aguarde...")
    print_log("Movimentação de pasta no storage")

    # Adiciona storage no caminho
    caminho_origem_normalizado= montar_caminho(ponto_montagem, caminho_origem_normalizado)
    caminho_destino_normalizado= montar_caminho(ponto_montagem, caminho_destino_normalizado)
    print_log("Movimentar pasta de  ", caminho_origem_normalizado)
    print_log("Movimentar pasta para", caminho_destino_normalizado)


    # Move pasta temporária para pasta definitiva
    # -------------------------------------------------------------------------------
    try:

        # Verifica se pasta de origem existe
        if os.path.exists(caminho_destino_normalizado):
            print_log("Pasta de destino contém arquivos")
            print("- IMPORTANTE: A pasta de destino associada JÁ EXISTE: ", caminho_destino_normalizado)
            print("- Esta pasta será movida para a lixeira antes da movimentação")
            # Move pasta de destino para lixeira
            (movida, pasta_lixeira)=mover_lixeira(caminho_destino_normalizado)
            sapisrv_atualizar_status_tarefa_informativo(
                codigo_tarefa=codigo_tarefa,
                texto_status=texto("Pasta de destino atual foi movida para lixeira",
                                   pasta_lixeira)
            )

        # Move pasta temporária para definitiva
        sapisrv_atualizar_status_tarefa_informativo(
            codigo_tarefa=codigo_tarefa,
            texto_status="Movendo pasta no storage"
        )
        print_log("Movendo pasta", caminho_origem_normalizado, "para", caminho_destino_normalizado)
        mover_pasta_storage(caminho_origem_normalizado, caminho_destino_normalizado)
        print_log("Movimentação efetuada com sucesso")

    except Exception as e:
        # Isto não deveria acontecer nunca
        erro = "Não foi possível mover pasta: " + str(e)
        sapisrv_abortar_tarefa(codigo_tarefa, erro)
        print_tela_log("- Tarefa abortada: ",erro)
        print_tela_log("- Dica: Uma das causas mais comuns de falha de movimentação é haver algum arquivo aberto, ")
        print_tela_log("        ou até mesmo a pasta estar aberta no explorer, com algum arquivo sendo visualizado.")
        return

    # -----------------------------------------------------------------------------------------------------------------
    # Movimentação finalizada com sucesso
    # -----------------------------------------------------------------------------------------------------------------
    try:

        # Recupera características da pasta de destino
        carac_destino = obter_caracteristicas_pasta(caminho_destino_normalizado)

        # Troca para situação finalizada
        # -----------------------------------
        sapisrv_troca_situacao_tarefa_obrigatorio(
            codigo_tarefa=codigo_tarefa,
            codigo_situacao_tarefa=GFinalizadoComSucesso,
            texto_status="Dados copiados com sucesso para pasta de destino",
            dados_relevantes=dados_relevantes,
            tamanho_destino_bytes=carac_destino["tamanho_total"])

        print_log("Situação da tarefa atualizada com sucesso")

    except BaseException as e:
        print_tela_log("- Movimentação da pasta da tarefa", codigo_tarefa, "foi concluída")
        print_tela_log("- Contudo, NÃO FOI POSSÍVEL possível atualizar situação para 'Sucesso'")
        print_tela_log("- Esta tarefa ficará em estado inconsistente, pois para o sistema ainda está em execução")
        print_falha_comunicacao()
        print_tela_log("- Após sanar o problema, utilize comando *CS para atualizar situação da tarefa")
        return

    # Sucesso
    print_tela_log("- Tarefa concluída com sucesso (pasta movimentada)")
    return


def copiar_pasta(tarefa, codigo_tarefa, dados_relevantes, caminho_origem, caminho_destino, metodo_copia, label_metodo_copia, log_copia):

    # Verifica se pasta de destino já existe
    limpar_pasta_destino_antes_copiar = False
    # Para cópia tradicional, verifica se pasta de destino deve ser apagada
    if os.path.exists(caminho_destino):
        print_log("Pasta de destino contém arquivos")
        if metodo_copia==1: # Robocopy
            print("- Pasta de destino JÁ EXISTE")
            print("- Procedimento de cópia irá tornar a pasta de destino idêntica à pasta de origem")
            print("- Isto significa que arquivos da pasta de destino poderão ser excluídos, caso estes não estejam na pasta de origem (sincronização)")
        if metodo_copia==2: # Copia tradicional (python/Windows)
            print()
            print("- IMPORTANTE: A pasta de destino JÁ EXISTE:", caminho_destino)
            print()
            print("- Não é possível iniciar a cópia nesta situação para o método de copia python/windows.")
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


    #print_atencao()
    print("- Confira se a pasta de destino no storage (exibida acima) está bem formada,")
    print("  ou seja, se o memorando e o item estão ok,")
    print("  pois será assim que ficará gravado na mídia de destino.")
    print("- IMPORTANTE: Se a estrutura não estiver ok (por exemplo, o item está errado), cancele comando,")
    print("  ajuste no SETEC3 (*s3) e depois retome esta tarefa.")


    # -----------------------------------------------------------------
    # Confirmação final
    # -----------------------------------------------------------------
    print()
    prosseguir = pergunta_sim_nao("< Iniciar cópia? ", default="n")
    if not prosseguir:
        return

    print_log("Iniciando execução de comando de cópia (*cr)")

    # Troca situação da tarefa
    # ------------------------
    texto_status = texto(
        "Preparando para copiar",
        caminho_origem,
        "para",
        caminho_destino,
        "utilizando",
        label_metodo_copia)

    print_log(texto_status)
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

    #print("caminho_origem=", caminho_origem)
    #print("caminho_destino=", caminho_destino)
    #die('ponto2415')

    # Inicia processo filho para execução da cópia
    # ------------------------------------------------------------------------------------------------------------------
    label_processo = "executar:" + str(codigo_tarefa)
    dados_pai_para_filho=obter_dados_para_processo_filho()
    p_executar = multiprocessing.Process(
        target=background_executar_copia,
        args=(tarefa,
              codigo_tarefa,
              caminho_origem,
              caminho_destino,
              dados_relevantes,
              limpar_pasta_destino_antes_copiar,
              nome_arquivo_log_para_processos_filhos,
              label_processo,
              dados_pai_para_filho,
              metodo_copia,
              label_metodo_copia,
              log_copia
              )
    )
    p_executar.start()

    registra_processo_filho(label_processo, p_executar)

    # Tudo certo, agora é só aguardar
    print()
    print("- Ok, procedimento de cópia foi iniciado em background.")
    print("- Você pode continuar trabalhando, inclusive efetuar outras cópias simultaneamente.")
    print("- Para acompanhar a situação da cópia, utilize o comando *SG (Situação Geral), ou então *SGR (Situação Geral Repetitiva)")
    print("- Também é possível acompanhar a situação através do SETEC3 (*s3)")
    print("- Em caso de problema/dúvida, utilize *LG para visualizar o log")
    print("- IMPORTANTE: Não encerre este programa enquanto houver cópias em andamento, ")
    print("  pois as mesmas serão interrompidas e terão que ser reiniciadas")

    exibir_situacao_apos_comando(repetir=True)

    return



# Recebe uma pasta e ajusta para utilizá-la em operações de atualização
# - caminho_normalizado
# - storage: Se estiver em um storage conhecido pelo programa
# - pasta_storage: Pasta no storage
def normaliza_pasta_atualizacao_storage(pasta):

    # Remove notação UNC para caminho longo
    # ?\\UNC\\10.41.87.235\storage\pasta => \\10.41.87.235\storage
    pasta = remove_unc(pasta)

    # Trocar drive por notação de compartilhamento
    # Exemplo:
    #   Z:/pasta => \\gtpi-sto-03\storage\pasta
    for sto in Gdrive_mapeado:
        drive = Gdrive_mapeado[sto]
        if pasta[0:2] == drive:
            pasta = pasta.replace(drive, sto)

    # Troca nome netbios por IP
    # Exemplo:
    # \\gtpi-sto-03\storage\pasta => \\10.41.87.235\storage\pasta
    for ip in Gdic_storage:
        netbios = Gdic_storage[ip]
        pasta = pasta.replace(netbios, ip)

    # Localiza a palavra storage, que serve como separador
    partes  =str(pasta).split("\\storage")

    storage_ip = None
    storage_pasta = pasta
    if len(partes)>1:
        # Como é pasta do storage
        # Separa nos dois componentes necessários
        storage_ip = partes[0]
        storage_pasta = "".join(partes[1:])
        storage_pasta=storage_pasta.strip("/")
        storage_pasta=storage_pasta.strip("\\")

        # Troca referência ao storage de ip para netbios
        #storage = storage
        #for ip in Gdic_storage:
        #    netbios = Gdic_storage[ip]
        #    ip = ip + "\\storage"
        #    storage = storage.replace(ip, netbios)
        # Remove tudo que é desnecessário, retronando apenas o nome netbios do storage
        # Exemplo:
        # \\gtpi-sto-03\storage => gtpi-sto-03
        storage_ip = storage_ip.replace("\\storage","")
        storage_ip = storage_ip.strip("/")
        storage_ip = storage_ip.strip("\\")

    #var_dump(Gdic_storage)
    #var_dump(2675)

    return (pasta, storage_ip, storage_pasta)


# Determina se caminho de origem e destino estão no mesmo storage
# Em caso positivo, retorna também as pastas ajustadas, para o servidor
# - sucesso
# - origem_pasta: Pasta de origem  no servidor
# - destino_pasta Pasta de destino no srevidor
def origem_destino_mesmo_storage(caminho_origem, caminho_destino):

    #var_dump(Gdrive_mapeado)
    #var_dump(Gdic_storage)
    #die('ponto2641')

    caminho_servidor_origem  = caminho_origem[:]
    caminho_servidor_destino = caminho_destino[:]
    # Caminho origem, troca drive por \\xxxx\
    for sto in Gdrive_mapeado:
        drive = Gdrive_mapeado[sto]
        if caminho_servidor_origem[0:2] == drive:
            caminho_servidor_origem = caminho_servidor_origem.replace(drive, sto)

    # Remove unc
    caminho_servidor_destino = remove_unc(caminho_servidor_destino)

    # IP para nome netbios
    for ip in Gdic_storage:
        netbios = Gdic_storage[ip]
        caminho_servidor_destino = caminho_servidor_destino.replace(ip, netbios)

    # Separa os componente, antes e depois da palavra storage
    partes_origem  =str(caminho_servidor_origem).split("\\storage")
    partes_destino =str(caminho_servidor_destino).split("\\storage")
    if len(partes_origem)>1 and len(partes_destino)>1:
        origem_storage=partes_origem[0].strip()
        origem_pasta="".join(partes_origem[1:])
        destino_storage=partes_destino[0].strip()
        destino_pasta="".join(partes_destino[1:])
        # Remove "/", "\" do início, fim
        origem_pasta=origem_pasta.strip("/")
        origem_pasta=origem_pasta.strip("\\")
        destino_pasta=destino_pasta.strip("/")
        destino_pasta=destino_pasta.strip("\\")
        # Pastas de origem e destino compartilham o mesmo storage
        if (origem_storage==destino_storage):
            return (True, origem_pasta, destino_pasta)

    # Não estão no mesmo storage
    return (False, None, None)



# Efetua a cópia de uma pasta
def background_executar_copia(tarefa,
                              codigo_tarefa,
                              caminho_origem,
                              caminho_destino,
                              dados_relevantes,
                              limpar_pasta_destino_antes_copiar,
                              nome_arquivo_log,
                              label_processo,
                              dados_pai_para_filho,
                              metodo_copia,
                              label_metodo_copia,
                              log_copia
                              ):

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
    arquivo_xml_origem = montar_caminho_longo(caminho_origem, "Relatório.xml")
    arquivo_xml_origem_renomeado = arquivo_xml_origem + "_em_copia"
    sucesso=False
    erro = ''
    try:
        # 1) Marca início em background
        print_log("Início da cópia em background para tarefa", codigo_tarefa)

        # 2) Exclui pasta de destino antes de iniciar, se necessário
        # ------------------------------------------------------------------
        if limpar_pasta_destino_antes_copiar:
            texto_status = "Excluindo pasta de destino"
            sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)
            # Exclui pasta de destino
            print_log("Excluindo pasta", caminho_destino)
            shutil.rmtree(caminho_destino)
            # Verifica se excluiu com sucesso
            if os.path.exists(caminho_destino):
                raise Exception("Exclusão de pasta de destino falhou")

            # Ok, exclusão concluída
            texto_status = "Pasta de destino excluída"
            sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)

        # 3) Registra em sapi.info que tarefa foi iniciada (controle de concorrência)
        # ---------------------------------------------------------------------------
        sapi_info_set(caminho_origem, 'sapi_cellebrite_pasta_origem', caminho_origem)
        sapi_info_set(caminho_origem, 'sapi_cellebrite_codigo_tarefa', codigo_tarefa)
        sapi_info_set(caminho_origem, 'sapi_cellebrite_caminho_destino', caminho_destino)
        sapi_info_set(caminho_origem, 'sapi_cellebrite_solicitacao_exame', tarefa['identificacao_solicitacao_exame_siscrim'])
        sapi_info_set(caminho_origem, 'sapi_cellebrite_material', tarefa['dados_item']['identificacao'])


        # 4) Determina características da pasta de origem
        # ------------------------------------------------
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, "Calculando tamanho da pasta de origem")
        # Registra características da pasta de origem
        carac_origem = obter_caracteristicas_pasta(caminho_origem)
        tam_pasta_origem = carac_origem.get("tamanho_total", None)
        if tam_pasta_origem is None:
            # Se não tem conteúdo, aborta...
            # Isto não deveria acontecer nunca....
            raise Exception("Pasta de origem com tamanho indefinido")

        # Atualiza status com características da pasta de origem
        texto_status = "Pasta de origem com " + converte_bytes_humano(tam_pasta_origem) + \
                       " (" + str(carac_origem["quantidade_arquivos"]) + " arquivos)"
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)


        # 5) Inicia processo filho de acompanhamento da cópia
        # ------------------------------------------------------------------------------------------------------------------
        label_processo = "acompanhar:" + str(codigo_tarefa)
        p_acompanhar = multiprocessing.Process(
            target=background_acompanhar_copia,
            args=(codigo_tarefa,
                  caminho_origem,
                  caminho_destino,
                  nome_arquivo_log,
                  label_processo,
                  metodo_copia,
                  label_metodo_copia,
                  log_copia,
                  carac_origem))
        p_acompanhar.start()
        # Isto aqui não serve para nada, pois estamos em outro processo
        # Logo, vai registar em uma estrutura que não pode ser acessada pelo pai
        # Contudo, o método de kill tree deve conseguir localizar todos os processos
        # filhos e elminá-los
        registra_processo_filho(label_processo, p_acompanhar)

        # 6) Executa a cópia
        # ------------------------------------------------------------------
        tempo_copia_ini = time.time()
        texto_status=texto("Copiando via ", label_metodo_copia)
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)

        print_log("Copiando de:", caminho_origem)
        print_log("Copiando para:", caminho_destino)
        if metodo_copia==1:
            # Cópia via Robocopy
            caminho_log_robocopy = "sapi_log_robocopy_tarefa_" + str(codigo_tarefa) + ".txt"
            (sucesso, resultado_copia) = copiar_pasta_via_robocopy(caminho_origem, caminho_destino, caminho_log_robocopy)
        elif metodo_copia==2:
            # Cópia tradicional
            shutil.copytree(caminho_origem, caminho_destino)
            resultado_copia="Cópia efetuada por python/windows"
            sucesso=True # Supostamente se falhar irá gerar exception
        else:
            raise Exception("Opção de cópia com valor inválido" + str(metodo_copia))

        if not sucesso:
            raise Exception(texto("Cópia falhou:", resultado_copia))

        # Calcula taxa média
        tempo_decorrido = time.time() - tempo_copia_ini
        taxa_byte_por_segundos = int(tam_pasta_origem / tempo_decorrido)
        taxa_byte_por_segundos_humano = converte_bytes_humano(taxa_byte_por_segundos, 0)

        # Atualiza status indicativos de término da cópia
        texto_status = texto(resultado_copia,
                             "com taxa média:",
                             taxa_byte_por_segundos_humano + "/s"
                             )

        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status=texto_status)

        # 7) Confere se cópia foi efetuada com sucesso
        # ------------------------------------------------------------------
        # Compara tamanho total e quantidade de arquivos
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, "Conferindo cópia (tamanho e quantidade de arquivos)")

        carac_destino = obter_caracteristicas_pasta(caminho_destino)


        # Simula uma divergência
        #print_log("Simulando divergência entre origem e destino")
        #carac_destino["tamanho_total"] = carac_destino["tamanho_total"] + 1
        #carac_destino["quantidade_arquivos"] = carac_destino["quantidade_arquivos"] + 1
        # rrrr

        # Guarda detalhes no log
        print_log("Comparando características da pasta de origem com pasta de destino")
        print_log("Origem: ", var_dump_string(carac_origem))
        print_log("Destino: ", var_dump_string(carac_destino))

        # Efetuar comparação de características
        if carac_origem["tamanho_total"]==carac_destino["tamanho_total"]:
            print_log("Tamanho total confere")
        else:
            msg_exception=texto("Divergência entre tamanho total de origem (",
                                carac_origem["tamanho_total"],
                                ") e destino (",
                                carac_destino["tamanho_total"],
                                ")")
            raise Exception(msg_exception)

        if carac_origem["quantidade_arquivos"]==carac_destino["quantidade_arquivos"]:
            print_log("Quantidade de arquivos confere")
        else:
            msg_exception = texto("Divergência de quantidade de arquivos entre origem (",
                                  carac_origem["quantidade_arquivos"],
                                  ") e destino (",
                                  carac_destino["quantidade_arquivos"],
                                  ")")
            raise Exception(msg_exception)

        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, "Tamanho total e quantidade de arquivos compatíveis")



        # Se chegou aqui, sucesso
        # --------------------------------------------------------------------
        print_log("Cópia concluída com sucesso")
        sucesso=True

    except OSError as e:
        # Erro fatal: Mesmo estando em background, exibe na tela
        erro=texto("- [2581] ** ERRO na tarefa",
                   codigo_tarefa,
                   "durante cópia:",
                   str(e))
        print_tela_log(erro)
        print("- Consulte log para mais informações")
        sucesso=False

    except BaseException as e:
        # Erro fatal: Mesmo estando em background, exibe na tela
        trc_string=traceback.format_exc()
        erro=texto("- [2899] ** ERRO na tarefa", codigo_tarefa, "durante cópia:", str(e))
        print_tela_log(erro)
        print_log(trc_string)
        print("- Consulte log para mais informações")
        print("- Caso o problema persista, experimente:")
        print("  - Excluir primeiramente a tarefa (*EX) para limpar a pasta de destino, caso exista.")
        print("  - Copiar a pasta de origem para outra máquina, e executar novamente em outra máquina.")
        sucesso=False

    # -----------------------------------------------------------------------------------------------------------------
    # COPIA COM ERRO
    # -----------------------------------------------------------------------------------------------------------------
    if not sucesso:
        # Troca para situação Abortada
        try:
            sapisrv_troca_situacao_tarefa_obrigatorio(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=GAbortou,
                texto_status=texto("Cópia FALHOU: ", erro))
        except BaseException as e:
            # Se não conseguiu trocar a situação, avisa que usuário terá que abortar manualmente
            print_tela_log("- [1826] Não foi possível abortar a tarefa",codigo_tarefa, "automaticamente")
            print_tela_log("- Cópia falhou, e além disso, quando o sistema tentou atualizar situação para 'Abortada', isto também falhou")
            print_tela_log("- Tarefa está em situação inconsistente, como se estive executando, mas na realidade já foi abortada")
            print_tela_log("- Será necessário abortar manualmente (comando *AB)")
            print_falha_comunicacao()
            # Prossegue por gravidade, pois está em background e irá encerrar logo em seguida

        # Encerra
        os._exit(0)

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
            dados_relevantes=dados_relevantes,
            tamanho_destino_bytes=carac_destino["tamanho_total"])
        print_log("Situação da tarefa atualizada com sucesso")
    except BaseException as e:
        print_tela_log("- Cópia da tarefa", codigo_tarefa,"foi concluída")
        print_tela_log("- Contudo, NÃO FOI POSSÍVEL possível atualizar situação para 'Sucesso'")
        print_tela_log("- Esta tarefa ficará em estado inconsistente, pois para o sistema ainda está em execução")
        print("- Após sanar o problema, utilize comando *cs para atualizar situação da tarefa")
        print_falha_comunicacao()
        os._exit(0)

    # Tudo certo
    print()
    print("- Cópia de relatório para tarefa", codigo_tarefa, "foi concluída com SUCESSO")
    print("- Utilize comando *SG para conferir a situação atual da tarefa")
    print_log("Fim da cópia em background para tarefa", codigo_tarefa)
    os._exit(0)


# Acompanhamento de copia em background
def background_acompanhar_copia(codigo_tarefa,
                                caminho_origem,
                                caminho_destino,
                                nome_arquivo_log,
                                label_processo,
                                metodo_copia,
                                label_metodo_copia,
                                log_copia,
                                carac_origem
                                ):

    # Impede interrupção por sigint
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Inicializa sapilib, compartilhando o arquivo de log do processo principal
    sapisrv_inicializar(Gprograma, Gversao, nome_arquivo_log=nome_arquivo_log, label_processo=label_processo)
    print_log("Processo de acompanhamento de cópia iniciado")

    # Executa, e se houver algum erro, registra em log
    try:

        # simula erro
        #i=5/0

        if metodo_copia==1:
            # Acompanhamento de cópia via robocopy
            # Demora muito para dar uma primeiro sinal de vida...deixa usuário ansioso
            _background_acompanhar_copia_robocopy(codigo_tarefa, caminho_origem,
                                                          caminho_destino, log_copia, carac_origem)

        # Método tradicional, via python/windows
        if metodo_copia == 2:
            # Acompanhamento de cópia tradicional (python/Windows)
            _background_acompanhar_copia_tradicional(codigo_tarefa,
                                                     caminho_origem,
                                                     caminho_destino)




    except BaseException as e:
        # Erro fatal: Mesmo que esteja em background, exibe na tela
        trc_string=traceback.format_exc()
        erro=texto("[2746]: Acompanhamento de cópia falhou: ",
                   trc_string)
        print_tela_log(erro)

    # Encerra normalmente
    print_log("Processo de acompanhamento de cópia finalizado")
    os._exit(0)


# Processo em background para efetuar o acompanhamento da cópia
def _background_acompanhar_copia_tradicional(codigo_tarefa,
                                 caminho_origem,
                                 caminho_destino):

    print_log("Acompanhamento de cópia tradicional inativo")
    print_log("Requer revisão para voltar a funcionar")
    return

    start_time = time.time()

    print('ponto2762')
    # Recupera características da pasta de origem
    r=obter_caracteristicas_pasta(caminho_origem)
    tam_pasta_origem = None
    if r is not None:
        tam_pasta_origem = r.get("tamanho_total", None)
    if tam_pasta_origem is None:
        # Se não tem conteúdo, encerrra....Não deveria acontecer nunca
        raise Exception("[2027] Falha na obtençao do tamanho da pasta de origem")


    # Aguarda até ter sido criada a pasta de destino
    while True:
        if not os.path.exists(caminho_destino):
            dormir(15, 'Aguardando criação da pasta de destino')
            continue
        # Ok, pasta de destino foi criada
        break

    print('ponto2772')

    # Fica em loop enquanto tarefa estiver em situação EmAndamento
    tamanho_anterior=0
    primeira=True
    tempo_pausa = 15
    while True:

        print('ponto2793')
        # Intervalo entre atualizações de status
        if not primeira:
            #dormir(tempo_pausa, "Próxima atualização de status")
            pass
        primeira=False

        # Verifica se tarefa ainda está em estado de Andamento
        tarefa=recupera_tarefa_do_setec3(codigo_tarefa)
        if tarefa is not None:
            codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
            if codigo_situacao_tarefa != GEmAndamento:
                print_log("Interrompendo acompanhamento, pois situação da tarefa",codigo_tarefa,"foi modificada para",codigo_situacao_tarefa)
                return

        debug("Novo ciclo de acompanhamento de tarefa")

        # Verifica o tamanho atual da pasta de destino
        #tamanho_copiado = obter_tamanho_pasta_ok(caminho_destino)
        tempo_calc_tamanho_ini = time.time()
        carac_destino = obter_caracteristicas_pasta_ok(caminho_destino)
        tamanho_copiado = None
        if carac_destino is not None:
            print('ponto2803')
            tempo_calc_tamanho_fim = time.time()
            tempo_calc_tamanho = tempo_calc_tamanho_fim - tempo_calc_tamanho_ini
            tamanho_copiado = carac_destino.get("tamanho_total", 0)
            quantidade_arquivos = carac_destino.get("quantidade_arquivos", 0)
        if tamanho_copiado is None:
            print('ponto2810')
            print_log("Falha na obtençao do tamanho da pasta de destino")
            continue

        # Calcula o tempo para a próximoa pausa
        # 1/10 do tempo utiliza para efetuar o acompanhamento
        tempo_pausa = tempo_calc_tamanho * 10

        # Para teste, vamos acelerar
        tempo_pausa = tempo_calc_tamanho * 2

        tempo_pausa = int(tempo_pausa)

        print("ponto2784")
        print("tamanho_copiado = ", tamanho_copiado)
        print("tamanho_anterior=", tamanho_anterior)
        print("tamanho_copiado>tamanho_anterior = ", tamanho_copiado>tamanho_anterior)
        print("Novo tempo entre atualizações = ", tempo_calc_tamanho)

        # Só atualiza, se já tem algo na pasta
        # e se o tamanho atual é maior que o tamanho anterior
        # Ou seja, o primeiro tamanho (da primeira iteração) não será atualizado
        # Além disso, não atualiza se o tamanho estiver diminuindo
        # Isto evita atualizar quando o tamanho está diminuindo, durante a exclusão da pasta
        texto_status=""
        if tamanho_copiado>0:
            tamanho_copiado_humano = converte_bytes_humano(tamanho_copiado)
            percentual = (tamanho_copiado / tam_pasta_origem) * 100
            texto_status = "Copiado " + tamanho_copiado_humano + " (" + str(round(percentual, 0)) + "%)"
            texto_status += " (" + str(quantidade_arquivos) + " arquivos)"

            # Se já tem duas medições, calcula taxa
            if tamanho_anterior > 0 and tamanho_copiado > tamanho_anterior:
                tempo_decorrido = time.time() - start_time
                # Calcula taxa
                taxa_byte_por_segundos = tamanho_copiado/tempo_decorrido
                taxa_byte_por_segundos_humano = converte_bytes_humano(taxa_byte_por_segundos,0)
                # Calcula término previso
                termino_segundos = round((tam_pasta_origem-tamanho_copiado)/taxa_byte_por_segundos)

                # Atualiza status
                if (percentual>10):
                    texto_status += " Taxa: " + taxa_byte_por_segundos_humano + "/s"
                    texto_status += " Término: " + converte_segundos_humano(termino_segundos)

            # Atualiza status
            print_log(texto_status)
            sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)

            if percentual>=100:
                print_log("Encerrando acompanhamento, pois foi atingido 100%")
                return

        # Guarda tamanho atual
        tamanho_anterior=tamanho_copiado

        print("Novo tamanho_anterior = ",tamanho_anterior)
        print("ponto2819")



# Acompanhamento de cópia efetuada via robocopy
# Monitora o arquivo de log e efetua calculo aproxima de progresso,
# Um acompanhamento preciso da evolução da cópia é difícil,
# uma vez que o robocopy pré-aloca o espaço nos arquivos de destino
def _background_acompanhar_copia_robocopy(codigo_tarefa,
                                          caminho_origem,
                                          caminho_destino,
                                          log_copia,
                                          carac_origem):

    print_log("Acompanhamento de cópia via Robocopy")

    start_time = time.time()

    # Recupera características da pasta de origem
    tam_pasta_origem = carac_origem.get("tamanho_total", None)
    quantidade_arquivos_pasta_origem = carac_origem.get("quantidade_arquivos", None)
    if tam_pasta_origem is None or quantidade_arquivos_pasta_origem is None:
        # Se não tem conteúdo, encerrra....Não deveria acontecer nunca
        raise Exception("[2027] Falha na obtençao do tamanho da pasta de origem")

    # Aguarda até ter sido criada a pasta de destino
    while True:
        if not os.path.exists(caminho_destino):
            dormir(15, 'Aguardando criação da pasta de destino')
            continue
        # Ok, pasta de destino foi criada
        break

    # Fica em loop enquanto tarefa estiver em situação EmAndamento
    primeira=True
    tempo_pausa = 30
    quantidade_arquivos_processados_anterior = 0
    while True:

        # Intervalo entre atualizações de status
        if not primeira:
            dormir(tempo_pausa, "Próxima atualização de status")
            pass
        primeira=False

        # Verifica se tarefa ainda está em estado de Andamento
        tarefa=recupera_tarefa_do_setec3(codigo_tarefa)
        if tarefa is not None:
            codigo_situacao_tarefa = int(tarefa['codigo_situacao_tarefa'])
            if codigo_situacao_tarefa != GEmAndamento:
                print_log("Interrompendo acompanhamento, pois situação da tarefa",codigo_tarefa,"foi modificada para",codigo_situacao_tarefa)
                return

        # Analisa o log e determina a quantidade total de arquivos processados
        res=acompanhar_log_copia_robocopy(log_copia)
        if not res["sucesso"]:
            print_log("Analise do arquivo de log falhou: ", res.get("explicacao","") )
            continue

        # Estima quantidade de arquivos para o qual já foi iniciado a cópia
        quantidade_arquivos_processados = res.get("quantidade_arquivos_processados",0)
        # Despreza os registros de exclusão de arquivos (/mir)
        quantidade_arquivos_excluidos = res.get("quantidade_arquivos_excluidos",0)
        if quantidade_arquivos_excluidos >0:
            quantidade_arquivos_processados -= quantidade_arquivos_excluidos
        if quantidade_arquivos_processados==0:
            print_log("Arquivo de log do robocopy ainda não contém nenhum arquivo processado.")
            # É comum que o robocopy demore um pouco para escrever os primeiros registros no arquivo de log
            # Enquanto não tem dados no log, vamos ler direto da pasta da destino
            # Isto aqui também demora....também não funciona
            #print_log("Obtendo caracteristiscas da pasta de destino")
            #carac_destino = obter_caracteristicas_pasta_ok(caminho_destino)
            #if carac_destino is None:
            #    # Se falhar, ignora e tenta mais tarde
            #    print_log("Leitura de característica da pasta de destino falhou")
            #    continue
            #quantidade_arquivos_processados = carac_destino.get("quantidade_arquivos", 0)
            #print_log("Arquivos na pasta de destino = ", quantidade_arquivos_processados)

            # Mecanismo anti-ansiedades....serve para dar um número, indicando que a cópia foi iniciada
            # apenas para usuário não ficar ansioso
            # Calculando quantidade de arquivos copiados...não é a quantidade real
            taxa_dummy_bytes_segundo = 5*1024*1024 #5MB/s
            tempo_decorrido = time.time() - start_time
            tamanho_total_copiado_estimado = tempo_decorrido * taxa_dummy_bytes_segundo
            tamanho_medio_arquivo = tam_pasta_origem / quantidade_arquivos_pasta_origem
            quantidade_arquivos_copiados_estimados = int(tamanho_total_copiado_estimado / tamanho_medio_arquivo)

            # Fictício => Anti-ansiedade
            quantidade_arquivos_processados = quantidade_arquivos_copiados_estimados
            print_log("progresso estimado")

        # Se não houve progresso, ou em função de método conflituosos (direto da pasta x log)
        # houve um decréscimo no número de arquivo processados, ignora a atualização
        if quantidade_arquivos_processados < quantidade_arquivos_processados_anterior:
            continue

        # A medição de arquivos processados é bastante imprecisa
        # Logo, se a quantidade de arquivos processados igualar ou superar a quantidade de arquivos
        # na pasta de origem, é melhor abandonar o acompanhamento para evitar confusão
        if quantidade_arquivos_processados >= quantidade_arquivos_pasta_origem:
            return

        # Calcula o percentual de avanço
        percentual = (quantidade_arquivos_processados / quantidade_arquivos_pasta_origem) * 100
        percentual = round(percentual,1)
        #if percentual==0:
        #    # Despreza, se o percentual é muito baixo
        #    continue
        percentual_texto="("+str(percentual)+"%)"
        texto_status = texto("Arquivos copiados:", quantidade_arquivos_processados, percentual_texto)

        # Atualiza status
        print_log(texto_status)
        sapisrv_atualizar_status_tarefa_informativo(codigo_tarefa, texto_status)
        quantidade_arquivos_processados_anterior = quantidade_arquivos_processados

        # Depois que fez primeira atualização, diminui a frequencia
        tempo_pausa = GtempoEntreAtualizacoesStatus


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
    ponto_montagem=conectar_storage_consulta_ok(dados_storage=tarefa["dados_storage"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return (erro_interno, status, {}, erros, avisos)



    # Verifica se pasta de destino existe
    # -----------------------------------
    caminho_destino = os.path.join(ponto_montagem, tarefa["caminho_destino"])
    print("- Pasta de destino: ", caminho_destino)

    if not os.path.exists(caminho_destino):
        status = "Não iniciado (sem pasta)"
        print("- Pasta de destino ainda não foi criada.")
        return (GSemPastaNaoIniciado, status, {}, erros, avisos)  # Não iniciado

    print("- Pasta de destino existente.")

    # Procura arquivo XML
    # --------------------------------------------------------------------
    qtd_arquivo_xml = 0
    arquivo_xml = ""
    for file in os.listdir(caminho_destino):
        if file.endswith(".xml"):
            print("- Localizado arquivo XML: ",os.path.join(caminho_destino, file))
            arquivo_xml = file
            qtd_arquivo_xml=qtd_arquivo_xml+1

    msg_erro=""
    if qtd_arquivo_xml==0:
        msg_erro= "Não foi encontrado arquivo XML na pasta de destino no servidor"

    if qtd_arquivo_xml>1:
        msg_erro="Existe mais de um arquivo XML na pasta de destino no servidor"

    if msg_erro != "":
        status = msg_erro
        codigo_status = GAbortou
        print("-",status)
        return (codigo_status, status, {}, erros, avisos)

    # Ok, já tem todos os arquivos básicos
    status = "Pasta contém todos os arquivos básicos."
    print("-",status)

    # Valida arquivo xml
    # xxxx
    caminho_arquivo_xml = os.path.join(caminho_destino, arquivo_xml)
    print("- Validando XML. Isto pode demorar, dependendo do tamanho do arquivo. Aguarde...")
    (resultado, dados_relevantes, erros, avisos) = processar_arquivo_xml(
        arquivo=caminho_arquivo_xml,
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


def refresh_exibir_situacao():
    refresh_tarefas()
    exibir_situacao()
    return

def exibir_situacao_apos_comando(repetir=False):

    # Não vamos mais dar opção de repetir, quase ninguem utiliza
    print()
    pausa()
    refresh_exibir_situacao()
    return

    # Deixa usuário decidir se fará ou não exibição contínua
    print()
    continuo = pergunta_sim_nao("< Deseja entrar em modo de acompanhamento contínuo da situação das tarefas (*sgr)?","n")
    if not continuo:
        refresh_exibir_situacao()
        return

    # Modo de repetição contínuo. Fica em loop, até receber CTR-C
    exibir_situacao_repetir()
    return


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

    global Gicor

    # Antes de mais nada, sanitiza Gicor no range de tarefas
    # É possível que uma exclusão de tarefa tenha feito o Gicor ficar maior que o tamanho da lista
    # de tarefas
    if Gicor>len(Gtarefas):
        # Posiciona no primeiro
        Gicor=1
    if Gicor<1:
        Gicor=1

    # Cabeçalho da lista de elementos
    # --------------------------------------------------------------------------------
    if modo_debug():
        print()
    else:
        cls()
    print_linha_cabecalho()


    # Lista elementos
    # ----------------------------------------------------------------------------------
    q = 0
    q_sucesso = 0
    for dado in Gtarefas:


        q += 1
        t = dado.get("tarefa")
        i = dado.get("item")

        # Sinalizador de Corrente
        corrente = "  "
        if (q == Gicor):
            corrente = '=>'

        # Situacao
        if t['estado_descricao']=='Sucesso':
            q_sucesso = q_sucesso + 1

        situacao = t["estado_descricao"]
        # Se está em andamento, mostra o último status, se houver
        if int(t['codigo_situacao_tarefa']) == int(GEmAndamento) and t['status_ultimo'] is not None:
            situacao = t['status_ultimo']

        # Calcula largura da última coluna, que é variável (item : Descrição)
        # Esta constantes que está sendo subtraida é a soma de todos os campos e espaços antes do campo "Item : Descrição"
        lid = Glargura_tela - 78
        lid_formatado = "%-" + str(lid) + "." + str(lid) + "s"

        string_formatacao = '%2s %2s %6s %-50.50s %-13s ' + lid_formatado

        # cabecalho
        if (q == 1):
            print(string_formatacao % (
                " ", "Sq", "tarefa", "Situação da tarefa", "Material", "Item : Descrição"))
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

    print_centralizado()

    if q==0:
        print("*** Não existe nenhuma tarefa de extração para este exame ***")
        print()
        print("- Efetue a criação de tarefas no SETEC3 (comando *S3 para abrir diretamente o SETEC3)")

    if q_sucesso>0:
        print("- A situação 'Sucesso' indica apenas que a tarefa de upload foi realizada com sucesso.")
        print("  Esta tela não exibe o resultado das tarefas subsequentes (exemplo: IPED).")
        print("  Para um visão completa de todas as tarefas, consulte o SETEC3, utilizando o atalho *S3.")

    print()
    if comando=='':
        print("- Para recuperar a situação atualizada do servidor (Refresh), utilize os comando *SG ou *SGR (repetitivo)")


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

            # Sanitiza para utf8 na console
            # ignora os ajustes efetuados
            (linha, ajustes)=console_sanitiza_utf8(linha)

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


# ----------------------------------------------------------------------
# @*TT - Usuário seleciona a solicitação de exame
# ----------------------------------------------------------------------
def obter_solicitacao_exame():
    return console_executar_tratar_ctrc(funcao=_obter_solicitacao_exame)

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

        #matricula = input("< Entre com sua matrícula: ")
        #matricula = matricula.replace(".", "")
        #matricula = matricula.lower().strip()

        #if not matricula.isdigit():
        #    print("- Entre com seu número de matrícula (composto exclusivamente por dígitos)")
        #    continue

        matricula=obter_param_usuario("matricula")

        print()
        print("- Consultando suas solicitações de exame SAPI. Aguarde...")
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
                "- Não existe nenhuma solicitacao de exame com tarefas SAPI para esta matrícula. Verifique no setec3")
            print()
            abrir_setec3 = pergunta_sim_nao("< Deseja abrir página SAPI do SETEC3? ", default="s")
            if abrir_setec3:
                abrir_browser_setec3_sapi()

            print()
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
    print("  vá para SETEC3 (utilizando o comando *s3g), localize a solicitação de exame desejada, ")
    print("  e prepare a solicitação de exame para o SAPI, definindo as tarefas a serem executadas.")

    # Usuário escolhe a solicitação de exame de interesse
    # --------------------------------------------------------
    tarefas = None
    while True:
        #
        print()
        num_solicitacao = input(
            "< Indique o número de sequência (Sq) da solicitação na lista acima (ou digite *s3g => SAPI no SETEC3): ")
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
        #if (len(Gtarefas) == 0):
            #print()
            #print("- Esta solicitação de exame NÃO TEM NENHUMA TAREFA DE EXTRAÇÃO. Verifique no SETEC3.")
            #print()
            # Continua no loop
            #continue

        # Muda log para o arquivo com nome
        partes=solicitacao["identificacao"].split('-')
        nome_arquivo_log="log_sapi_cellebrite_"+partes[0]+"_"+solicitacao["codigo_documento_externo"]+".txt"
        # Sanitiza, removendo e trocando caracteres especiais
        nome_arquivo_log=nome_arquivo_log.replace('/','-')
        nome_arquivo_log=nome_arquivo_log.replace(' ','')

        renomear_arquivo_log_default(nome_arquivo_log)

        # Tudo certo, interrompe loop e retorna
        return True


def refresh_tarefas():
    # Irá atualizar a variáel global de tarefas
    global Gtarefas
    global GdadosGerais
    global Gicor

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

    # Insucesso. Algo estranho aconteceu
    if (not sucesso):
        # Sem sucesso
        print_log("[1073] Recuperação de situação de tarefas FALHOU: ", msg_erro)
        return False

    # Guarda na global de tarefas
    Gtarefas = tarefas

    # Ajusta índice, pois pode ter ocorrido exclusão de tarefas, deixando o índice com valor inválido
    if Gtarefas is None or Gicor>len(Gtarefas):
        Gicor=1

    # Guarda data hora do último refresh de tarefas
    GdadosGerais["data_hora_ultima_atualizacao_status"] = datetime.datetime.now().strftime('%H:%M:%S')

    return True


# Exibir informações sobre tarefa
# ----------------------------------------------------------------------
def dump_tarefa():

    # Carrega situação atualizada da tarefa
    # -----------------------------------------------------------------------------------------------------------------
    tarefa = carrega_exibe_tarefa_corrente()
    if tarefa is None:
        return False

    print("===============================================")
    var_dump(tarefa)
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
            # Gpfilhos[ix].terminate()
            kill_processo_completo(Gpfilhos[ix].pid)
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
                print("- Você está em modo *SGR, com refresh repetitivo da situação geral das tarefas a cada", intervalo, "segundos.")
                print("- Uma vez que a maioria dos procedimentos atualizam o status no servidor apenas a cada 3 minutos,")
                print("  é normal que em alguns ciclos não haja alteração da situação.")
                print("- Utilize <CTR><C> para sair deste modo e voltar ao menu de comandos")
            time.sleep(intervalo)

    except KeyboardInterrupt:
        print()
        print("Saindo de modo *SGR")
        return


def acompanhar_log_copia_robocopy(caminho_log_robocopy):

    # Dicionário de resultado
    res = dict()
    res["sucesso"]=False
    res["quantidade_arquivos_processados"]=0
    res["quantidade_arquivos_excluidos"]=0
    res["explicacao"]=""

    # Arquivo de log não existe
    if not os.path.isfile(caminho_log_robocopy):
        res["explicacao"] = "Arquivo não existe"
        return res


    # Procurar por linha que contem tamanho
    quantidade_arquivos_processados = 0
    quantidade_arquivos_excluidos = 0
    with open(caminho_log_robocopy, "r") as fentrada:
        for linha in fentrada:
            #print_sanitizado(linha)

            # Despreza linhas pequenas, que normalmente contém apenas um percentual
            if len(linha)<10:
                continue

            # Como o robocopy está rodando com /mir
            # é possível que a pasta de destino contenha arquivos que serão excluídos
            # durante o procedimento
            if "*Arquivo EXTRA" in linha:
                quantidade_arquivos_excluidos = quantidade_arquivos_excluidos + 1

            # Está no logo, considerada como processado
            # Isto não significa que a cópia foi concluída
            quantidade_arquivos_processados=quantidade_arquivos_processados+1


    # Tudo certo
    res["sucesso"]=True
    res["quantidade_arquivos_processados"]=quantidade_arquivos_processados
    res["quantidade_arquivos_excluidos"]=quantidade_arquivos_excluidos
    return res



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
    print("- Se a linha de separador ---- está sendo dividida/quebrada,")
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

    if not login_sapi():
        return False


    #caminho_log_robocopy="log_teste.txt"
    #resultado=acompanhar_log_copia_robocopy(caminho_log_robocopy)
    #var_dump(resultado)
    #die('ponto3673')

    #caminho="\\\\10.41.87.235\\storage\\Memorando_5917-17_XXX_YYY\\item1a\\item1a_extracao9\\"
    #carac=obter_caracteristicas_pasta_python(caminho)
    #var_dump(carac)
    #die('ponto3674')

    # Teste de calculo do tamanho de pasta através do Robocopy
    #caminho_origem = "I:/desenvolvimento/sapi/dados_para_testes/relatorios_cellebrite/00_pequeno_XML_danificado"
    #tamanho=obter_tamanho_pasta_ok(caminho_origem)
    #print(tamanho)
    #die('ponto3692')


    # Teste de copia via Robocopy
    #caminho_origem  = "I:/desenvolvimento/sapi/dados_para_testes/relatorios_cellebrite/00_pequeno_XML_danificado"
    #caminho_destino = "I:/desenvolvimento/sapi/dados_para_testes/relatorios_cellebrite/teste_robocopy_"+str(time.time())
    #codigo_tarefa = 1234
    #caminho_log = "log_robocopy.txt"
    #(resultado, explicacao)=copiar_pasta_via_robocopy(caminho_origem, caminho_destino, caminho_log)
    #var_dump(resultado)
    #var_dump(explicacao)
    #die('ponto3814')


    #caminho_unc_pasta="\\\\10.41.87.235\\storage\\teste\\copia131"
    #(sucesso, pasta_lixeira, erro) = mover_lixeira_UNC(caminho_unc_pasta)
    #if sucesso:
    #    print("- Pasta da tarefa foi movida para lixeira no storage:", pasta_lixeira)
    #else:
    #    print("- Movimentação da pasta da tarefa para a lixeira falhou: ", erro)
    #die('ponto3848')

    # Teste
    #atualizar_status_tarefa_andamento(465, 'bla, bla')
    #atualizar_status_tarefa_andamento(465, 'status2')
    #die('ponto2832')

    # Carrega o estado anterior
    # -----------------------------------------------------------------------------------------------------------------
    # Obtem lista de tarefas, solicitando o memorando
    if not (obter_solicitacao_exame()):
        # Se usuário interromper sem selecionar, finaliza
        print("- Execução finalizada.")
        # sys.exit()
        return


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
                print_log("Finalizado por comando de usuário (*qq)")
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

        # Comandos de tarefa
        if (comando == '*du'):
            dump_tarefa()
            continue
        elif (comando == '*cr'):
            copiar_relatorio_cellebrite()
            continue
        elif (comando == '*sto'):
            exibir_pasta_tarefa_file_explorer()
            continue
        elif (comando == '*cs'):
            comparar_sistema_com_storage()
            continue
        elif (comando == '*logt'):
            exibir_log_tarefa(filtro_usuario=argumento)
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
        elif (comando == '*log'):
            exibir_log(comando='*log', filtro_base='', filtro_usuario=argumento)
            continue
        elif (comando == '*s3'):
            abrir_browser_setec3_exame(GdadosGerais["codigo_solicitacao_exame_siscrim"])
            continue
        elif (comando == '*s3g'):
            abrir_browser_setec3_sapi()
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
                exibir_situacao()
                continue

                # Loop de comando

    # Encerrando conexão com storage
    print()
    desconectar_todos_storages()

    # Finaliza
    print()
    print("FIM SAPI Cellebrite - Versão: ", Gversao)




if __name__ == '__main__':


    # Teste de movimentação no storage
    #pasta_origem="\\\\10.41.87.235\\storage\\teste\\copia2"
    #pasta_destino="\\\\10.41.87.235\\storage\\teste\\copia1xx"

    #pasta_pai_destino="\\\\10.41.87.235\\storage\\lixeira\\xxx\\"
    #if not os.path.exists(pasta_pai_destino):
    #    os.makedirs(pasta_pai_destino)

    #pasta_destino=pasta_pai_destino+"copia1"
    #print("pasta_origem=",pasta_origem)
    #print("pasta_destino=",pasta_destino)

    #os.rename(pasta_origem, pasta_destino)
    #die('ponto3828')


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

    #path="\\\?\\UNC\\10.41.87.235\\storage\\Memorando_5917-17_XXX_YYY\\item1b\\item1b_extracao"
    #pasta = path
    #pasta = remove_unc(pasta)
    #print(pasta)
    #if os.path.exists(pasta):
    #    print("Existe")
    #else:
    #    print("Não existe")
    #die('ponto4116')

    #caminho_destino="H:/sapi_dados_para_testes/dados_cellebrite/00.000 XML_livre"
    #carac_destino_1 = obter_caracteristicas_pasta(caminho_destino)
    #carac_destino_2 = obter_caracteristicas_pasta_via_dirdos(caminho_destino)
    #print("-"*50)
    #var_dump(carac_destino_1)
    #var_dump(carac_destino_2)
    #die('ponto4294')

    main()

    print()
    espera_enter("Programa finalizado. Pressione <ENTER> para fechar janela.")
