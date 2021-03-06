﻿# -*- coding: utf-8 -*-
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
# Histórico:
#  - v1.0 : Inicial
#  - v1.3 (2017-05-16 Ronaldo): Ajuste para sapilib_0_7_1
#  - v1.4 (2017-05-17 Ronaldo):
#    Substituição de variáveis por blocos em respostas aos quesitos
#  - v1.5 (2017-05-22 Ronaldo):
#    sapi_lib_0_7_2 que efetua checagem de versão de programa
#  - V2.1 (2017-11-07 Ronaldo):
#    * Laudo tanto de celular como de mídias de armazenamento
#  - V2.3 (2018-08-16 Ronaldo):
#    * Tratamento para versão 2.0 do sapi, com múltiplas únidades.
#    * Criação de modo --config
#    * Geração automatica de modelo de laudo para unidades.
# =======================================================================


# Módulos utilizados
# ====================================================================================================
from __future__ import print_function
import platform
import sys
import xml.etree.ElementTree
import zipfile
import multiprocessing

# Verifica se está rodando versão correta de Python
# ====================================================================================================
if sys.version_info <= (3, 0):
    sys.stdout.write("Versao do intepretador python (" + str(platform.python_version()) + ") inadequada.\n")
    sys.stdout.write("Este programa requer Python 3 (preferencialmente Python 3.5.2).\n")
    sys.exit(1)

# =======================================================================
# GLOBAIS
# =======================================================================
Gprograma = "sapi_laudo"
Gversao = "2.3"
Gmodelo_versao_esperado = "MODELO_VERSAO_2_3"

# Para gravação de estado
Garquivo_estado = Gprograma + "v" + Gversao.replace('.', '_') + ".sapi"

# Wiki
Gwiki_sapi = "http://10.41.84.5/wiki/index.php/SAPI_Manual_de_instalação_e_configuração"

# Base de dados (globais)
GdadosGerais = dict()  # Dicionário com dados gerais
Glaudo = None
Gitens = list()  # Lista de itens do laudo
Gstorages = None
Gsolicitacao_exame = None
Gmateriais_solicitacao = None
Gstorages_laudo = list()  # Lista de storages associados a tarefas do laudo


# Variáveis atualizadas durante a carga de um modelo SAPI
Gmod_constantes             = None
Gmod_ignorar_quesitacoes    = None
Gmod_blocos                 = None
Gmod_lista_cv               = None
Gmod_tabelas                = None
Gmod_quesitos_respostas     = None

# Relativo a mídia de destino
Gitem_midia=dict()
Gresumo_midia=dict()

# Diversos sem persistência
Gicor = 1

# ---------------------------------------------------------
# Menu de usuário
# ---------------------------------------------------------
Gmenu_comandos = dict()
Gmenu_comandos['comandos'] = {
    # Comandos de navegacao
    '+': 'Navega para a tarefa seguinte da lista',
    '-': 'Navega para a tarefa anterior da lista',

    # Comandos relacionados com um item
    '*si': 'Exibe dados de laudo para o item corrente',
    '*du': 'Dump: Mostra todas as propriedades de uma tarefa (utilizado para Debug)',

    # Comandos exibição
    '*sg': 'Exibir situação atualizada das tarefas (com refresh do servidor). ',

    # Comandos para diagnóstico de problemas
    '*db': 'Ligar/desligar modo debug. No modo debug serão geradas mensagens adicionais no log.',
    '*lg': 'Exibir log geral.',

    # Comandos gerais
    '*ml': 'Geração de modelo de laudo SAPI (Siscrim)',
    '*gl': 'Gera laudo',
    '*s3': 'Abrir solicitação de exame no SETEC3',
    '*s3g': 'Abrir lista de Pendências SAPI no SETEC3',
    '*sto': 'Exibir pasta da solicitaçaõ de exame no storage através do File Explorer',
    '*cl': 'Exibir laudo no SISCRIM',
    '*tt': 'Troca laudo',
    '*qq': 'Finaliza'
}

Gmenu_comandos['cmd_exibicao'] = ["*sg"]
Gmenu_comandos['cmd_navegacao'] = ["+", "-"]
Gmenu_comandos['cmd_item'] = ["*si"]
Gmenu_comandos['cmd_geral'] = ['*ml', '*gl', '*s3', '*s3g', '*sto', '*cl',  '*tt', '*qq']
Gmenu_comandos['cmd_diagnostico'] = ['*lg', '*db']

# ---------------------------------------------------------
# Menu de Administrador
# ---------------------------------------------------------
Gmenu_admin = dict()
Gmenu_admin['comandos'] = {
    # Comandos de navegacao
    '+': 'Navega para a tarefa seguinte da lista',
    '-': 'Navega para a tarefa anterior da lista',

    # Comandos relacionados com um item

    # Comandos exibição

    # Comandos para diagnóstico de problemas
    '*db': 'Ligar/desligar modo debug. No modo debug serão geradas mensagens adicionais no log.',
    '*lg': 'Exibir log geral.',

    # Comandos gerais
    '*gm': 'Geração automática de modelo de laudo SAPI para unidade com quesitos mais comuns',
    '*vm': 'Validar modelo de laudo SAPI da unidade',
    '*aq': 'Adição de novos quesitos (automaticamente)',
    '*qq': 'Finaliza'
}

Gmenu_admin['cmd_exibicao'] = []
Gmenu_admin['cmd_navegacao'] = ["+", "-"]
Gmenu_admin['cmd_item'] = []
Gmenu_admin['cmd_geral'] = ['*gm', '*vm', '*aq']
Gmenu_admin['cmd_diagnostico'] = ['*lg', '*db']


# ------------------------------------------------------------------------------------------------
# Constantes para localização de seções do laudo, que serão substituídos por blocos de parágrafos
# ------------------------------------------------------------------------------------------------
GsapiQuesitos   = 'sapiQuesitos'
GsapiRespostas  = 'sapiRespostas'
GsapiEntrega    = 'sapiEntrega'

#
Gtipos_componentes = dict()

# Debug
Gverbose = False  # Aumenta a exibição de detalhes (para debug)

# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi_xxx.py, para evitar dependência
from sapilib_2_0 import *

# **********************************************************************
# PRODUCAO
# **********************************************************************

# ======================================================================
# Funções Auxiliares específicas deste programa
# ======================================================================


def exibir_dados_laudo(dados_laudo, tarefa):
    print_centralizado(" Dados para da tarefa laudo ")

    console_dump_formatado(dados_laudo)

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
    dados_item = Gitens[obter_item_corrente()]
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
            console_dump_formatado(dados_relevantes_json["laudo"])
            print()

    return


# Exibe dados de laudo para o item corrente
def exibir_situacao_item_corrente():
    item = Gitens[obter_item_corrente()]["item"]
    exibir_situacao_item(item)


def indent(elem, level=0):
    i = "\n" + level * "  "
    j = "\n" + (level - 1) * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = j
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = j
    return elem



'''
========================================================================
========================================================================
BIBLIOTECA ZIP
========================================================================
========================================================================
'''


# Função auxiliar para remover um ou mais arquivos de um zip
#
# Parâmetros:
# - zipfname: Caminho para o arquivo
# - filenames: Lista de arquivos que devem ser removidos
def remove_from_zip(zipfname, filenames):
    tempdir = tempfile.mkdtemp()
    try:
        tempname = os.path.join(tempdir, 'new.zip')
        with zipfile.ZipFile(zipfname, 'r') as zipread:
            with zipfile.ZipFile(tempname, 'w') as zipwrite:
                for item in zipread.infolist():
                    if item.filename not in filenames:
                        data = zipread.read(item.filename)
                        zipwrite.writestr(item, data)
        shutil.move(tempname, zipfname)
    finally:
        shutil.rmtree(tempdir)


'''
========================================================================
========================================================================
BIBLIOTECA XML : Complementa ElementTree
========================================================================
========================================================================
'''

# Separa o namespace de um tag xml
def xml_decompoe_ns_tag(ns_tag):
    partes = ns_tag.split('}')
    ns = partes[0] + '}'
    tag = partes[1]

    return (ns, tag)

# Recupera todos os name spaces de um xml
def xml_parse_and_get_ns(caminho_arq):
    events = "start", "start-ns"
    root = None
    ns = {}
    for event, elem in xml.etree.ElementTree.iterparse(caminho_arq, events):
        if event == "start-ns":
            if elem[0] in ns and ns[elem[0]] != elem[1]:
                # NOTE: It is perfectly valid to have the same prefix refer
                #     to different URI namespaces in different parts of the
                #     document. This exception serves as a reminder that this
                #     solution is not robust.    Use at your own peril.
                raise KeyError("Duplicate prefix with different URI found.")
            ns[elem[0]] = "%s" % elem[1]
        elif event == "start":
            if root is None:
                root = elem

    return ns


'''
========================================================================
========================================================================
===================== BIBLIOTECA ODT ===================================
========================================================================
========================================================================
'''

# Variáveis relacionadas com a carga de um documento ODT
Gxml_ns                 = None
Gxml_ns_inv             = None
Godt_raiz               = None
Godt_office_text            = None
Godt_filho_para_pai_map = None

# Carrega um arquivo ODT em memória
def odt_carrega_arquivo(caminho_arquivo_odt):

    global Godt_raiz
    global Godt_office_text
    global Godt_filho_para_pai_map

    debug("Carregando arquivo:", caminho_arquivo_odt)

    caminho_arq_content_xml = odt_extrai_content_xml(caminho_arquivo_odt)
    if not caminho_arq_content_xml:
        return False

    debug("Arquivo de content.xml:", caminho_arq_content_xml)

    # Primeiramente é necessário carregar os name spaces
    # Isto permite acesso pelo namespace
    # E com o registro que é feito também faz
    # com que durante a gravação o namespace seja registrado
    if not odt_armazena_e_registra_ns(xml_parse_and_get_ns(caminho_arq_content_xml)):
        print_tela_log("Carregamento de arquivo falhou durante leitura de name_space")
        return False

    try:
        # Faz parse no arquivo e atualizar Godt_raiz
        xml_tree = xml.etree.ElementTree.parse(caminho_arq_content_xml)
        Godt_raiz = xml_tree.getroot()
        
        # Localiza elemento office:text 
        office_body = Godt_raiz.find('office:body', Gxml_ns)
        Goffice_text = office_body.find('office:text', Gxml_ns)

        # Monta mapeamento para elemento pai de todos os elemento de office:text
        # Isto é necessário, pois no ElementTree não existe mecanismo
        # para navegar para o pai (apenas para os filhos)
        Godt_filho_para_pai_map = {c: p for p in Goffice_text.iter() for c in p}

    except BaseException as e:
        print_tela_log("ERRO: Problema no parse do arquivo:", str(e))
        return False


    # Tudo certo
    return True

# Extrai arquivo de conteúdo (content.xml) do odt
def odt_extrai_content_xml(caminho_arquivo_saida_odt):

    # Um arquivo ODT é um ZIP contendo arquivos XML
    # Logo, primeiramente é necessário abrir o zip
    # e retirar de dentro do zip o arquivo content.xml
    # o qual contém os dados do arquivo texto

    try:
        print_log("- Unzipando arquivo de saída", caminho_arquivo_saida_odt)
        zf = zipfile.ZipFile(caminho_arquivo_saida_odt, 'r')
        # listarArquivos(zf)
        # exibirInfo(zf)

        # Cria pasta temporária para extrair arquivo
        pasta_tmp = tempfile.mkdtemp()

        # O conteúdo propriamente dito do arquivo ODT
        # está armazenado no arquivo content.xml
        arq_content_xml = "content.xml"
        if not arq_content_xml in zf.namelist():
            print_tela_log("- ERRO: Não foi encontrado arquivo:", arq_content_xml)
            return False

        caminho_arq_content_xml = os.path.join(pasta_tmp, arq_content_xml)

    except BaseException as e:
        print_tela_log("ERRO: Ao unzipar", caminho_arquivo_saida_odt, str(e))
        return False

    try:
        # Extração de content.xml para arquivo em pasta temporária
        zf.extract(arq_content_xml, pasta_tmp)
        print_log("- Arquivo content_xml extraído para [", pasta_tmp, "]")

    except BaseException as e:
        print_tela_log("ERRO: Não foi possível ler arquivo ", arq_content_xml)
        print_tela_log("ERRO: ", e)
        return False

    # Tudo certo
    return caminho_arq_content_xml



# Le todos os name spaces de um ODT, armazena para efetuar consultas
# e registra para que durante a gravação os name spaces sejam preservados
def odt_armazena_e_registra_ns(xml_ns):
    # Irá alterar estas duas globais
    global Gxml_ns
    global Gxml_ns_inv

    # Guarda em global
    Gxml_ns = xml_ns

    # Inverte dicionário de namespace e guarda em global
    Gxml_ns_inv = {}
    for k in Gxml_ns:
        Gxml_ns_inv[Gxml_ns[k]] = k


    try:
        # Registra o namespace (desta forma o mesmo será preservado na gravação)
        qtd = 1
        for k in Gxml_ns:
            prefix = k
            uri = Gxml_ns[k]
            debug("Registrando NS", prefix, " para ", uri)
            xml.etree.ElementTree.register_namespace(prefix, uri)
            qtd = qtd+1

        debug(qtd,"namespaces registrados")

    except BaseException as e:
        print_tela_log("ERRO: Não foi possível registrar o namespace =>", str(e))
        print_tela_log("Para gerar detalhamento do erro, rode novamente em modo --debug")
        return False

    # Tudo certo
    return True

# Exibe name spaces
def odt_print_ns(xml_ns):
    qtd=0
    for k in xml_ns:
        print(k," => ", xml_ns[k])
        qtd=qtd+1
    print("Identificado",qtd,"namespaces")


# Localiza todos os elmentos com tag abaixo do pai
# Retorna uma lista
def odt_localiza_todos(pai, tag):

    #Goffice_text.findall('table:table', Gxml_ns):
    lista = pai.findall(tag, Gxml_ns)

    return lista


# Recupera o texto do elemento e de todos os seus descendentes
def odt_obtem_texto_recursivo(elem):
    # Texto no próprio elemento
    t = ""

    #var_dump(elem)
    #var_dump(elem.text)
    #var_dump(elem.attrib)
    #var_dump(elem.tail)
    #print('--------------')

    if (elem.text is not None):
        # Texto no próprigo elemento
        t = t + elem.text

    # <p style-name="P373">
    #   <soft-page-break/># Abaixo estão as definições de blocos que substituirão alguns componentes
    #   <span style-name="T350">referenciados </span>
    #   acima.
    # </p>
    # Pega a parte que vem depois dos tags, como por exemplo o <soft-page-break/>
    if (elem.tail is not None):
        t = t + elem.tail

    # Concatena com texto nos elementos filhos
    for filho in elem:
        t += odt_obtem_texto_recursivo(filho)

    return str(t)


# Recupera o texto total de um parágrafo
# Um parágrafo pode ser formando por vários níveis, com elementos
# span aninhados, como ilustrado abaixo:
# <text:p text:style-name="P107">
#   <text:span text:style-name="sapiBloco">sapiBlocoInicio:sapi</text:span>
#     <text:span text:style-name="sapiBloco">
#       <text:span text:style-name="T134">QuesitosNoveQuesitos</text:span>
#   </text:span>
# </text:p>
def odt_obtem_texto_total_paragrafo(p):
    t = odt_obtem_texto_recursivo(p)

    return str(t)


# Faz dump do texto contido em um parágrafo,
# inclusive em subelementos (span)
def odt_dump_paragrafo(p):
    print(p)
    print(p.attrib)
    texto = odt_obtem_texto_total_paragrafo(p)

    print(texto.encode("utf-8"))  # Gambiarra para conseguir exibir na console windows

    return texto


# Faz dump de todos os parágrafos contidos em um elemento
# Gxml_ns: deve conter o name space que define 'text'
def odt_dump_todos_paragrafos(elemento):
    print("======= DUMP DE PARÁGRAFOS ==================================")

    # Parágrafos do texto
    # for p in elemento.findall('text:p', Gxml_ns):
    for p in odt_localiza_todos(pai=elemento, tag='text:p'):
        odt_dump_paragrafo(p)
        print("========================================================")


# Procurar um ancestral de um elemento que possua o tipo passado como parâmetro
def odt_busca_ancestral_com_tipo(elemento, raiz, tipo, debug=False):
    # mapeamento de pai filho, para poder subir para o ancestral
    filho_para_pai = {
        c: p for p in raiz.iter() for c in p
        }

    ancestral = elemento
    while (True):
        tipo_ancestral = odt_get_tipo(ancestral)

        if debug:
            print("odt_busca_ancestral_com_tipo => ancestral: ", ancestral, "tipo: ", tipo_ancestral)

        if (tipo_ancestral == tipo):
            if debug: print("odt_busca_ancestral_com_tipo =>: Achou : ", ancestral)
            return ancestral

        # Sobe para pai
        ancestral = filho_para_pai.get(ancestral, None)
        if (ancestral is None):
            # Chegou no topo, e não encontrou sapiCampoVar
            if debug: print("odt_busca_ancestral_com_tipo =>: Não tem pai")
            return None


# Procura elemento textual que contém texto indicado
# Faz busca em parágrafo e seus componentes (span)
# Se localizar em um span, retorna span (e não o parágrafo pai)
def odt_procura_paragrafo_contendo_texto(elemento, texto):
    print("Texto=", texto)

    # Procura nos parágrafos e em seus componentes
    for p in elemento.findall('text:p', Gxml_ns):
        print(p, p.text.encode("utf-8"))
        if (p.text is not None) and (texto.lower() in p.text.lower()):
            return p
        for span in p.findall("text:span", Gxml_ns):
            if (texto.lower() in span.text.lower()):
                return span

    return None


# Recupera todos os elementos de um certo tipo_procurado
# retornando uma lista, sendo cada elemento da lista um dicionário contendo:
#  - elemento: Elemento localizado
#  - pai: Elemento pai
#  - pos: Posição do filho no pai
def odt_recupera_recursivamente(pai, tipo_procurado):
    lista = []
    pos = 0  # Posição relativa do filho no pai
    for filho in pai:
        # Recupera tipo
        p = filho.tag.split('}')
        tipo = p[1]

        if (tipo == tipo_procurado):
            dados = dict()
            dados["elemento"] = filho
            dados["pai"] = pai
            dados["pos"] = pos
            lista.append(dados)
        else:
            # Se não for do tipo procurado,
            # chama recursivamente, pois estamos
            # interessando em elementos em qualquer nível
            lista_filho = odt_recupera_recursivamente(filho, tipo_procurado)
            lista = lista + lista_filho

        # Ajusta posição relativa
        pos += 1

    return lista


# Recupera todos os parágrafos subordinados ao elemento
# Retorna um dicionário contendo:
#  - Campos de odt_recupera_recursivamente(elemento, elemento_pai, pos)
#  - texto: Agrupa todos os textos, inclusive dos spans filhos
def odt_recupera_lista_paragrafos(pai):
    lista = odt_recupera_recursivamente(pai, 'p')
    # var_dump(lista)

    for p in lista:
        # Adiciona dados
        p["texto"] = odt_obtem_texto_total_paragrafo(p["elemento"])

    return lista


# Recebe um nome qualificado, e retorna apenas a parte depois do namespace
# Por exemplo:
# Recebe : {urn:oasis:names:tc:opendocument:xmlns:text:1.0}p
# Retorna: p
def odt_remove_qualificacao(nome_qualificado):
    p = nome_qualificado.split('}')
    nome = p[1]
    return nome


# Recupera um nome de atributo
# A qualificação é desprezada
# Logo, o chamada deve ser feita sem qualificação
# Errado: odt_get_atributo(elemento, "text:style-name")
# Certo: odt_get_atributo(elemento, "style-name")
def odt_get_atributo(elemento, nome_atributo_sem_qualificacao):
    da = elemento.attrib

    for nome_qualificado in da:
        # O label do atributo vem qualificado no formato estendido
        # Remove namespace
        # {urn:oasis:names:tc:opendocument:xmlns:text:1.0}name
        if (nome_atributo_sem_qualificacao in nome_qualificado):
            return da[nome_qualificado]

    # Não encontrou
    return None


# Recupera o nome qualificado de um atributo
def odt_get_nome_qualificado_atributo(elemento, nome_atributo_sem_qualificacao):
    da = elemento.attrib

    for nome_qualificado in da:
        # O label do atributo vem qualificado no formato estendido
        # Remove namespace
        # {urn:oasis:names:tc:opendocument:xmlns:text:1.0}name
        if (nome_atributo_sem_qualificacao in nome_qualificado):
            return nome_qualificado

    # Não encontrou
    return None


def odt_get_tipo(elemento):
    t = elemento.tag
    return odt_remove_qualificacao(t)


# Recupera todos os campos variáveis subordinados ao elemento
# Exemplo: <text:user-field-get text:name="sapiTabelaMaterialExaminado">{sapiTabelaMaterialExaminado}</text:user-field-get>
# Retorna um dicionário contendo:
#  - Campos de odt_recupera_recursivamente(elemento, elemento_pai, pos)
#  - name: O nome do campo, definido durante a criação
#  - texto: O que aparece para o usuário na visualização do documento odt
def odt_recupera_lista_campos_variaveis(pai):
    lista = odt_recupera_recursivamente(pai, 'user-field-get')
    # var_dump(lista)

    for cv in lista:
        # Adiciona dados
        elemento = cv["elemento"]
        # Texto que aparece na visualização do odt
        cv["texto"] = elemento.text
        # Nome do campo variável
        name = odt_get_atributo(elemento, 'name')
        if (name is None):
            erro_fatal("Falha no parse do campo 'name' de campo_variavel")
        cv["name"] = name
        # Resultado
        # debug("- Encontrado campo de usuário: ", cv["name"])
    # print(elemento.attrib)
    # print(cv["texto"])
    # print(cv["name"])
    # die('ponto539')

    # Procura pelo ancestral que tem tipo

    return lista


# Recupera todos os campos variáveis subordinados ao elemento
# Exemplo: <text:user-field-get text:name="sapiTabelaMaterialExaminado">{sapiTabelaMaterialExaminado}</text:user-field-get>
# Retorna um dicionário contendo:
#  - Campos de odt_recupera_recursivamente(elemento, elemento_pai, pos)
#  - name: O nome do campo, definido durante a criação
#  - texto: O que aparece para o usuário na visualização do documento odt
def odt_recupera_lista_campos_variaveis_sapi(pai):
    lista_resultado = []

    # mapeamento de pai filho, para poder subir para o ancestral
    filho_para_pai = {
        c: p for p in pai.iter() for c in p
        }

    # Recupera todos os campos variáveis
    lista_cv = odt_recupera_lista_campos_variaveis(pai)

    erros = 0
    # Confere campos variáveis
    for cv in lista_cv:

        nome = cv["name"].lower()

        # Se é um campo variável do siscrim, ignorar
        if eh_variavel_siscrim(nome):
            continue

        # Verifica nome do campo
        if (nome[:4] != "sapi"):
            print_tela_log("- ERRO: Campo '"+str(cv["name"])+"' com nome fora do padrão. Todas as variáveis sapi devem ter prefixo sapi (Exemplo: sapiXXXX)")
            erros += 1
            continue



        pai = cv["pai"]

        # Verifica se campo variável está em um span
        # -------------------------------------------------------------
        # O que estamos interessado aqui é em assegurar que o
        # campo esteja dentro de um span, para possibilitar a substituição
        # em parágrafos complexo:
        # Ex: Marca/Modelo: {sapiAparelhoMarca} / {sapiAparelhoModelo}
        # Neste tipo de parágrafo, os campo variáveis tem
        # que ser autônomos (não podem depender do parágrafo)
        tipo_pai = odt_get_tipo(pai)
        if (tipo_pai != 'span'):
            print_tela_log("- ERRO: Campo variável [", cv["name"],
                           "] mal formatado. Todo campo variável deve possuir um estilo para diferenciá-lo do restante do parágrafo. Posicione sobre o campo, digite F11 e na aba de estilo de caracter troque para o estilo 'sapiCampoVar'. Se o campo variável ocorrer mais de uma vez no texto, execute o procedimento para cada ocorrência.")
            erros += 1

        # Verifica se o valor do campo é compatível com o nome da variável
        # ---------------------------------------------------------------
        # Exemplo: Nome: sapiXyz => Valor: {sapiXyz}
        texto = cv['texto']
        texto_esperado = '{' + cv['name'] + '}'
        if (texto != texto_esperado):
            print_tela_log("- ERRO: Campo variável '" + cv[
                "name"] + "' com texto incompatível '" + texto + "'. O texto deveria ser '" + texto_esperado + "'")
            erros += 1

        # var_dump(cv)
        # die('ponto659')

        # Procura sapiCampoVar
        # -------------------------------------------------------------
        # Verifica se o estilo do span do parágrafo é 'sapiCampoVar'
        # ou se algum ancestral tem este estilo
        # Pode ser algo como:
        # <text:p text:style-name="P25">
        #     <text:span text:style-name="sapiCampoVar">
        #         <text:span text:style-name="T113">
        #             <text:user-field-get text:name="sapiQuesitos">{sapiQuesitos}</text:user-field-get>
        #         </text:span>
        #     </text:span>
        # </text:p>
        # odt_dump(pai)

        ancestral = pai
        encontrou = False
        while (True):
            estilo_ancestral = odt_get_atributo(ancestral, 'style-name')
            if (estilo_ancestral == 'sapiCampoVar'):
                encontrou = True
                break
            # Sobe para pai
            ancestral = filho_para_pai.get(ancestral, None)
            if (ancestral is None):
                # Chegou no topo, e não encontrou sapiCampoVar
                break

        if (not encontrou):
            print_tela_log("- ERRO: Campo variável '" + cv["name"] + "' não tem estilo sapiCampoVar")
            erros += 1

        cv["ancestral_sapiCampoVar"] = ancestral
        # if (ancestral!=pai):
        #     odt_dump(ancestral)
        #     var_dump(cv)
        #     die('ponto698')

        # Adiciona na lista de resultado
        lista_resultado.append(cv)

    # Retorna resultado
    return ((erros == 0), lista_resultado)


# Faz um busca em todos os parágrafos aninhados (abaixo na árvore)
# Retorna estrutura de dicionário com dados do parágrafo
# Se não achar, retorna none
def odt_busca_texto_paragrafo_aninhado(elemento_pai, texto_busca):
    # Recupera lista de parágrafos aninhados
    lista = odt_recupera_lista_paragrafos(elemento_pai)

    # Localiza um elemento
    for dpar in lista:
        if (texto_busca in dpar["texto"]):
            return dpar

    # Não achou
    return None


# Localiza campo variavel na lista
def odt_localiza_campo_variavel(lista_cv, nome_campo):
    # Procura campo variável na lista de campos váriaveis passada
    for cv in lista_cv:
        if (cv["name"].lower() == nome_campo.lower()):
            return cv

    return None


# Substitui campo variável identificado por 'substituir' em formato texto,
# pelo texto 'valor'
# Neste caso, será feita uma simples atualização do campo texto do elemento pai
# uma vez que o elemento pai de um campo variável é um 'p' ou um 'span'
# Retorna a quantidade de substituições que foram efetuadas
#
# <text:p text:style-name="P72">
#  <text:user-field-get text:name="sapiTabelaMaterialExaminado">{sapiTabelaMaterialExaminado}</text:user-field-get>
# </text:p>
#
# <text:span text:style-name="T129">
#  <text:user-field-get text:name="sapiAlvo">{sapiAlvo}</text:user-field-get>
# </text:span>
#
def odt_substitui_campo_variavel_texto(lista_cv, substituir, valor):
    qtd_substituicoes = 0

    # Procura campo variável na lista de campos váriaveis passada
    for cv in lista_cv:
        if (cv["name"].lower() == substituir.lower()):
            # Achou campo a ser substituido
            elemento = cv["elemento"]
            pai = cv["pai"]

            # Basta colocar no texto do pai o valor a ser substituido
            pai.text = valor

            # Ajusta o estilo do pai, para indica que o campo foi substituído
            # Troca sapiCampoVar => sapiCampoSubstituido
            # var_dump(cv)

            ancestral = cv["ancestral_sapiCampoVar"]
            nome_qualificado_atributo = (odt_get_nome_qualificado_atributo(ancestral, 'style-name'))
            ancestral.attrib[nome_qualificado_atributo] = 'sapiCampoSubstituido'

            # var_dump(ancestral)
            # odt_dump(ancestral)

            # var_dump(ancestral.attrib)
            # die('ponto807')

            # var_dump(ancestral)
            # odt_dump(ancestral)

            # Remove elemento de campo variável
            pai.remove(elemento)

            # Substuido com sucesso
            qtd_substituicoes += 1

    return qtd_substituicoes




# Substitui um parágrafo por uma lista de parágrafos
def odt_determinar_elemento_pai(paragrafo, raiz):
    # mapeamento de pai filho, para poder subir para o ancestral
    filho_para_pai = {
        c: p for p in raiz.iter() for c in p
        }

    # Determina o pai
    pai = filho_para_pai[paragrafo]

    return pai


# Substitui um parágrafo por uma lista de parágrafos
def odt_substituir_paragrafo_por_lista(paragrafo_substituir, raiz, lista_novos_par):
    # mapeamento de pai filho, para poder subir para o ancestral
    filho_para_pai = {
        c: p for p in raiz.iter() for c in p
        }

    # Determina o pai e a posição que o filho ocupa nos elementos do pai
    pai_paragrafo_substituir = filho_para_pai[paragrafo_substituir]
    # odt_dump(paragrafo_substituir)
    # die('ponto912')
    # odt_dump(pai_paragrafo_substituir)
    # odt_dump_ancestral(pai_paragrafo_substituir, raiz)
    # die('ponto914')

    posicao_substituir = odt_determina_posicao_pai_filho(pai_paragrafo_substituir, paragrafo_substituir)
    # var_dump(posicao_substituir)
    # die('ponto919')
    if (posicao_substituir is None):
        erro_fatal("Erro de integridade entre pai e filho para substiuição")

    # Insere parágrafos da lista na posição ocupada pelo parágrafo atual
    pos = posicao_substituir
    for np in lista_novos_par:
        pai_paragrafo_substituir.insert(pos, np)
        pos += 1

    # Após ter inserido todos os parágrafos do bloco,
    # remove o parágrafo atual
    pai_paragrafo_substituir.remove(paragrafo_substituir)

    # Retorna o parágrafo pai, caso seja necessário debugar (dump)
    return pai_paragrafo_substituir


# Substitui um componente de texto, procurando em parágrafos e
# seus componentes, armazenados abaixo de base
# Retorna;
#  - sucesso:  Verdadeiro se conseguiu substituir. Caso contrário, Falsto
#  - componente: Componente em que foi efetuada a substituição
def odt_substitui_label(base, label_substituir, substituto):
    # Localiza label para substiuição em algum dos componentes sob base
    componente = odt_procura_paragrafo_contendo_texto(base, label_substituir)

    if (componente is None):
        # Não localizou texto indicado, retorna falso
        return (False, None)

    # Efetua substituição de texto no elemento
    componente.text = componente.text.replace(label_substituir, substituto)

    # Tudo certo: Retorna true e o componente
    return (True, componente)



# Recupera um atributo, ajustando o name space para o formato completo
# - ns_nome: Exemplo table:nome
# Retorna o valor do atributo, se existir
def obtem_atributo_xml(elem, ns_nome):
    # Separa table:name
    (ns, nome) = ns_nome.split(":")

    # Procura o alias do namespace
    ns_extenso = Gxml_ns.get(ns, None)
    if ns_extenso is None:
        print("Erro obtem_atributo_xml: ", ns, " nao existe em Gxml_ns")
        exit(1)

    # Monta nome com alias estendido
    # {urn:oasis:names:tc:opendocument:xmlns:table:1.0}name
    k = "{" + ns_extenso + "}" + nome

    # Retorna, se existir
    return elem.get(k, None)


def odt_dump_print(x, nivel):
    # Formata tag
    p = x.tag.split('}')
    ns = p[0].replace('{', '')
    alias = Gxml_ns_inv.get(ns, "indefinido")
    tag = x.tag.replace(ns, alias)
    tag = tag.replace('{', '')
    tag = tag.replace('}', ':')

    # Recupera texto
    texto = ''
    if (x.text is not None):
        texto = x.text

    # Recupera atributo style-name
    style = odt_get_atributo(x, 'style-name')
    atributo = ""
    if (style is not None):
        atributo = "[" + style + "]"

    # Exibe tag
    print(' ' * nivel, nivel, ':', tag, atributo, "=> ", texto.encode("utf-8"))


def odt_dump(elem, nivel=0, nivel_max=None):
    # Exibe pai
    odt_dump_print(elem, nivel)

    # Exibe filhos
    nivel += 1
    if nivel_max is not None and nivel > nivel_max:
        return
    for filho in elem:
        # Recursivo
        odt_dump(filho, nivel=nivel, nivel_max=nivel_max)


def odt_dump_ancestral(elemento, raiz):
    # mapeamento de pai filho, para poder subir para o ancestral
    filho_para_pai = {
        c: p for p in raiz.iter() for c in p
        }

    nivel = 1
    odt_dump_print(elemento, nivel)
    ancestral = elemento
    while (True):
        # Sobe para pai
        ancestral = filho_para_pai.get(ancestral, None)
        # Se não tem ancestral, acabou
        if (ancestral is None):
            return
        # Exibe ancestral
        nivel += 1
        odt_dump_print(ancestral, nivel)


def odt_determina_posicao_pai_filho(pai, filho):
    pos = 0
    for f in pai:
        if (f == filho):
            return pos
        pos += 1

    return None



# Determina coordenadas para substituição de um campo variável
def odt_determinar_coordenadas_substituicao_campo_var(lista_cv, filho_para_pai_linha_map, campo_var):
    posicao_substituir = None
    paragrafo_substituir = None
    pai_paragrafo_substituir = None
    for cv in lista_cv:
        if (cv["name"] == campo_var):
            # Sobe na estrutura, até chegar no parágrafo
            pai = cv["pai"]
            while True:
                if (odt_get_tipo(pai) == 'p'):
                    paragrafo_substituir = pai
                    break
                pai = filho_para_pai_linha_map[pai]

            # Localiza o pai do parágrafo alvo
            pai_paragrafo_substituir = filho_para_pai_linha_map[paragrafo_substituir]
            posicao_substituir = odt_determina_posicao_pai_filho(pai_paragrafo_substituir, paragrafo_substituir)
            if (posicao_substituir is None):
                erro_fatal("Erro de integridade entre pai e filho para substiuição de ", campo_var)

    if (paragrafo_substituir is None):
        erro_fatal("Campo de substituição", campo_var,"não localizado")

    # Ok, tudo certo
    return (posicao_substituir, paragrafo_substituir, pai_paragrafo_substituir)

# Procura campo variável na lista de campos váriaveis passada
# Retorna True se achar, e False caso contrário
def odt_lista_contem_campo_variavel(lista_cv, campo_var):

    for cv in lista_cv:
        if (cv["name"].lower() == campo_var.lower()):
            # Achou campo a ser substituido
            return True

    return False


# Efetua a substituição de um campo variável em um elemento
# A rotina parte do princípio que o campo existe
# Se não existir, não fará nada (apenas retorna false)
# Se conseguiu substituir, retorna a quantidade de substituições efetuadas
def  odt_localiza_substitui_campo_variavel_ok(elemento, campo_var, valor_var):

    # Monta lista com todos os campos variáveis
    (sucesso, lista_cv) = odt_recupera_lista_campos_variaveis_sapi(elemento)
    if not sucesso:
        # Se não conseguiu montar lista, retorna falso
        return False

    # Efetua a substituição
    qtd = odt_substitui_campo_variavel_texto(lista_cv, campo_var, valor_var)
    if (qtd==0):
        return False

    return qtd



# Substitui o content_xml em um arquivo odt
def odt_substitui_content_xml(odt_raiz, caminho_arquivo_saida_odt):

    try:

        # Gravar arquivo odt com conteúdo modificado
        # ------------------------------------------------------------------
        # Gera string do xml completo
        xml_string_alterado = xml.etree.ElementTree.tostring(odt_raiz, encoding="utf-8")

        # A edição um arquivo .ODT é complicada, pois implica em recriar
        # o arquivo, descartando os arquivos a serem removidos
        #
        # Uma vez que o ODT é um zip, permite remover componentes de um arquivo ODT
        # Neste caso, esta função é utilizada para remover o content.xml
        # para depois colocar um novo arquivo no lugar.
        #
        # Remove content.xml do zip
        componente_trocar = "content.xml"
        remove_from_zip(caminho_arquivo_saida_odt, [componente_trocar])

        # Adiciona novo content.xml (modificado)
        with zipfile.ZipFile(caminho_arquivo_saida_odt, mode='a', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(componente_trocar, xml_string_alterado)
    except BaseException as e:
        print_tela_log("- ERRO na criação do arquivo de saída '" + caminho_arquivo_saida_odt + "'")
        print_tela_log("- ERRO: ", e)
        print_tela_log("- Verifique se arquivo não está aberto, ou se existe alguma outra condição que possa estar impedindo a sua criação")
        return False

    print_log("Arquivo gravado com sucesso", caminho_arquivo_saida_odt)
    return True



# Lista nomes de uma lista de cv
def odt_print_lista_cv(lista_cv):
    for cv in lista_cv:
        print(cv["name"])

# Procura por um CV em uma lista
# Se não achar, retorna None
def odt_procura_cv_lista(lista_cv, nome_campo):
    for cv in lista_cv:
        if (cv["name"] == nome_campo):
            return cv

    return None


'''
========================================================================
================ FIM  BIBLIOTECA ODT ===================================
========================================================================
'''


# ------------------------------------------------------------------
# Reconhece e devolve as definições de blocos
# A variável de retorno será um dicionário, contendo os nomes dos blocos
# Para cada bloco, retorna a lista de parágrafos que compõe o bloco
#
# Retorno:
# - Sucesso/Fracasso: Verdadeiro/Falso
# - Lista de blocos
# ------------------------------------------------------------------
def carrega_blocos(base, excluir_blocos=True):
    # Dicionário de blocos
    dblocos = {}

    # Recupera todos os parágrafos
    lista_p = odt_recupera_recursivamente(base, 'p')

    # Varre Recupera e armazena Parágrafos do texto
    bloco_iniciado = False
    nome_bloco = None
    ultimo_nome_bloco = None
    bloco_inicio = "SapiBlocoInicio"
    bloco_fim = "SapiBlocoFim"
    q = 0
    lista_par = list()
    erros=list()
    for d in lista_p:
        q += 1
        # var_dump(d)
        paragrafo = d['elemento']
        pai = d['pai']
        # var_dump(paragrafo)
        # die('ponto858')
        texto = odt_obtem_texto_total_paragrafo(paragrafo)

        # Despreza comentario
        if len(texto) >= 1 and (texto[0] == "#"):
            continue

        # Trata início de bloco
        # Ex: SapiBlocoInicio:SapiCelularAparelhoIdentificacao
        if (texto.lower()[:len(bloco_inicio)] == bloco_inicio.lower()):

            # var_dump(texto)
            # die('ponto1010')

            # Verifica estado
            if (bloco_iniciado):
                msg_erro = "Bloco ["+nome_bloco+"] foi iniciado mas não foi concluído ("+bloco_fim+")"
                erros.append(msg_erro)
                continue

            bloco_iniciado = True

            # Extrai nome do bloco, e converte para minusculas
            # para não ser case sensitive
            x = texto.split(":")
            nome_bloco = x[1].lower()
            # Não pode ter branco nos nomes
            nome_bloco = nome_bloco.replace(" ", "")
            # print("bloco Inicio:", nome_bloco)
            # Verifica se bloco já existe
            if dblocos.get(nome_bloco, None) is not None:
                msg_erro="Bloco ["+nome_bloco+"] está duplicado"
                erros.append(msg_erro)
                continue

            # Guarda nome de bloco recente
            ultimo_nome_bloco = nome_bloco

            # Inicia bloco
            print_log("Bloco [", nome_bloco, "] iniciado em parágrafo:", q)
            lista_par = []
            # Remove parágrafo
            if excluir_blocos:
                pai.remove(paragrafo)
            # Prossegue para o próximo parágrafo
            continue

        # Trata fim de bloco
        # if (False):
        # if (blocoFim.lower() in texto.lower()):
        if (texto.lower()[:len(bloco_fim)] == bloco_fim.lower()):

            if (not bloco_iniciado):
                msg_erro = "Bloco finalizado sem ser iniciado. Procure no texto por um '" + bloco_fim + \
                           "' sobrando após o bloco '" + ultimo_nome_bloco + "'"
                erros.append(msg_erro)
                continue

            print_log("Finalizando carregamento de bloco [", nome_bloco, "] em parágrafo:", q, ". Bloco contém ",
                      len(lista_par), " parágrafos")
            # Armazena bloco
            dblocos[nome_bloco] = lista_par
            # reinicializa
            bloco_iniciado = False
            lista_par = []
            # Remove parágrafo
            if excluir_blocos:
                pai.remove(paragrafo)
            # Prossegue para o próximo parágrafo
            continue

        # Trata parágrafos do bloco
        if (bloco_iniciado):
            # Adiciona parágrafo na lista de parágrafos do bloco
            lista_par.append(paragrafo)
            # Remove parágrafo
            if excluir_blocos:
                pai.remove(paragrafo)

    #var_dump(erros)
    #die('ponto1063')

    # Verifica se ocorreram erros
    if len(erros)>0:
        for msg_erro in erros:
            msg_erro="ERRO: "+msg_erro
            print_tela_log(msg_erro)
        # Finaliza com Fracasso
        return (False, {})


    # Terminou, tudo certo
    return (True, dblocos)


def recupera_dados_para_laudo_das_tarefas_item(dados_item, fase=None):
    lista_dados_laudo = []

    # Para teste....
    # dadosTarefaSimulados={
    # 					'sapiQuantidadeComponentes': 2,
    # 					'sapiSoftwareVersao': 'UFED/cellebrite 5.2.3',
    # 					'sapiTipoAquisicao': 'extracao',
    # 					'comp1': {
    # 								'sapiNomeComponente': 'Aparelho',
    # 								'sapiAparelhoMarca': 'Samsung',
    # 								'sapiAparelhoModelo': 'GTXXXX',
    # 								'sapiIMEI': '353954070289799',
    # 								'sapiExtracoes': 'Sistema de arquivos',
    # 								'sapiTipoComponente': 'aparelho'
    # 							 },
    # 					'comp2': {   'sapiNomeComponente': 'Cartão SIM',
    # 								 'sapiSimICCID': '89550534000115696190',
    # 								 'sapiSimIMSI': '724054204557115',
    # 								 'sapiSimOperadora': 'Claro BR',
    # 								 'sapiExtracoes': 'Lógica',
    # 								 'sapiTipoComponente': 'sim'
    # 							 }
    # 					}
    #
    # print_tela_log("- *** Não foi recuperado tarefas do servidor...simulando apenas ***")
    #
    # listaDadosLaudo.append(dadosTarefaSimulados)
    #
    # return 	listaDadosLaudo=[]

    # Recupera as tarefas finalizadas de um item
    # --------------------------------------------------------------
    item = dados_item['item']
    #var_dump(dados_item)
    #die('ponto1099')

    print_log("- Recuperando dados para laudo das tarefas do item ", item)
    param = {'codigo_solicitacao_exame_siscrim': GdadosGerais["codigo_solicitacao_exame_siscrim"],
             'item': item,
             'tipo': 'todos',
             'situacao': 'finalizada'}
    if fase is not None:
        param['fase'] = fase

    tarefas = sapisrv_chamar_programa_sucesso_ok(
        programa="sapisrv_obter_tarefas.php",
        parametros=param
    )

    # Monta resposta
    for t in tarefas:
        # var_dump(t["tarefa"]["dados_relevantes_json"])
        # var_dump(t["tarefa"]["dados_relevantes_json"])
        if t["tarefa"]["dados_relevantes_json"] is not None:
            dados_relevantes_json = json.loads(t["tarefa"]["dados_relevantes_json"])
            dados_laudo = dados_relevantes_json["laudo"]
            lista_dados_laudo.append(dados_laudo)
        # TODO: Inexequibilidade
        # O if acima é para tratar inexiquilibadade...tarefa sem dados json
        # Contudo, o certo seria o sistema gravar o motivo da inexiquilibilidade no JSON
        # para depois aproveitar no laudo....ou talvez dar um outro tratamento diferenciado.
        #dados_relevantes_json = json.loads(t["tarefa"]["dados_relevantes_json"])
        #dados_laudo = dados_relevantes_json["laudo"]
        #lista_dados_laudo.append(dados_laudo)

    return lista_dados_laudo



# Recupera todas as tarefas finalizadas de um item
def obter_tarefas_finalizadas_item(item):
    print_tela_log("- Recuperando tarefas finalizads do item ", item)
    param = {'codigo_solicitacao_exame_siscrim': GdadosGerais["codigo_solicitacao_exame_siscrim"],
             'item': item,
             'tipo': 'todos',
             'situacao': 'finalizada'}

    (sucesso, msg_erro, tarefas) = sapisrv_chamar_programa(
        "sapisrv_obter_tarefas.php", param)
    if (not sucesso):
        print_tela_log("ERRO: Falha na busca de tarefas no servidor: ", msg_erro)
        return

    return tarefas

# Cria uma linha para tabela de materiais para o item
# Recebe a linha de modelo e os dados do item
def criar_linha_para_item(tr_modelo, dados_item, dblocos):

    global Gtipos_componentes

    # Duplica modelo para criar nova linha
    tr_nova_linha_item = copy.deepcopy(tr_modelo)

    # Mapeamento filho para pai na nova linha
    filho_para_pai_tr_nova_linha_item_map = {
        c: p for p in tr_nova_linha_item.iter() for c in p
        }

    # Procura por campos de substiuição na nova linha
    (sucesso, lista_cv_tr_nova_linha_item) = odt_recupera_lista_campos_variaveis_sapi(tr_nova_linha_item)
    # die('ponto1349')

    # var_dump(dadosItem)
    # die('ponto1319')

    # Prepara lista de substituição de campos gerais do item
    # --------------------------------------------------------------
    dcs = dict()
    dcs['sapiItem'] = dados_item['item']
    dcs['sapiDescricaoSiscrim'] = dados_item['descricao']
    dcs['sapiMaterialSiscrim'] = dados_item['material']

    # Pode não existir lacre de entrada
    if (dados_item['lacre_anterior'] is not None):
        dcs['sapiLacre'] = dados_item['lacre_anterior']

    # Recupera dados para laudo tarefas do item da fase de aquisição
    lista_dados_laudo = recupera_dados_para_laudo_das_tarefas_item(dados_item, fase='10-aquisicao')

    # Geração de parágrafos
    lista_novos_par = []  # Lista de parágrafos que será gerada
    for dados_tarefa in lista_dados_laudo:

        quantidade_componentes = dados_tarefa['sapiQuantidadeComponentes']
        print_log("Item possui", quantidade_componentes, " componentes")


        # Dados gerais para substituição
        # ------------------------------
        if (dados_tarefa.get('sapiSaidasFormatos', None) is not None):
            # Ajusta os formatos de saída, para ficar mais compreensível para o leitor
            sapiSaidasFormatos = dados_tarefa.get('sapiSaidasFormatos', None)
            sapiSaidasFormatos = sapiSaidasFormatos.replace('ufdr', 'ufdr (UFD Reader)')
            sapiSaidasFormatos = sapiSaidasFormatos.replace('xlsx,', 'xlsx (Excel),')
            sapiSaidasFormatos = sapiSaidasFormatos.replace('xls,', 'xls (Excel),')
            sapiSaidasFormatos = sapiSaidasFormatos.replace('xml', 'IPED')
            dcs['sapiSaidasFormatos'] = sapiSaidasFormatos
        if (dados_tarefa.get('sapiSaidasPastaDestino', None) is not None):
            dcs['sapiSaidasPastaDestino'] = dados_tarefa['sapiSaidasPastaDestino']
        if (dados_tarefa.get('sapiSaidasNomeBase', None) is not None):
            dcs['sapiSaidasNomeBase'] = dados_tarefa['sapiSaidasNomeBase']

        # --------------------------------------------------------------
        # Processa todos os componetes de um item e monta lista
        # de parágrafos para substuição
        # --------------------------------------------------------------
        q_comp = 1
        while (q_comp <= quantidade_componentes):

            # Recupera dados do componente
            ix_comp = "comp" + str(q_comp)
            dados_componente = dados_tarefa[ix_comp]


            # Tipo de componente
            tipo = dados_componente['sapiTipoComponente']

            # Armazena o tipo de componente detectado
            Gtipos_componentes[tipo]=1
            print_log("Adicionado tipo de componente: ", tipo)

            # Recupera bloco de identificação específico
            # para o tipo de componente
            # (ex: sapiIdentificacaoAparelho, sapiIdentificacaoSim)
            nome_bloco_componente = "sapiIdentificacao" + tipo
            bloco = dblocos.get(nome_bloco_componente.lower(), None)
            if bloco is None:
                print_tela_log(
                    texto("ERRO: Não foi localizado bloco com nome[",
                          nome_bloco_componente,
                          "] no seu documento.",
                          " Confira/corrija o seu modelo.",
                          "(Esclarecimento: Nome do bloco NÃO é case sensitive)"
                          )
                )
                return None

            # Monta lista de parágrafos para substituir
            # ----------------------------------------------------------
            for par in bloco:
                # Duplica parágrafo
                novo_paragrafo = copy.deepcopy(par)

                # Adiciona novo parágrafo em lista
                lista_novos_par.append(novo_paragrafo)

                # Verifica se tem campos variáveis no novo parágrafo
                (sucesso, lista_cv) = odt_recupera_lista_campos_variaveis_sapi(novo_paragrafo)
                if (len(lista_cv) == 0):
                    # Se não tem nenhum campo variável, não tem mais o que fazer
                    continue

                # Substitui campos variáveis no parágrafo
                for substituir in dados_componente:
                    valor = dados_componente[substituir]
                    odt_substitui_campo_variavel_texto(lista_cv, substituir, valor)

            # E os dados relativos aos exames....
            # tem que processar também...

            # yyyyy

            # Próximo componente
            q_comp += 1

            # -- Fim do processamento do componente

    # Efetua a substituição dos dados gerais do item
    #var_dump(dcs)
    #die('ponto1203')
    for cs in dcs:
        odt_substitui_campo_variavel_texto(lista_cv_tr_nova_linha_item, cs, dcs[cs])

    # -- Fim do processamento da lista de dados para laudo

    # Terminou o processamento de todos os componentes do item
    # Logo, já tem a lista de parágrafos que serão utilizados
    # Agora tem que efetuar a substituição na linha de modelo da tabela
    # de materiais
    #
    # Localiza o campo variável de sapiItemIdentificacao
    # --------------------------------------------------------------
    campo_var = "sapiItemIdentificacao"
    (posicao_substituir,
     paragrafo_substituir,
     pai_paragrafo_substituir) = odt_determinar_coordenadas_substituicao_campo_var(
        lista_cv_tr_nova_linha_item,
        filho_para_pai_tr_nova_linha_item_map,
        campo_var)

    # Codigo deprecated...substituido por chamada acima
    # posicao_substituir = None
    # paragrafo_substituir = None
    # pai_paragrafo_substituir = None
    # for cv in lista_cv_tr_nova_linha_item:
    #     if (cv["name"] == 'sapiItemIdentificacao'):
    #         # O avô do span de texto variável é o que será substituído
    #         # <text:p text:style-name="P70">
    #         # 	<text:span text:style-name="sapiCampoVar">
    #         # 		<text:user-field-get text:name="sapiItemIdentificacao">{sapiItemIdentificacao}</text:user-field-get>
    #         # 	</text:span>
    #         # </text:p>
    #
    #
    #         # Este código foi substituído pela chamada abaixo
    #         #pai = cv["pai"]
    #         #avo = filho_para_pai_tr_nova_linha_item_map[pai]
    #
    #         #if (odt_get_tipo(avo) != 'p'):
    #         #    erro_fatal("Tipo de ancestral do campo 'sapiItemIdentificacao' não é parágrafo")
    #         #paragrafo_substituir = avo
    #
    #
    #         # Localiza o campo variável sapiTextoQuesitacao
    #         campo_var = "sapiTextoQuesitacao"
    #         (posicao_substituir,
    #          paragrafo_substituir,
    #          pai_paragrafo_substituir) = odt_determinar_coordenadas_substituicao_campo_var(
    #             lista_cv_linha,
    #             filho_para_pai_linha_map,
    #             campo_var)
    #
    #         paragrafo_substituir = odt_busca_ancestral_com_tipo(cv["pai"], raiz=tr_modelo, tipo='p')
    #         if (paragrafo_substituir is None):
    #             odt_dump(tr_modelo)
    #             erro_fatal("Não encontrou ancestral do cv 'sapiItemIdentificacao' com tipo parágrafo")
    #
    #         # die('ponto1213')
    #
    #         # Localiza o pai do parágrafo alvo
    #         pai_paragrafo_substituir = filho_para_pai_tr_nova_linha_item_map[paragrafo_substituir]
    #         posicao_substituir = odt_determina_posicao_pai_filho(pai_paragrafo_substituir, paragrafo_substituir)
    #         if (posicao_substituir is None):
    #             erro_fatal("Erro de integridade entre pai e filho para substiuição de sapiItemIdentificacao")
    #
    # if (paragrafo_substituir is None):
    #     erro_fatal("Campo de substituição {sapiItemIdentificacao} não localizado na linha de tabela de materiais")

    # Substitui parágrafo por bloco de parágrafos
    # ----------------------------------------------------------
    # var_dump(posicao_substituir)
    # var_dump(pai_paragrafo_substituir)
    # die('ponto1338')
    pos = posicao_substituir
    for np in lista_novos_par:
        pai_paragrafo_substituir.insert(pos, np)
        pos += 1

    # odt_dump(tr_nova_linha_item)
    # odt_dump(pai_paragrafo_substituir)
    # die('ponto1427')

    # Após ter inserido todos os parágrafos do bloco,
    # remove o parágrafo que contém o campo variável de substituição
    # (ex: sapiItemIdentificacao)
    pai_paragrafo_substituir.remove(paragrafo_substituir)

    #
    return tr_nova_linha_item


# Cria zero, uma ou mais linhas de hash para um item,
# baseado em dados armazenados nas tarefas
def criar_linhas_hash_para_item(tr_modelo, dados_item):
    # Retorno
    linhas = []

    # Recupera dados de laudo das tarefas do item
    lista_dados_laudo = recupera_dados_para_laudo_das_tarefas_item(dados_item)

    for dados_tarefa in lista_dados_laudo:

        sapi_hashes = dados_tarefa.get('sapiHashes', None)
        if (sapi_hashes is None):
            # Tarefa não possui dados de hash
            continue

        # Processa a lista de hashes, gerando uma linha para cada hash
        for h in sapi_hashes:

            # Duplica modelo para criar nova linha
            tr_nova_linha_item = copy.deepcopy(tr_modelo)

            # Procura por campos de substiuição na nova linha
            (sucesso, lista_cv_tr_nova_linha_item) = odt_recupera_lista_campos_variaveis_sapi(tr_nova_linha_item)

            # Adiciona item na descrição do hash
            descricao = "Item " + str(dados_item['item']) + " - " + h["sapiHashDescricao"]

            # substituição de campos na nova linha de hashes
            dcs = dict()
            dcs['sapiHashDescricao'] = descricao
            dcs['sapiHashValor'] = h["sapiHashValor"]
            dcs['sapiHashAlgoritmo'] = h["sapiHashAlgoritmo"]

            for cs in dcs:
                odt_substitui_campo_variavel_texto(lista_cv_tr_nova_linha_item, cs, dcs[cs])

            # Adciona nova linha na lista de linhas
            linhas.append(tr_nova_linha_item)

            # -- Fim do processamento de hashes

    return linhas



# Cria uma linha para material devolvido
def criar_linha_matdevol(tr_modelo_linha_matdevol, mat):

    # Duplica modelo para criar nova linha
    nova_linha = copy.deepcopy(tr_modelo_linha_matdevol)

    # Procura por campos de substiuição na nova linha
    (sucesso, lista_campos) = odt_recupera_lista_campos_variaveis_sapi(nova_linha)

    # Adiciona item na descrição do hash
    material    = mat['material']
    descricao   = mat['descricao']
    lacre       = mat['lacre']

    # Campo composto (descricao_eou_lacre)
    if mat['destino'] == False:
        # === Material examinado ===
        # Monta lista de itens
        texto_itens = ", ".join(mat['itens'])
        # Exibe apenas o número do lacre
        descricao_ou_lacre = lacre
    else:
        # === Material de DESTINO ===
        # Lista de itens é nula para material de destino
        texto_itens="n/a (destino)"
        # Exibe descrição e se existir o lacre
        descricao_ou_lacre = descricao
        if lacre is not None:
            descricao_ou_lacre += ' Lacre: ' + lacre

    # substituição de campos na nova linha
    dcs = dict()
    dcs['sapiMaterialSiscrim']          = material
    dcs['sapiItensDoMaterial']          = texto_itens
    if descricao_ou_lacre is not None:
        dcs['sapiDescricaoEOULacreAtual']   = descricao_ou_lacre

    for cs in dcs:
        odt_substitui_campo_variavel_texto(lista_campos, cs, dcs[cs])

    return nova_linha


# Recupera dados gerais (que não ficaram em tabelas) das tarefas
# Exemplo: Software utilizado por cada tarefa
def recupera_dados_gerais_tarefas(dados_item, dict_software):

    # Recupera dados de laudo das tarefas do item
    lista_dados_laudo = recupera_dados_para_laudo_das_tarefas_item(dados_item)

    for dados_tarefa in lista_dados_laudo:

        # Armazena software utilizado na tarefa
        software = dados_tarefa.get('sapiSoftwareVersao', None)
        if software is not None:
            dict_software[software] = 1

    return


def odt_clonar_bloco(nome_bloco, dblocos):
    lista_par = []

    bloco = dblocos.get(nome_bloco.lower(), None)
    if (bloco is None):
        erro_fatal("Erro: Não foi localizado bloco com nome[", nome_bloco, "] odt_clonar_bloco (case insensitive)")

    # Monta lista de parágrafos para substituir
    # ----------------------------------------------------------
    for par in bloco:
        # Duplica parágrafo
        novo_paragrafo = copy.deepcopy(par)

        lista_par.append(novo_paragrafo)

    return lista_par


# Parse de blocos de quesito e respostas
# Retorna
#  - sucesso:
#  - Dicionário de quesitos_respostas
def parse_quesitos_respostas(dblocos):
    sucesso = True

    quesitos = []
    respostas = []

    for b in dblocos:
        b = b.lower()

        # Despreza os blocos de modelo de quesitos
        # Estes blocos seguem o padrão
        # sapiBlocoInicio:sapiQuesitos-{SapiQuesitacaoHash}
        if ("SapiQuesitacaoHash".lower() in b):
            continue

        if (GsapiQuesitos.lower() in b):
            # Separa apenas o nome (remove a constante)
            nome = str(b.replace(GsapiQuesitos.lower(), ''))
            quesitos.append(nome)
        if (GsapiRespostas.lower() in b):
            # Separa apenas o nome
            nome = str(b.replace(GsapiRespostas.lower(), ''))
            respostas.append(nome)

    # var_dump(dblocos)
    if (len(quesitos) == 0):
        print_tela_log(
            "- Não foi encontrada nenhuma definição de quesitos. Assegure-se de ter utilizado um modelo de laudo padrão SAPI")
        sucesso = False

    # Verifica se o conjunto de quesitos e respostas está coerente
    # Cada quesito tem que ter um bloco de respostas
    for q in quesitos:
        # var_dump(q)
        # var_dump(respostas)
        # die('ponto1548')
        if (q not in respostas):
            print_tela_log(
                "- ERRO: Quesitação '" + q + "' não possui seção de respostas. Defina bloco '" + GsapiRespostas + q + "'")
            sucesso = False
        else:
            print_log("Encontrada quesitação e resposta com label '" + q + "'")
    # Alguma resposta sem quesito?
    for r in respostas:
        if (r not in quesitos):
            print_tela_log(
                "- ERRO: Respostas '" + r + "' não possui seção de quesitos. Defina bloco '" + GsapiQuesitos + r + "'")
            sucesso = False

    # Se ocorreu algum erro básico, encerra
    if (not sucesso):
        return (sucesso, None)

    # Monta descrição dos quesitos
    # -----------------------------
    quesitos_respostas = {}
    for q in quesitos:
        # Nome do bloco
        nome_bloco_quesitos = (GsapiQuesitos + q).lower()
        nome_bloco_respostas = (GsapiRespostas + q).lower()
        resumo_quesitos = ""
        # Sumariza o texto dos quesitos, pegando um parte do texto de cada parágrafo
        qtd_quesitos = 0
        for p in dblocos[nome_bloco_quesitos]:

            debug_on=False
            #if 'cac_10' in nome_bloco_quesitos:
            #    debug_on=True

            texto = odt_obtem_texto_total_paragrafo(p)
            if debug_on:
                odt_dump(p)
            # Ajusta e sintetiza
            # texto = filtra_apenas_ascii(texto)
            (texto, qtd_alteracoes) = console_sanitiza_utf8(texto)
            if texto.strip()=='':
                # Despreza linha em branco
                continue

            #print(texto)
            #parte_inicial = texto[0:100].strip(' .')
            parte_inicial = texto[0:125]
            #parte_inicial = parte_inicial + '.' * (102 - len(parte_inicial)) + " "
            #print(len(parte_inicial))
            if len(texto)>100:
                parte_inicial=parte_inicial + "..."

            # Adiciona ao texto resumo
            resumo_quesitos = resumo_quesitos + parte_inicial + "\n"

            qtd_quesitos += 1


        # Remove ? do início e do final
        resumo_quesitos = resumo_quesitos.strip('\n')
        resumo_quesitos = resumo_quesitos.strip('?')

        if debug_on:
            debug("Resumo dos quesitos")
            debug(resumo_quesitos)

        dados_quesitacao = dict()
        dados_quesitacao["resumo_quesitos"] = resumo_quesitos
        dados_quesitacao["quantidade_quesitos"] = qtd_quesitos
        dados_quesitacao["nome_bloco_quesitos"] = nome_bloco_quesitos
        dados_quesitacao["nome_bloco_respostas"] = nome_bloco_respostas


        # Dá uma filtrada em caracteres de separação,
        # para o nome da quesitação ficar mais adequados
        nome_quesitacao = q.strip(' -_')
        quesitos_respostas[nome_quesitacao] = dados_quesitacao

    # Resultado
    sucesso = True
    return (sucesso, quesitos_respostas)


def formata_frases(texto, tamanho_max):
    lista_frases = []

    # Remove caracteres de formatação
    texto = texto.replace("\n", " ")

    palavras = texto.split(" ")
    frase = ""
    for ix in range(len(palavras)):
        p = palavras[ix]
        t = len(frase) + len(p)

        if (t > tamanho_max):
            # Adiciona frase na lista e reinicia
            lista_frases.append(frase)
            frase = ""

        # Inclui palavra na frase
        p = p.strip()
        if (p != ""):
            frase = frase + p + " "

    # Última frase
    if (frase != ""):
        lista_frases.append(frase)

    return "\n".join(lista_frases)


# Retorna o nome do bloco de quesitos e de respostas
# -nome_bloco_quesitos
# -nome_bloco_respostas
# ---------------------------------------------------------------------------------------------------------------------
def usuario_escolhe_quesitacao(quesitos_respostas):
    try:
        return _usuario_escolhe_quesitacao(quesitos_respostas)
    except KeyboardInterrupt:
        print()
        print("- Operação interrompida pelo usuário <CTR><C>s")
        return None


def _usuario_escolhe_quesitacao(quesitos_respostas, apenas_listar=False):
    # Isto não deveria acontecer
    if (len(quesitos_respostas) == 0):
        erro_fatal("Inesperado: Não existem quesitos disponíveis")

    # Se existe apenas um quesito, não precisa selecionar
    if (len(quesitos_respostas) == 1):
        for q in quesitos_respostas:
            return quesitos_respostas[q]

    # Lista ordenada de quesitação por quantidade de quesitos
    lista = []
    for nome_quesito in quesitos_respostas:
        quesitacao = quesitos_respostas[nome_quesito]
        # Ordena por quantidade de quesito, concatenado com nome
        # Ex: 011^blackBerry
        qtd = str(quesitacao["quantidade_quesitos"]).zfill(3)
        qtd_nome = qtd + "^" + nome_quesito

        lista.append(qtd_nome)

    # Ordena pelo número dos quesitos, que antecede o nome
    # Ex: 009^Comum, 011^blackBerry
    lista.sort()

    # var_dump(lista)
    # die('ponto1635')

    # Exibe lista de quesitos para seleção
    # ------------------------------------
    # qtd_seq = 0
    # for qtd_nome in lista:
    #
    #     qtd_seq += 1
    #
    #     # Separa o nome da chave de ordenação e recupera quesitação
    #     nome_quesito = qtd_nome.split("^")[1]
    #     quesitacao = quesitos_respostas[nome_quesito]
    #     resumo_quesitos = quesitacao["resumo_quesitos"]
    #     # var_dump(quesitacao)
    #     quantidade_quesitos = quesitacao["quantidade_quesitos"]
    #
    #     print_centralizado("")
    #     print(qtd_seq, "=> ", "Qtd. quesitos:", int(quantidade_quesitos), "  Nome da quesitação:", nome_quesito)
    #     print_centralizado("")
    #     # Imprime o resumo de três quesitos por linha
    #     #tam_linha = 105
    #     #for i in range(0, len(resumo_quesitos), tam_linha):
    #     #    print("  ", resumo_quesitos[i:i + tam_linha])
    #     print(resumo_quesitos)
    #     print()

    # Solicita o número de sequencia da quesitação
    while True:

        # Solicita que usuário informe a quantidade de quesitos da solicitação
        while True:

            # Se for apenas para listar, não faz pergunta
            if apenas_listar:
                qtd_quesitos_solicitacao = '*'
                break

            # Pergunta a quantidade de quesitos
            print("- Para selecionar a quesitação adequada, primeiramente verifique quantos quesitos existem na solicitação de exame.")
            print("- Informe esta quantidade na pergunta abaixo.")
            print("- Se não houver nenhum quesito (por exemplo, solicitação de duplicação), informe zero '0'.")
            print("- Caso deseje listar todas as quesitos, informe '*' na pergunta abaixo")
            pergunta = "< Quantidade de quesitos: "
            # Valida resposta
            qtd_quesitos_solicitacao = input(pergunta)
            qtd_quesitos_solicitacao = qtd_quesitos_solicitacao.strip()
            if qtd_quesitos_solicitacao=='*':
                break
            if not qtd_quesitos_solicitacao.isdigit():
                continue
            # Tudo certo
            if int(qtd_quesitos_solicitacao)==0:
                print("- Mesmo quando não existe quesito explícito, a própria solicitação é considerada um quesito.")
                print("- Logo, no mínimo é 1. Convertido 0 para 1.")
                qtd_quesitos_solicitacao=1
            break

        # Exibe lista de quesitação que atendem requisito de quantidade
        # -------------------------------------------------------------
        print()
        map_ix_para_seq=dict()
        qtd_seq = 0
        for ix in range(0, len(lista)):
            #var_dump(lista)
            #var_dump(ix)

            qtd_nome=lista[ix]

            #var_dump(qtd_nome)
            #die('ponto1612')

            # Separa o nome da chave de ordenação e recupera quesitação
            nome_quesito = qtd_nome.split("^")[1]
            quesitacao = quesitos_respostas[nome_quesito]
            resumo_quesitos = quesitacao["resumo_quesitos"]
            # var_dump(quesitacao)
            quantidade_quesitos = quesitacao["quantidade_quesitos"]

            if (  qtd_quesitos_solicitacao!='*' and
                  int(quantidade_quesitos)!=int(qtd_quesitos_solicitacao)):
                continue

            # Ok, quesitação aceita
            qtd_seq += 1

            # Guarda mapeamento
            map_ix_para_seq[qtd_seq]=ix

            print_centralizado("")
            print(qtd_seq,
                  "=> ",
                  "Qtd. quesitos:", int(quantidade_quesitos),
                  "  Identificador da quesitação:", nome_quesito
                  #, "[",ix,"]"
                  )
            print_centralizado("")
            # Imprime o resumo de três quesitos por linha
            # tam_linha = 105
            # for i in range(0, len(resumo_quesitos), tam_linha):
            #    print("  ", resumo_quesitos[i:i + tam_linha])
            print(resumo_quesitos)
            print()

        # Se não achar nenhuma quesitação
        if qtd_seq==0:
            print("- Não existe nenhuma opção de quesitação com", qtd_quesitos_solicitacao, "quesitos")
            continue

        # Se for apenas para listar, não pergunta qual o quesito selecionado
        if apenas_listar:
            return None

        print()
        print("- Dica: Escolha a quesitação que mais se aproxima da contida na solicitação de exame.")
        print('- Caso a quesitação da solicitação de exame não seja idêntica a nenhuma das quesitações listadas,')
        print('  selecione a que possuir maior semelhança, efetue os ajustes diretamente no seu laudo')
        print('  e posteriormente notique o administrador SAPI da sua unidade, para que este avalie')
        print('  a necessidade de ampliação das quesitações padrões.')
        print('- Em função de limitações da console, é possível que alguns caracteres acentuados tenham ')
        print('  sido substituídos por "?" no resumo. Não se preocupe, no laudo gerado ficará ok.')

        # Solicita que usuário seleciona a quesitação da lista
        # ----------------------------------------------------
        while True:
            print()
            pergunta = "< Selecione a quesitação entrando com o número de sequencia da lista acima (1 a " + str(
                qtd_seq) + "): "

            # Valida resposta
            seq = input(pergunta)
            seq = seq.strip()
            if not seq.isdigit(): continue
            seq = int(seq)
            if (seq < 1): continue
            if (seq > qtd_seq): continue

            #Ok, usuário selecionou uma quesitação da lista
            break

        # Confirma se a quesitação selecionada é realmente a desejada
        # -----------------------------------------------------------
        #var_dump(map_ix_para_seq)
        ix_selecionada = map_ix_para_seq[seq]
        nome_quesitacao = lista[ix_selecionada].split("^")[1]
        quesitacao_selecionada = quesitos_respostas[nome_quesitacao]

        # Separa o nome da chave de ordenação e recupera quesitação
        resumo_quesitos = quesitacao_selecionada["resumo_quesitos"]
        print()
        print("Quesitação selecionada:")
        print("=======================")
        print(resumo_quesitos)
        print()
        if pergunta_sim_nao("< Confirma quesitação selecionada?", default="s"):
            # Tudo certo, usuário selecionou quesitação
            return quesitacao_selecionada




# ----------------------------------------------------------------------------------------------------------------------
# Recebe o arquivo de entrada (modelo), sendo este um arquivo odt gerado a partir de um modelo SAPI no sisCrim.
# Gera um novo arquivo odt, substituindo os elementos sapi por dados coletados durante as tarefas sapi executadas.
# Retorna o caminho para o arquivo de saída
# ----------------------------------------------------------------------------------------------------------------------
def ajustar_laudo_odt(caminho_arquivo_entrada_odt):
    print_log("- ajustar_laudo_odt para arquivo [", caminho_arquivo_entrada_odt, "]")

    # Verifica se arquivo tem extensão odt
    if (".odt" not in caminho_arquivo_entrada_odt.lower()):
        print_tela_log("- Arquivo de entrada [", caminho_arquivo_entrada_odt, "] não possui extensão .odt")
        return

    # ---------------------------------------------------------------------------------------------------
    # Copia arquivo de entrada xxxx.odt para arquivo de saída xxxx_sapi.odt
    # ---------------------------------------------------------------------------------------------------

    # Será feita uma cópia do arquivo para um novo, adicionando um sufixo
    # O arquivo xxxx.odt será copiado para xxxx_sapi.odt
    # Caminho para o novo arquivo gerado
    (pasta_entrada, nome_arquivo_entrada) = decompoe_caminho(caminho_arquivo_entrada_odt)

    # var_dump(caminho_arquivo_entrada_odt)
    # var_dump(pasta_entrada)
    # var_dump(nome_arquivo_entrada)
    # die('ponto460')

    # Copia arquivo de entrada para arquivo de saída
    pasta_saida = pasta_entrada
    nome_arquivo_saida = nome_arquivo_entrada.replace(".odt", "_sapi.odt")
    caminho_arquivo_saida_odt = pasta_saida + nome_arquivo_saida

    # xxx
    print_tela_log("- Copiando para arquivo de saída: " + caminho_arquivo_saida_odt)
    if os.path.isfile(caminho_arquivo_saida_odt):
        if not pergunta_sim_nao("< Arquivo de saída já existe. Será substituido. Prosseguir?", default="n"):
            print("- Operação cancelada pelo usuário.")
            return
    try:
        # Tenta duplicar arquivo, para equivalente com extensão SAPI
        shutil.copyfile(caminho_arquivo_entrada_odt, caminho_arquivo_saida_odt)
    except BaseException as e:
        print_tela_log("- ERRO na criação do arquivo de saída '" + caminho_arquivo_saida_odt + "'")
        print_tela_log("- ERRO: ", e)
        print_tela_log(
            "- Verifique se arquivo não está aberto, ou se existe alguma outra condição que possa estar impedindo a sua criação")
        return None

    shutil.copyfile(caminho_arquivo_entrada_odt, caminho_arquivo_saida_odt)
    print_tela_log("- Todos os ajustes serão feitos no arquivo de saída. O arquivo de entrada não será alterado.")

    # Valida arquivo de modelo
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("Passo 2: Iniciando validação de modelo do laudo")
    print("-------------------------------------")

    if not carrega_valida_modelo(caminho_arquivo_saida_odt, template=False):
        print("- Validação de modelo falhou")
        return False


    # ------------------------------------------------------------------------------------------------------------------
    # Solicita que usuário escolha a quesitação
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("Passo 3: Escolha da quesitação")
    print("------------------------------")

    # Quesitação determinada automaticamente
    #kkk
    #quesitacao_selecionada = sistema_escolhe_quesitacao(Gmod_quesitos_respostas)

    # Usuário escolhe quesitação, em modo interativo
    quesitacao_selecionada = usuario_escolhe_quesitacao(Gmod_quesitos_respostas)

    if quesitacao_selecionada is None:
        return

    nome_bloco_quesitos = quesitacao_selecionada["nome_bloco_quesitos"]
    nome_bloco_respostas = quesitacao_selecionada["nome_bloco_respostas"]

    # Recupera listas de parágrafos das perguntas e respostas
    lista_par_quesitos = odt_clonar_bloco(nome_bloco_quesitos, Gmod_blocos)
    lista_par_respostas = odt_clonar_bloco(nome_bloco_respostas, Gmod_blocos)

    # ------------------------------------------------------------------------------------------------------------------
    # Substitui sapiQuesitos
    # ------------------------------------------------------------------------------------------------------------------
    cv_sapi_quesitos = odt_localiza_campo_variavel(Gmod_lista_cv, 'sapiQuesitos')
    if (cv_sapi_quesitos is None):
        print_tela_log("ERRO: Modelo sapi mal formado. Não foi localizado campo de substituição 'sapiQuesitos'.")
        return

    paragrafo_substituir_sapi_quesitos = odt_busca_ancestral_com_tipo(cv_sapi_quesitos['pai'], raiz=Godt_raiz, tipo='p')
    # var_dump(ancestral)
    # odt_dump(ancestral)
    # die('ponto1836')
    if (paragrafo_substituir_sapi_quesitos is None):
        print_tela_log("ERRO 1938: Não encontrado parágrafo onde se localiza 'sapiQuesitos'")
        return

    odt_substituir_paragrafo_por_lista(paragrafo_substituir_sapi_quesitos, Godt_raiz, lista_par_quesitos)

    # ------------------------------------------------------------------------------------------------------------------
    # Substitui sapiRespostas
    # ------------------------------------------------------------------------------------------------------------------
    cv_sapi_respostas = odt_localiza_campo_variavel(Gmod_lista_cv, GsapiRespostas)
    if (cv_sapi_respostas is None):
        print_tela_log(
            "ERRO: Modelo sapi mal formado. Não foi localizado campo de substituição '" + GsapiRespostas + "'.")
        return

    paragrafo_substituir_sapi_respostas = odt_busca_ancestral_com_tipo(cv_sapi_respostas['pai'], raiz=Godt_raiz,
                                                                       tipo='p')
    if (paragrafo_substituir_sapi_respostas is None):
        print_tela_log("ERRO 1955: Não encontrado parágrafo onde se localiza '" + GsapiRespostas + "'")
        return

    # Por fim, substitui os parágrafos das respostas aos quesitos
    odt_substituir_paragrafo_por_lista(paragrafo_substituir_sapi_respostas, Godt_raiz, lista_par_respostas)

    #for p in lista_par_respostas:
    #    odt_dump_paragrafo(p)
    #die('ponto1960')

    # ------------------------------------------------------------------------------------------------------------------
    # Geração de tabela de materiais examinados
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("Passo 4: Montagem de tabelas de materiais")
    print("-----------------------------------------")

    # Procura tabela de materiais
    # ---------------------------
    tabela_materiais = Gmod_tabelas['tabela_materiais']

    # Isola linha de modelo da tabela de materiais
    # ------------------------------------------------------------------
    # Parte-se do princípio que a tabela de materiais terá um cabeçalho,
    # e a linha de modelo.
    # O cabeçalho pode ser formado por várias linhas,
    # mas entende-se que a situação mais comum será ter um cabeçalho
    # com uma única linha
    # A linha de modelo DEVE SER ÚNICA, e será sempre a última linha
    # da tabela.
    # ------------------------------------------------------------------
    # odt_localiza_todos(pai=xxxxxxxx, tag='zzzzz')
    # tr_linhas = tabela_materiais.findall('table:table-row', Gxml_ns)
    tr_linhas = odt_localiza_todos(pai=tabela_materiais, tag='table:table-row')
    qtd_linhas = len(tr_linhas)
    if (qtd_linhas != 1):
        # Não é comum ter mais de uma linha
        print_tela_log("- Tabela de materiais contém", qtd_linhas, " linhas, o que é incomum.")
        print_tela_log("- Assumindo que a linha de modelo para substituição é a última linha da tabela de materiais")
    tr_modelo = tabela_materiais.findall('table:table-row', Gxml_ns)[qtd_linhas - 1]

    tab_materiais = Godt_filho_para_pai_map[tr_modelo]
    posicao_inserir_tab_materiais = odt_determina_posicao_pai_filho(tab_materiais, tr_modelo)

    # Recupera campos variáveis da linha de modelo da tabela de materiais
    # ------------------------------------------------------------------
    print_log("- Recuperando campos variáveis da tabela de materiais")
    (sucesso, lista_cv_tabela_materiais) = odt_recupera_lista_campos_variaveis_sapi(tr_modelo)
    if (len(lista_cv_tabela_materiais) == 0):
        print_tela_log(
            "ERRO: Não foi detectado nenhum campo variável na tabela de materiais. Assegure-se de utilizar um modelo de ODT sapi para a geração do laudo")
        return


    # ------------------------------------------------------------------
    # Gera linhas na tabela de materiais para cada um dos itens
    # ------------------------------------------------------------------
    q = 0
    for dados_item in Gitens:
        q += 1

        item = dados_item['item']
        # Despreza materiais de destino
        if item=='destino':
            continue

        #var_dump(dadosItem)
        #die('ponto1863')
        print_tela_log("- Tabela de materiais, processando item ", item)

        # Processa item, criando nova linha na tabela de materiais
        tr_nova_linha_item = criar_linha_para_item(tr_modelo, dados_item, Gmod_blocos)
        if tr_nova_linha_item is None:
            return

        # Insere nova linha na tabela de materiais
        tab_materiais.insert(posicao_inserir_tab_materiais, tr_nova_linha_item)
        posicao_inserir_tab_materiais += 1

    # --- Fim do loop de processamento dos itens da tabela de materiais
    # Remove linha de modelo da tabela de materiais
    tab_materiais.remove(tr_modelo)


    # ------------------------------------------------------------------
    # Substitui textos gerais do corpo do laudo
    # Não é texto que está em blocos
    # ------------------------------------------------------------------
    print()
    print("Passo 5: Substituição de textos gerais do laudo")
    print("-----------------------------------------------")

    # Processa auto
    auto_apreensao = Gsolicitacao_exame["auto_apreensao"]
    partes_auto = auto_apreensao.split(' ')
    tipo_auto = partes_auto[0]
    numero_auto = partes_auto[1]
    if partes_auto[0] == 'apreensao':
        descricao_tipo_auto = "Auto de Apreensão"
    if partes_auto[0] == 'arrecadacao':
        descricao_tipo_auto = "Auto de Arrecadação"
    descricao_auto = descricao_tipo_auto + " nº " + numero_auto


    # ------------------------------------------------------------------
    # Recupera dados gerais que estão armazenados em tarefas
    # ------------------------------------------------------------------
    dict_software = dict()
    print_tela_log("- Recuperando dados gerais armazenados nas tarefas")
    for dados_item in Gitens:
        item = dados_item['item']
        # Despreza materiais de destino
        if item=='destino':
            continue

        recupera_dados_gerais_tarefas(dados_item, dict_software)

    # Ajuste em sapiSoftwareVersao
    lista_software=list(dict_software.keys())
    lista_software.sort()
    texto_sofware=", ".join(lista_software)

    # Monta dicionário de substituição
    dsub = dict()
    dsub['sapiAlvo'] = Gsolicitacao_exame["local_busca"]
    dsub['sapiAuto'] = descricao_auto
    dsub['sapiSoftwareVersao'] = texto_sofware

    # Substitui cada componente
    for substituir in dsub:

        # Efetua substituição de texto
        novo_valor = dsub[substituir]
        qtd_substituicoes = odt_substitui_campo_variavel_texto(Gmod_lista_cv, substituir, novo_valor)
        if (qtd_substituicoes == 0):
            print("Falhou na substituição de '" + substituir + "'")
            return
        else:
            print("- Substituído", substituir)

    # ------------------------------------------------------------------------------------------------------------------
    # Substitui sapiEntrega
    # ------------------------------------------------------------------------------------------------------------------

    nome_bloco_entrega=None
    cv_sapi_entrega = odt_localiza_campo_variavel(Gmod_lista_cv, GsapiEntrega)
    if (cv_sapi_entrega is None):
        print_tela_log(
            "AVISO: No modelo não existe campo (", + GsapiEntrega + "). Substituição não será efetuada.")
    else:
        print_tela_log("- Localizada variável", GsapiEntrega)
        # --- Início substituição de sapiEntrega
        # var_dump(solicitacao)
        #die('ponto1636')

        # Ajusta metodo_entrega
        metodo_entrega = Gsolicitacao_exame['dados_exame']['metodo_entrega']
        print_tela_log("- Método de entrega definido (SETEC3): ", metodo_entrega)
        # O método do banco vem no seguinte formato:
        # entrega_DVD
        # entrega_BLURAY
        # entrega_midiadestino
        # entrega_copia_pasta:sto_gtpi_ftk_entrega
        # yyy
        # Descartando o que vem depois de :
        # Exemplo: entrega_copia_pasta:sto_gtpi_ftk_entrega => entrega_copia_pasta
        partes = metodo_entrega.split(":")
        metodo_entrega=partes[0]
        # Remove o prefixo "entrega_"
        metodo_entrega = metodo_entrega.replace("entrega_", "")

        nome_bloco_entrega = GsapiEntrega + metodo_entrega
        nome_bloco_entrega = nome_bloco_entrega.lower()
        print_tela_log("- Bloco para substituição de ", GsapiEntrega, ": ",nome_bloco_entrega)


    # --------------------------------------------------------------------
    # Substitui campos variáveis por blocos com mesmo nome
    # ------------------------------------------------------------------
    print()
    print("Passo 6: Substituição de variáveis por blocos de parágrafos")
    print("-----------------------------------------------------------")

    # Monta lista de extensões de variáveis de laudo que devem ser consideradas
    # As extensões tratadas atualmente são:
    # paraCelular       => Relacionado com exame de celular em geral
    # paraSim           => Relacionado com exame específico de Sim Card
    # paraAparelho      => Relacionado com exame específico de aparelho Celular
    # paraArmazenamento => Relacionado com dispositivo de armazenamento de dados
    print("- Tipos de componentes a serem considerados: ", list(Gtipos_componentes.keys()))
    considerar=dict()
    if 'sim' in Gtipos_componentes:
        considerar['paraSim']=True
        considerar['paraCelular']=True
    if 'aparelho' in Gtipos_componentes:
        considerar['paraAparelho'] = True
        considerar['paraCelular'] = True
    if 'armazenamento' in Gtipos_componentes:
        considerar['paraArmazenamento'] = True
    print("- Considerando parágrafos com os seguintes sufixos: ", list(considerar.keys()))

    # Monta lista complementar, indicando quais variáveis devem ser desprezadas
    todas=('paraSim', 'paraAparelho', 'paraCelular', 'paraArmazenamento')
    desprezar=list()
    for d in todas:
        if considerar.get(d,None) is None:
            desprezar.append(d)
    print("- Eliminando parágrafos com variáveis contendo os seguintes sufixos: ", desprezar)

    # Em cada passada (iteração) efetua a substituição de um conjunto de variáveis
    # Nos novos parágrafos podem surgir novas variáveis, que por sua vez
    # devem ser substituidas (se houver algo para substituir)
    lista_variaveis_processadas=list()
    passada=0
    nova_variavel=True
    while nova_variavel:

        passada += 1
        # Será alterado para True, se alguma nova variável for encontrada
        nova_variavel=False

        # Substitui todas as variáveis disponíveis nesta passada
        # ------------------------------------------------------
        (sucesso, lista_cv) = odt_recupera_lista_campos_variaveis_sapi(Godt_raiz)
        for campo in lista_cv:
            nome_campo_variavel = campo['name'].lower()
            # print(nome_campo_variavel)

            # Despreza, se variável já foi processada
            if nome_campo_variavel in lista_variaveis_processadas:
                continue

            lista_variaveis_processadas.append(nome_campo_variavel)
            nova_variavel=True

            # Verifica se existe bloco com nome igual ao da variável
            nome_bloco_substituir=nome_campo_variavel
            # Variável sapiEntrega é uma exceção,
            # pois pode ser substituida por blocos diferentes,
            # dependendo do método de entrega (ex: sapiEntregaDVD)
            if nome_campo_variavel.lower()==GsapiEntrega.lower():
                nome_bloco_substituir=nome_bloco_entrega

            if Gmod_blocos.get(nome_bloco_substituir, None) is None:
                # Não existe bloco com o nome de campo variável. Despreza variável.
                print_log(passada, "Não foi encontrado bloco ", nome_bloco_substituir, "para substituir variável " + nome_campo_variavel)
                continue

            # Recupera lista de blocos do parágrafo
            lista_par_bloco = odt_clonar_bloco(nome_bloco_substituir, Gmod_blocos)

            # Localiza parágrafo pai onde está localizado a variável
            # uma vez que o parágrafo (inteiro) será substituido pelo conjunto de parágrafos do bloco
            # Atenção: Isto impede que um parágrafo contenha mais de uma variável
            paragrafo_substituir = odt_busca_ancestral_com_tipo(campo['pai'], raiz=Godt_raiz, tipo='p')

            # Recupera elemento pai do parágrafo aonde aparece variável
            elemento_pai = odt_determinar_elemento_pai(paragrafo_substituir, Godt_raiz)

            #odt_dump_paragrafo(paragrafo_substituir)
            #odt_dump_paragrafo(paragrafo_pai)
            #die('ponto2001')

            # Verifica se variável deve ser deprezada
            ignorar_variavel=False
            for d in desprezar:
                if str(d).lower() in str(nome_campo_variavel).lower():
                    ignorar_variavel=True
                    break

            if ignorar_variavel:
                # Elimina parágrafo que contém referência à variável
                elemento_pai.remove(paragrafo_substituir)
                print_log(passada, "Eliminado parágrafo que continha " + nome_campo_variavel + " uma vez que laudo não contém material desta natureza")
            else:
                # Substitui a variável
                odt_substituir_paragrafo_por_lista(paragrafo_substituir, Godt_raiz, lista_par_bloco)
                print_log(passada,"Substituída variável " + nome_campo_variavel + " por bloco correspondente")


    # ------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------
    # Geração de tabela de materiais devolvidos,
    # que na realidade são os materiais que estão associados (vinculados) ao laudo
    # ------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("Passo 7: Montagem de tabelas de materiais devolvidos")
    print("----------------------------------------------------")

    # Procura tabela de materiais devolvidos
    # ---------------------------------------
    tabela_matdevol = None
    for table in Godt_office_text.findall('table:table', Gxml_ns):
        nome_tabela = obtem_atributo_xml(table, 'table:name')
        if (nome_tabela == 'tabela_materiais_devolvidos'):
            print_log("- Localizada tabela de materiais devolvidos")
            tabela_matdevol = table

    if (tabela_matdevol is None):
        print_tela_log("- ERRO 2265: Não foi localizada a tabela de materiais devolvidos no modelo.")
        print_tela_log("- Esta tabela é caracterizada através da propriedade nome=tabela_materiais_devolvidos.")
        print_tela_log("- Verifique se o arquivo de modelo possui esta tabela.")
        return None

    # ------------------------------------------------------------------------------------------------------------------
    # Isola linha de modelo da tabela de matdevol
    # ------------------------------------------------------------------------------------------------------------------
    # Parte-se do princípio que a tabela terá um cabeçalho,
    # seguido da linha de modelo.
    # A linha de modelo DEVE SER ÚNICA, e será sempre a última linha
    # da tabela.
    # ------------------------------------------------------------------------------------------------------------------
    tr_linhas = tabela_matdevol.findall('table:table-row', Gxml_ns)
    qtd_linhas = len(tr_linhas)
    if (qtd_linhas != 1):
        print_tela_log("- Tabela de materais devolvidos contém", qtd_linhas, " linhas, o que é incomum.")
        print_tela_log("- Assumindo que a linha de modelo para substituição é a última linha da tabela")
    tr_modelo_linha_matdevol = tabela_matdevol.findall('table:table-row', Gxml_ns)[qtd_linhas - 1]

    # Valida linha da tabela
    # Tem que ter pelo menos uma variável (ex: {sapiItem})
    # ------------------------------------------------------------------
    print_log("- Recuperando campos variáveis da tabela")
    (sucesso, lista_cv_tabela_matdevol) = odt_recupera_lista_campos_variaveis_sapi(tr_modelo_linha_matdevol)
    if (len(lista_cv_tabela_matdevol) == 0):
        print_tela_log(
            "ERRO: Não foi detectado nenhum campo variável nesta tabela. Assegure-se de utilizar um modelo sapi para a geração do laudo")
        return

    # ------------------------------------------------------------------
    # Gera linhas na tabela de materiais devolvidos
    # ------------------------------------------------------------------
    # Determina posição aonde está a linha de modelo.
    # Nesta posição serão inseridas as novas linhas da tabela.
    posicao_inserir_tab_matdevol = odt_determina_posicao_pai_filho(tabela_matdevol, tr_modelo_linha_matdevol)

    dic_mat=dict()
    qtd_destino=0
    # Processa itens, agrupando dados por materiais
    for dados_item in Gitens:

        #var_dump(item)

        item = dados_item['item']
        # yyy
        #var_dump(dados_item)
        #die('ponto1820')

        if item=='destino':
            qtd_destino += 1

        material=dados_item['material']

        # Se vier um sufixo (quando tem vários itens em um material), remove sufixo
        # pois na tabela de materiais de devolução será agrupado
        # exemplo: 3200/2016 (1) => 3200/2016
        partes = material.split('(')
        material = partes[0].strip()

        # Coloca ano na frente do material, para ordenar corretamente
        # exemplo: 3200/2016 => 2016_3200
        partes = material.split('/')
        material_ano_numero=partes[1] + "_" + partes[0]

        #var_dump(material_ano_numero)

        # Verifica se material já existe
        if material_ano_numero in dic_mat:
            # Se Material já existe, apenas adiciona o item na lista de itens do material e passa para próximo item
            dic_mat[material_ano_numero]['itens'].append(item)
            continue

        # Material ainda não existe. Será incluído no dicionário
        dic_mat[material_ano_numero]=dict()
        dic_mat[material_ano_numero]['material'] = material
        dic_mat[material_ano_numero]['lacre'] = dados_item.get('lacre')
        dic_mat[material_ano_numero]['descricao'] = dados_item.get('descricao')
        dic_mat[material_ano_numero]['destino'] = dados_item.get('destino')
        # Cria lista de itens e adciona item atual
        dic_mat[material_ano_numero]['itens'] = list()
        dic_mat[material_ano_numero]['itens'].append(item)

    #var_dump(dic_mat)

    # Processa materias, gerando linhas na tabela
    for ix_mat in sorted(list(dic_mat.keys())):

        mat=dic_mat[ix_mat]

        print_tela_log("- Tabela de materias devolvidos, processando material ", mat['material'])

        # Processa item, gerando uma ou mais linhas de matdevol
        linha = criar_linha_matdevol(tr_modelo_linha_matdevol, mat)

        # Insere nova linha na tabela de matdevol
        tabela_matdevol.insert(posicao_inserir_tab_matdevol, linha)
        posicao_inserir_tab_matdevol += 1

    # --- Fim do loop de processamento dos itens da tabela de matdevol
    # Remove linha de modelo da tabela
    tabela_matdevol.remove(tr_modelo_linha_matdevol)

    # Verifica se método de entrega está coerente com materiais de destino do laudo
    if not conferir_metodo_entregua(metodo_entrega, qtd_destino):
        print("- Comando cancelado")
        return

    # ------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------
    # Geração de tabela de hash
    # ------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("Passo 8: Montagem de tabelas de hashes")
    print("--------------------------------------")

    # Procura tabela de hashes
    # ---------------------------
    tabela_hashes = None
    for table in Godt_office_text.findall('table:table', Gxml_ns):
        nome_tabela = obtem_atributo_xml(table, 'table:name')
        if (nome_tabela == 'tabela_hashes'):
            print_log("- Localizada tabela de hashes")
            tabela_hashes = table

    if (tabela_hashes is None):
        print_tela_log("- ERRO: Não foi localizada a tabela de hashes.")
        print_tela_log("A tabela de hashes é caracterizada através da propriedade nome=tabela_hashes.")
        print_tela_log("Verifique se o arquivo de modelo a partir do qual foir gerado o laudo atende este requisito.")
        return None

    # ------------------------------------------------------------------------------------------------------------------
    # Isola linha de modelo da tabela de hashes
    # ------------------------------------------------------------------------------------------------------------------
    # Parte-se do princípio que a tabela terá um cabeçalho,
    # seguido da linha de modelo.
    # A linha de modelo DEVE SER ÚNICA, e será sempre a última linha
    # da tabela.
    # ------------------------------------------------------------------------------------------------------------------
    tr_linhas = tabela_hashes.findall('table:table-row', Gxml_ns)
    qtd_linhas = len(tr_linhas)
    if (qtd_linhas != 2):
        # Não é comum ter mais de duas linhas...então é melhor avisar
        print_tela_log("- Tabela de hashes contém", qtd_linhas, " linhas, o que é incomum.")
        print_tela_log("- Assumindo que a linha de modelo para substituição é a última linha da tabela")
    tr_modelo_linha_hash = tabela_hashes.findall('table:table-row', Gxml_ns)[qtd_linhas - 1]

    # Valida linha da tabela de hashes.
    # Tem que ter pelo menos uma variável (ex: {sapiHashValor})
    # ------------------------------------------------------------------
    print_log("- Recuperando campos variáveis da tabela de hashes")
    (sucesso, lista_cv_tabela_hashes) = odt_recupera_lista_campos_variaveis_sapi(tr_modelo_linha_hash)
    if (len(lista_cv_tabela_hashes) == 0):
        print_tela_log(
            "ERRO: Não foi detectado nenhum campo variável na tabela de hashes. Assegure-se de utilizar um modelo sapi para a geração do laudo")
        return

    # ------------------------------------------------------------------
    # Gera linhas na tabela de Hashes
    # ------------------------------------------------------------------

    # Determina posição aonde está a linha de modelo.
    # Nesta posição serão inseridas as novas linhas da tabela.
    posicao_inserir_tab_hashes = odt_determina_posicao_pai_filho(tabela_hashes, tr_modelo_linha_hash)

    # Processa por item, para ficar organizado na tabela
    for dados_item in Gitens:

        item = dados_item['item']
        # Despreza materiais de destino
        if item=='destino':
            continue

        print_tela_log("- Tabela de hashes, processando item ", item)

        # Processa item, gerando uma ou mais linhas de hash
        linhas_hash = criar_linhas_hash_para_item(tr_modelo_linha_hash, dados_item)

        for linha in linhas_hash:
            # Insere nova linha na tabela de hashes
            tabela_hashes.insert(posicao_inserir_tab_hashes, linha)
            posicao_inserir_tab_hashes += 1

    # --- Fim do loop de processamento dos itens da tabela de hashes
    # Remove linha de modelo da tabela
    tabela_hashes.remove(tr_modelo_linha_hash)

    # ------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------
    # Procedimentos finais
    # ------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("Passo 9: Procedimentos finais")
    print("-----------------------------")

    # Gera novo arquivo
    if atualiza_arquivo_laudo(Godt_raiz, caminho_arquivo_saida_odt):
        # Se gravou com sucesso, sugere abertura
        print()
        print("- Laudo SAPI ajustado gravado em: ", caminho_arquivo_saida_odt)
        if pergunta_sim_nao("< Deseja abrir o arquivo de laudo para edição?"):
            webbrowser.open(caminho_arquivo_saida_odt)
            print("- Laudo SAPI foi aberto em programa compatível (normalmente libreoffice)")
            print("- Recomenda-se utilizar o LIBREOFFICE com versão superior a 5.2")


    return


# Remove todos os comentários do documento
# Um comentário é um parágrafo iniciado por #
def mod_remove_comentarios(base):

    lista_paragrafos = odt_recupera_lista_paragrafos(base)

    for p in lista_paragrafos:
        paragrafo = p["elemento"]
        texto = odt_obtem_texto_total_paragrafo(paragrafo)

        # Se começa por #, remove
        if len(texto) >= 1 and (texto[0] == "#"):
            # Remove
            pai = p["pai"]
            pai.remove(paragrafo)


# Busca constantes no arquivo de laudo
# As constantes estão em parâgrafos iniciados por #@
# Exemplo:
# @MODELO_VERSAO_2_3
def mod_buscar_constantes(base):

    constantes = list()

    # Recupera lista de parágrafos
    lista_paragrafos = odt_recupera_lista_paragrafos(base)

    # Verifica quais parágrafos são 'Constantes'
    # Uma constante é iniciada por #@
    for p in lista_paragrafos:
        paragrafo = p["elemento"]
        texto = odt_obtem_texto_total_paragrafo(paragrafo)
        texto = texto.strip()

        # Se começa por #, remove
        if len(texto) >= 3 and (texto[0] == "#") and texto[1]=='@':
            #Linha de configuração do modelo
            texto=texto.replace('#@','')
            texto=texto.strip()
            constantes.append(texto)

    # Devolve lista de constantes identificadas
    return constantes

#
# Remove todos os elementos posicionados após @FIM_LAUDO
def mod_remove_tudo_apos_fim_laudo(base):

    lista_paragrafos = odt_recupera_lista_paragrafos(base)

    fim_laudo_encontrado = False
    for p in lista_paragrafos:
        paragrafo = p["elemento"]
        texto = odt_obtem_texto_total_paragrafo(paragrafo)

        # Se começa por #, remove
        if len(texto) >= 1 and (texto[0] == "#"):
            if "@FIM_LAUDO" in texto:
                fim_laudo_encontrado = True

        if fim_laudo_encontrado:
            pai = p["pai"]
            pai.remove(paragrafo)


# Efetua ajustes no arquivo de laudo
def atualiza_arquivo_laudo(odt_raiz, caminho_arquivo_saida_odt):

    #
    # Remove todos os comentários do documento gerado
    # Um comentário é um parágrafo iniciado por #
    mod_remove_comentarios(odt_raiz)

    # Remove qualquer coisa apos tag de finalização de laudo
    mod_remove_tudo_apos_fim_laudo(odt_raiz)

    return odt_substitui_content_xml(odt_raiz, caminho_arquivo_saida_odt)



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
        print("- Existem", qtd_nao_pronto, "itens que NÃO ESTÃO PRONTOS para laudo.")
        return False

    # Tudo certo
    return True



# ==================================================================================================================
# Validação de modelo SAPI
# Utilizado pelo administrador SAPI para determinar se o modelo de laudo contém erros
# ==================================================================================================================

# Validar laudo
# ----------------------------------------------------------------------------------------------------------------------
def validacao_modelo_sapi():
    console_executar_tratar_ctrc(funcao=_validacao_modelo_sapi)


def _validacao_modelo_sapi():
    # # Fazendo teste...com modelo de laudo fixo
    # print("Em modo de desenvolvimento...desviando para teste1()")
    # caminho_laudo = "D:/Exames_andamento/memorando 1086_16 celulares/Laudo_2122_2016_SETEC_SR_PF_PR (23).odt"
    # ajustar_laudo_odt(caminho_laudo)
    # return

    print()
    print(" Validar MODELO SAPI de laudo ")
    print("------------------------------")
    print("- Esta função tem como objetivo auxiliar o administrador SAPI a validar um modelo de laudo padrão SAPI")
    print("  antes de fazer o upload do modelo para o Siscrim")
    print("- Isto elimina a chance de se fazer o upload de um modelo com algum problema sintático que inviabilize o seu uso")

    # ------------------------------------------------------------------------------------------------------------------
    # Seleciona o modelo do laudo
    # ------------------------------------------------------------------------------------------------------------------

    print()
    print("Selecione arquivo de modelo de laudo SAPI")
    print("-----------------------------------------")
    print("- Recomenda-se sejam feitas validações regulares, a cada alteração significativa no modelo.")
    print("- Desta forma, ficará mais fácil identificar o problema.")
    print("- Na janela gráfica que foi aberta, selecione o arquivo .ODT do modelo")


    while True:
        # Cria janela para seleção de laudo
        root = tkinter.Tk()
        j = JanelaTk(master=root)
        caminho_modelo = j.selecionar_arquivo([('ODT files', '*.odt')], titulo="Abra arquivo contendo o modelo SAPI")
        root.destroy()
    
        # Exibe arquivo selecionado
        if (caminho_modelo == ""):
            print()
            print("- Nenhum arquivo de modelo foi selecionado.")
            return

        print("- Arquivo de modelo selecionado:", caminho_modelo)
        
        # Verifica se arquivo tem extensão odt
        if (".odt" not in caminho_modelo.lower()):
            print_tela_log("- Arquivo de entrada [", caminho_modelo, "] não possui extensão .odt")
            continue

        print_log("- Validando modelo [", caminho_modelo, "]")
        break


    # Fica em loop de validação, até usuário ficar satifisfeito
    validado_com_sucesso = loop_validacao_modelo(caminho_modelo)


    # Se a última validação obteve sucesso, sugere atualização do modelo no Siscrim
    if validado_com_sucesso:
        print()
        print("- Se você terminou a customização do modelo, crie/atualize o modelo de laudo da Unidade no SisCrim")
        if pergunta_sim_nao("< Deseja atualizar o modelo no Siscrim agora", default="s"):
            abrir_browser_siscrim("/sistemas/criminalistica/modelo_usuario.php?acao=listar",
                                  descricao_pagina="Administração do Sistema => Modelos de Usuário")


    return validado_com_sucesso


# Fica em loop de validação
# Desta forma o usuário pode informar o arquivo apenas uma vez
# Ir fazendo alterações e validando apenas ao confirmar a repetição da validação
# Retorna se na última validação foi obtido sucesso
def loop_validacao_modelo(caminho_modelo):

    # ------------------------------------------------------------------------------------------
    # Fica em loop de validação
    # Desta forma o usuário pode informar o arquivo apenas uma vez
    # Ir fazendo alterações e validando apenas ao confirmar a repetição da validação
    # ------------------------------------------------------------------------------------------
    validado_com_sucesso=False
    while True:

        # Valida modelo
        # -------------
        print()
        print("Iniciando validação")
        print("-------------------")

        # Valida modelo, exibindo mensagens voltadas para Administrador SAPI
        validado_com_sucesso = carrega_valida_modelo(caminho_modelo, template=True)
        if validado_com_sucesso:
            print()
            print_tela("-"*100)
            print("Quesitação")
            print_tela("-"*100)
            _usuario_escolhe_quesitacao(Gmod_quesitos_respostas, apenas_listar=True)
            print()
            print_tela("- SUCESSO. Arquivo contém um MODELO de laudo SAPI sintaticamente correto.")

        # Continua validando
        print()
        if not pergunta_sim_nao("< Deseja validar novamente o arquivo?", default="s"):
            print_tela_log("- Validação do arquivo de modelo", caminho_modelo, "encerrada")
            break


    #
    return validado_com_sucesso


# Retorna verdadeiro se variavel é do Siscrim
def eh_variavel_siscrim(campo):

    # Esta é a lista de campos variáveis que o siscrim disponibiliza para inclusão nos modelos
    # Se no futuro o siscrim for atualizado e surgirem novas variáveis, vai ter que incluir aqui
    lista_campos_siscrim = [
        'abreviacao_subtipo_documento',
         'abreviacao_tipo_documento',
         'abreviacao_tipo_documento_raiz',
         'abreviacao_tipo_documento_referencia',
         'abreviacao_tipo_documento_solicitacao_exame',
         'abreviacao_tipo_procedimento',
         'abreviacao_tipo_procedimento_documento_raiz',
         'abreviacao_tipo_procedimento_documento_referencia',
         'ano_documento',
         'ano_documento_raiz',
         'ano_documento_referencia',
         'ano_documento_solicitacao_exame',
         'ano_laudo_relacionado',
         'ano_registro',
         'ano_registro_documento_raiz',
         'ano_registro_documento_referencia',
         'ano_registro_local',
         'ano_registro_local_documento_raiz',
         'ano_registro_local_documento_referencia',
         'ano_registro_local_material_examinado',
         'ano_registro_local_material_examinado_antes_desmembramento',
         'ano_registro_local_material_midia_espelhamento',
         'ano_registro_local_material_nao_examinado',
         'ano_registro_local_midia_gerada',
         'ano_registro_material_examinado',
         'ano_registro_material_examinado_antes_desmembramento',
         'ano_registro_material_midia_espelhamento',
         'ano_registro_material_nao_examinado',
         'ano_registro_midia_gerada',
         'artigo_definido_signatario',
         'artigo_definido_signatario_documento_raiz',
         'artigo_definido_signatario_documento_referencia',
         'artigo_definido_signatario_solicitacao_exame',
         'artigo_definido_signatarios',
         'artigo_definido_solicitante_documento_referencia',
         'artigo_definido_solicitante_exame',
         'artigo_definido_substituto_unidade_emissora',
         'artigo_definido_tipo_documento',
         'artigo_definido_tipo_documento_raiz',
         'artigo_definido_tipo_documento_referencia',
         'artigo_definido_tipo_documento_solicitacao_exame',
         'artigo_definido_tipo_procedimento',
         'artigo_definido_tipo_procedimento_documento_raiz',
         'artigo_definido_tipo_procedimento_documento_referencia',
         'artigo_definido_titular_unidade_emissora',
         'artigo_definido_unidade_acima_superior',
         'artigo_definido_unidade_emissora',
         'artigo_definido_unidade_superior',
         'assunto',
         'auto_apreensao_material_examinado',
         'auto_apreensao_material_examinado_antes_desmembramento',
         'auto_apreensao_material_midia_espelhamento',
         'auto_apreensao_material_nao_examinado',
         'avaliacao_monetaria',
         'bairro_unidade_emissora',
         'cargo_signatario',
         'cargo_substituto_unidade_emissora',
         'cargo_titular_unidade_emissora',
         'cargos_signatarios',
         'cep_unidade_emissora',
         'cidade_exame',
         'cidade_unidade_emissora',
         'classe_laudo',
         'classe_signatario',
         'codigo_barras_material_examinado',
         'codigo_barras_material_examinado_antes_desmembramento',
         'codigo_barras_material_midia_espelhamento',
         'codigo_barras_material_nao_examinado',
         'codigo_barras_midia_gerada',
         'codigo_documento',
         'complexidade_solicitacao_exame',
         'criticidade_solicitacao_exame',
         'data_emissao',
         'data_emissao_documento_raiz',
         'data_emissao_documento_referencia',
         'data_emissao_laudo_relacionado',
         'data_emissao_solicitacao_exame',
         'data_limite_atendimento_solicitacao_exame',
         'data_registro',
         'data_registro_documento_raiz',
         'data_registro_documento_referencia',
         'data_registro_local',
         'data_registro_local_documento_raiz',
         'data_registro_local_documento_referencia',
         'datum_exame',
         'descricao_material_examinado',
         'descricao_material_examinado_antes_desmembramento',
         'descricao_material_midia_espelhamento',
         'descricao_material_nao_examinado',
         'descricao_midia_gerada',
         'dia_emissao',
         'email_unidade_emissora',
         'endereco_exame',
         'endereco_unidade_emissora',
         'equipe_busca_material_examinado',
         'equipe_busca_material_examinado_antes_desmembramento',
         'equipe_busca_material_midia_espelhamento',
         'equipe_busca_material_nao_examinado',
         'estado_exame',
         'estado_unidade_emissora',
         'fax_unidade_emissora',
         'funcao_signatario_documento_raiz',
         'funcao_signatario_documento_referencia',
         'funcao_signatario_solicitacao_exame',
         'funcao_solicitante_documento_referencia',
         'funcao_solicitante_exame',
         'funcao_substituto_unidade_emissora',
         'funcao_titular_unidade_emissora',
         'identificacao',
         'identificacao_documento_raiz',
         'identificacao_documento_referencia',
         'identificacao_material_examinado',
         'identificacao_material_examinado_antes_desmembramento',
         'identificacao_material_midia_espelhamento',
         'identificacao_material_nao_examinado',
         'identificacao_midia_gerada',
         'identificacao_solicitacao_exame',
         'item_apreensao_material_examinado',
         'item_apreensao_material_examinado_antes_desmembramento',
         'item_apreensao_material_midia_espelhamento',
         'item_apreensao_material_nao_examinado',
         'lacre_antigo_material_examinado',
         'lacre_antigo_material_examinado_antes_desmembramento',
         'lacre_antigo_material_midia_espelhamento',
         'lacre_antigo_material_nao_examinado',
         'lacre_antigo_midia_gerada',
         'lacre_material_examinado',
         'lacre_material_examinado_antes_desmembramento',
         'lacre_material_midia_espelhamento',
         'lacre_material_nao_examinado',
         'lacre_midia_gerada',
         'latitude_exame',
         'local_apreensao_material_examinado',
         'local_apreensao_material_examinado_antes_desmembramento',
         'local_apreensao_material_midia_espelhamento',
         'local_apreensao_material_nao_examinado',
         'longitude_exame',
         'mandado_busca_material_examinado',
         'mandado_busca_material_examinado_antes_desmembramento',
         'mandado_busca_material_midia_espelhamento',
         'mandado_busca_material_nao_examinado',
         'marca_material_examinado',
         'marca_material_examinado_antes_desmembramento',
         'marca_material_midia_espelhamento',
         'marca_material_nao_examinado',
         'marca_midia_gerada',
         'matricula_signatario',
         'medida_material_examinado',
         'medida_material_examinado_antes_desmembramento',
         'medida_material_midia_espelhamento',
         'medida_material_nao_examinado',
         'medida_midia_gerada',
         'mes_emissao',
         'modelo_material_examinado',
         'modelo_material_examinado_antes_desmembramento',
         'modelo_material_midia_espelhamento',
         'modelo_material_nao_examinado',
         'modelo_midia_gerada',
         'motivo_criticidade_solicitacao_exame',
         'nome_guerra_signatario',
         'nome_orgao_documento_raiz',
         'nome_orgao_documento_referencia',
         'nome_orgao_solicitacao_exame',
         'nome_signatario',
         'nome_signatario_documento_raiz',
         'nome_signatario_documento_referencia',
         'nome_signatario_solicitacao_exame',
         'nome_solicitante_documento_referencia',
         'nome_solicitante_exame',
         'nome_substituto_unidade_emissora',
         'nome_titular_unidade_emissora',
         'nome_unidade_acima_superior',
         'nome_unidade_emissora',
         'nome_unidade_medida_material_examinado',
         'nome_unidade_medida_material_examinado_antes_desmembramento',
         'nome_unidade_medida_material_midia_espelhamento',
         'nome_unidade_medida_material_nao_examinado',
         'nome_unidade_medida_midia_gerada',
         'nome_unidade_superior',
         'numero_documento',
         'numero_documento_raiz',
         'numero_documento_referencia',
         'numero_documento_solicitacao_exame',
         'numero_itens_material_examinado',
         'numero_itens_material_examinado_antes_desmembramento',
         'numero_itens_material_midia_espelhamento',
         'numero_itens_material_nao_examinado',
         'numero_itens_midia_gerada',
         'numero_laudo_relacionado',
         'numero_procedimento',
         'numero_procedimento_documento_raiz',
         'numero_procedimento_documento_referencia',
         'numero_registro',
         'numero_registro_documento_raiz',
         'numero_registro_documento_referencia',
         'numero_registro_local',
         'numero_registro_local_documento_raiz',
         'numero_registro_local_documento_referencia',
         'numero_registro_local_material_examinado',
         'numero_registro_local_material_examinado_antes_desmembramento',
         'numero_registro_local_material_midia_espelhamento',
         'numero_registro_local_material_nao_examinado',
         'numero_registro_local_midia_gerada',
         'numero_registro_material_examinado',
         'numero_registro_material_examinado_antes_desmembramento',
         'numero_registro_material_midia_espelhamento',
         'numero_registro_material_nao_examinado',
         'numero_registro_midia_gerada',
         'numero_serie_material_examinado',
         'numero_serie_material_examinado_antes_desmembramento',
         'numero_serie_material_midia_espelhamento',
         'numero_serie_material_nao_examinado',
         'numero_serie_midia_gerada',
         'numero_siapro',
         'numero_siapro_documento_raiz',
         'numero_siapro_documento_referencia',
         'observacao_material_examinado',
         'observacao_material_examinado_antes_desmembramento',
         'observacao_material_midia_espelhamento',
         'observacao_material_nao_examinado',
         'observacao_midia_gerada',
         'operacao',
         'operacao_documento_raiz',
         'operacao_documento_referencia',
         'operacao_material_examinado',
         'operacao_material_examinado_antes_desmembramento',
         'operacao_material_midia_espelhamento',
         'operacao_material_nao_examinado',
         'ordem_signatario',
         'part_number_material_examinado',
         'part_number_material_examinado_antes_desmembramento',
         'part_number_material_midia_espelhamento',
         'part_number_material_nao_examinado',
         'part_number_midia_gerada',
         'preposicao_signatario_documento_raiz',
         'preposicao_signatario_documento_referencia',
         'preposicao_signatario_solicitacao_exame',
         'preposicao_solicitante_documento_referencia',
         'preposicao_solicitante_exame',
         'preposicao_substituto_unidade_emissora',
         'preposicao_titular_unidade_emissora',
         'procedimento',
         'procedimento_documento_raiz',
         'procedimento_documento_referencia',
         'pronome_demonstrativo_tipo_documento',
         'pronome_demonstrativo_unidade_emissora',
         'registro',
         'registro_documento_raiz',
         'registro_documento_referencia',
         'registro_local',
         'registro_local_documento_raiz',
         'registro_local_documento_referencia',
         'registro_local_material_examinado',
         'registro_local_material_examinado_antes_desmembramento',
         'registro_local_material_midia_espelhamento',
         'registro_local_material_nao_examinado',
         'registro_local_midia_gerada',
         'registro_material_examinado',
         'registro_material_examinado_antes_desmembramento',
         'registro_material_midia_espelhamento',
         'registro_material_nao_examinado',
         'registro_midia_gerada',
         'resumo',
         'resumo_documento_raiz',
         'resumo_documento_referencia',
         'resumo_material_examinado',
         'resumo_material_examinado_antes_desmembramento',
         'resumo_material_midia_espelhamento',
         'resumo_material_nao_examinado',
         'resumo_midia_gerada',
         'resumo_solicitacao_exame',
         'sigla_cargo_signatario',
         'sigla_cargo_substituto_unidade_emissora',
         'sigla_cargo_titular_unidade_emissora',
         'sigla_orgao_documento_raiz',
         'sigla_orgao_documento_referencia',
         'sigla_orgao_procedimento',
         'sigla_orgao_procedimento_documento_raiz',
         'sigla_orgao_procedimento_documento_referencia',
         'sigla_orgao_solicitacao_exame',
         'sigla_unidade_acima_superior',
         'sigla_unidade_emissora',
         'sigla_unidade_emissora_laudo_relacionado',
         'sigla_unidade_registro',
         'sigla_unidade_registro_documento_raiz',
         'sigla_unidade_registro_documento_referencia',
         'sigla_unidade_registro_local',
         'sigla_unidade_registro_local_documento_raiz',
         'sigla_unidade_registro_local_documento_referencia',
         'sigla_unidade_registro_local_material_examinado',
         'sigla_unidade_registro_local_material_examinado_antes_desmembramento',
         'sigla_unidade_registro_local_material_midia_espelhamento',
         'sigla_unidade_registro_local_material_nao_examinado',
         'sigla_unidade_registro_local_midia_gerada',
         'sigla_unidade_registro_material_examinado',
         'sigla_unidade_registro_material_examinado_antes_desmembramento',
         'sigla_unidade_registro_material_midia_espelhamento',
         'sigla_unidade_registro_material_nao_examinado',
         'sigla_unidade_registro_midia_gerada',
         'sigla_unidade_superior',
         'simbolo_unidade_medida_material_examinado',
         'simbolo_unidade_medida_material_examinado_antes_desmembramento',
         'simbolo_unidade_medida_material_midia_espelhamento',
         'simbolo_unidade_medida_material_nao_examinado',
         'simbolo_unidade_medida_midia_gerada',
         'situacao_solicitacao_exame',
         'subclasse_laudo',
         'subtipo_documento',
         'subtitulo_laudo',
         'telefone_unidade_emissora',
         'tipo_documento',
         'tipo_documento_raiz',
         'tipo_documento_referencia',
         'tipo_documento_solicitacao_exame',
         'tipo_material_examinado',
         'tipo_material_examinado_antes_desmembramento',
         'tipo_material_midia_espelhamento',
         'tipo_material_nao_examinado',
         'tipo_midia_gerada',
         'tipo_procedimento',
         'tipo_procedimento_documento_raiz',
         'tipo_procedimento_documento_referencia',
         'titulo_laudo',
         'tratamento_signatario_documento_raiz',
         'tratamento_signatario_documento_referencia',
         'tratamento_signatario_solicitacao_exame',
         'tratamento_solicitante_documento_referencia',
         'tratamento_solicitante_exame',
         'tratamento_substituto_unidade_emissora',
         'tratamento_titular_unidade_emissora',
         'ultimo_lacre_removido_material_examinado']

    for nome_base_campo in lista_campos_siscrim:
        # Alguns campos tem sufixo associados à ocorrência
        # Por exemplo: se tem dois materiais associados ao laudo,
        # os campos do primeiro material terão sufixo 1 e do segundo 2
        if campo.startswith(nome_base_campo):
            # Campo está na lista dos campos do siscrim
            return True

    return False


# # Função que carrega o arquivo de modelo e valida sintaticamente
# # True: Modelo carregado e válido
# # False: Ocorreu algum erro (já indicado)
# def carrega_valida_modelo_deprecated(caminho_arquivo_saida_odt, template=False):
#
#     global Gmod_blocos
#     global Gfilho_para_pai_map
#     global Glista_cv_office_text
#     global Godt_raiz
#     global Gmod_quesitos_respostas
#     global Goffice_text
#     global Gmod_tabelas
#
#     # -------------------------------------------------------------------
#     # Extrai arquivo de conteúdo (content.xml) do odt
#     # -------------------------------------------------------------------
#
#     # Um arquivo ODT é um ZIP contendo arquivos XML
#     # Logo, primeiramente é necessário abrir o zip
#     print_log("- Unzipando arquivo de saída", caminho_arquivo_saida_odt)
#     zf = zipfile.ZipFile(caminho_arquivo_saida_odt, 'r')
#     # listarArquivos(zf)
#     # exibirInfo(zf)
#
#     # Cria pasta temporária para extrair arquivo
#     pasta_tmp = tempfile.mkdtemp()
#
#     # O conteúdo propriamente dito do arquivo ODT
#     # está armazenado no arquivo content.xml
#     arq_content_xml = "content.xml"
#     if not arq_content_xml in zf.namelist():
#         print_tela_log("- ERRO: Não foi encontrado arquivo: " + arq_content_xml)
#         return False
#
#     # Extrai e converte arquivo content.xml para um string xml
#     try:
#         # Extração de content.xml para arquivo em pasta temporária
#         zf.extract(arq_content_xml, pasta_tmp)
#         print_log("- Arquivo content_xml extraído para [", pasta_tmp, "]")
#         caminho_arq_content_xml = pasta_tmp + "/" + arq_content_xml
#
#         # Le todo o arquivo content.xml e armazena em string
#         xml_string = zf.read(arq_content_xml)
#     except BaseException as e:
#         print_tela_log("'ERRO: Não foi possível ler arquivo " + arq_content_xml)
#         print_tela_log("Erro: ", e)
#         return False
#
#     # Verifica se arquivo foi criado com sucesso
#     if (os.path.isfile(caminho_arq_content_xml)):
#         print_log("- Extraído arquivo de conteúdo (content.xml) com sucesso para [", caminho_arq_content_xml, "]")
#     else:
#         print_tela_log("- Extração de arquivo de conteúdo (content.xml) para [", caminho_arq_content_xml,
#                        "] FALHOU. Arquivo não foi encontrado.")
#         return False
#
#     # -------------------------------------------------------------------
#     # Início de parse de content.xml
#     # -------------------------------------------------------------------
#
#     #debug
#     print("1. Antes de carregar")
#     #odt_print_ns(parse_and_get_ns(caminho_arq_content_xml))
#     #die('ponto3190')
#
#     # Obtém namespaces do arquivo xml
#     # e salva em global Gxml_ns
#     odt_armazena_e_registra_ns(xml_parse_and_get_ns(caminho_arq_content_xml))
#
#     # Obrigatoriamente tem que existir um namespace "text"
#     if (Gxml_ns.get("text", None) is None):
#         # Se não existe a seção text, tem algo esquisito...
#         print_tela_log(
#             "- ERRO: Falhou no parse dos namespaces. Não encontrado seção 'text'. Assegure-se que o arquivo informado é um ODT bem formado.")
#         if not template:
#             # Dica de uso do modelo
#             print_tela_log(
#                 "- Assegure-se de ter escolhido o arquivo SEM sufixo _sapi, ou seja, o arquivo original gerado no SisCrim.")
#         return False
#
#     # Faz parse geral do arquivo, que já foi lido e armazenado em string
#     Godt_raiz = xml.etree.ElementTree.fromstring(xml_string)
#
#     print("2. apos carregar Godt_raiz")
#     odt_dump(Godt_raiz, nivel=0, nivel_max=1)
#
#
#     xml_string_alterado = xml.etree.ElementTree.tostring(Godt_raiz, encoding="utf-8")
#     x = xml.etree.ElementTree.XMLID(xml_string_alterado)
#
#     #var_dump(x)
#     #die('ponto3209')
#
#     # PONTO_CORTE_33354 (rotina foi dividida aqui)

# Função que carrega o arquivo de modelo e valida sintaticamente
# True: Modelo carregado e válido
# False: Ocorreu algum erro (já indicado)
def carrega_valida_modelo(caminho_arquivo, template=False):

    # Carrega arquivo ODT
    # -------------------
    if not odt_carrega_arquivo(caminho_arquivo):
        print_tela("Assegure-se de informar o nome de um arquivo de modelo SAPI")
        return False

    # -------------------------------------------------------------------
    # Carrega e valida CONSTANTES do Modelo SAPI
    # -------------------------------------------------------------------
    global Gmod_constantes
    Gmod_constantes = mod_buscar_constantes(Godt_raiz)
    print()
    print_tela_log("- Constantes: Iniciando validação")

    # Verifica se é modelo de laudo SAPI
    # Um modelo sapi sempre tem a constante FIM_LAUDO, que marca o fim de um modelo laudo
    constante_fim_laudo='FIM_LAUDO'
    if (constante_fim_laudo in Gmod_constantes):
        print("- Encontrada constante:", constante_fim_laudo)
    else:
        print_tela_log("- ERRO: Arquivo carregado não é um modelo SAPI (não possui constante FIM_LAUDO)")
        if "_sapi.odt" in caminho_arquivo:
            print_tela("Aparentemete você informou o laudo final gerado pelo sapi, com sufixo _sapi.odt")
            print_tela("Tente novamente fornecendo o ARQUIVO DE MODELO gerado no siscrim")
        return False

    #var_dump(Gmod_constantes)
    #die('ponto3370')

    #var_dump(Gmodelo_configuracao)
    #print(Gmodelo_configuracao)
    if (Gmodelo_versao_esperado in Gmod_constantes):
        print("- Encontrada constante:", Gmodelo_versao_esperado)
    else:
        print_tela_log("- ERRO: Este programa requer um laudo padrão SAPI", Gmodelo_versao_esperado)
        if template:
            print_tela_log("- Verifique se você não apagou por engano a seção de bloco de sistema, que fica após FIM_LAUDO em vermelho")
        else:
            # Dica de uso do modelo
            print_tela("- Retorne ao SisCrim e gere o modelo na versão mais atualizada.")
            print_tela("- Se isto não funcionar, consulte o administrador SAPI de sua unidade, e solicite que ele atualize o modelo SAPI")
        return False

    # Constantes que definem quesitações a serem ignoradas
    global Gmod_ignorar_quesitacoes
    Gmod_ignorar_quesitacoes = list()
    for c in Gmod_constantes:
        if ("ignorar_quesitacao_" in c):
            texto=str(c).replace("ignorar_quesitacao_","")
            (hash, valor)=texto.split('=')
            hash=str(hash).strip()
            valor=str(valor).strip()
            if valor=='0':
                continue
            if valor=='1':
                Gmod_ignorar_quesitacoes.append(hash)
                print_tela("- Ignorando quesitação:", hash)
                continue
            print("Constante mal formada: ", c)
            return False

    print_tela_log("- Constantes: OK")

    # -------------------------------------------------------------------
    # Recupera e valida lista de CAMPOS VARIÁVEIS
    # -------------------------------------------------------------------
    global Gmod_lista_cv
    print()
    print_tela_log("- Campos variáveis: Iniciando validação")
    (sucesso, Gmod_lista_cv) = odt_recupera_lista_campos_variaveis_sapi(Godt_office_text)
    #var_dump(lista_cv_office_text)
    #die('ponto1881')
    if (not sucesso):
        print_tela_log("ERRO: Modelo com campos variáveis inválidos")
        return False
    if (len(Gmod_lista_cv) == 0):
        print_tela_log("ERRO: Não foi detectado nenhum campo variável no padrão sapi.")
        return False

    # Campos obrigatórios no modelo de laudo
    cv_esperados=['sapiQuesitos',
                  'sapiRespostas',
                  'sapiEntrega'
                  ]
    for nome_cv in cv_esperados:
        if odt_procura_cv_lista(Gmod_lista_cv, nome_cv) is None:
            print_tela_log("- ERRO: Não foi encontrado campo obrigatório:", nome_cv)
            return False
        else:
            print_tela_log("- Encontrado campo obrigatório:", nome_cv)

    print_tela_log("- Campos variáveis: OK")

    # -------------------------------------------------------------------
    # Carrega e valida BLOCOS
    # -------------------------------------------------------------------
    global Gmod_blocos
    print()
    print_tela_log("- Blocos: Iniciando validação")
    # Recupera blocos de parágrafos
    excluir_blocos=True
    if template:
        excluir_blocos=False
    (sucesso, Gmod_blocos) = carrega_blocos(Godt_office_text, excluir_blocos)
    if (not sucesso):
        return False
    print("- Quantidade de blocos: ", len(Gmod_blocos))
    if (len(Gmod_blocos)==0):
        print("ERRO: Não foi encontrado nenhum bloco SAPI")
        return False

    # Verifica existência de blocos obrigatórios
    # ------------------------------------------
    blocos_esperados=['sapiIdentificacaoAparelho',
                      'sapiIdentificacaoSIM',
                      'sapiIdentificacaoArmazenamento'
                      ]
    for nome_bloco in blocos_esperados:
        if odt_procura_bloco(Gmod_blocos, nome_bloco) is None:
            print_tela_log("- ERRO: Não foi encontrado o bloco obrigatório:", nome_bloco)
            return False
        else:
            print_tela_log("- Encontrado bloco obrigatório:", nome_bloco)

    print_tela_log("- Blocos: OK")

    # -------------------------------------------------------------------
    # Verifica QUESITOS E RESPOSTAS
    # -------------------------------------------------------------------
    global Gmod_quesitos_respostas
    print()
    print_tela_log("- Quesitos e respostas: Iniciando validação")
    (sucesso, Gmod_quesitos_respostas) = parse_quesitos_respostas(Gmod_blocos)
    if not sucesso:
        return False
    qtd_quesitos = len(Gmod_quesitos_respostas)
    print("- Quantidade de quesitos encontrados:", qtd_quesitos)
    if (qtd_quesitos==0):
        print("- ERRO: Não foi encontrado nenhum quesito")
        return False
    for nome_quesito in Gmod_quesitos_respostas:
        print("- Quesito com identificação:", nome_quesito)

    print_tela_log("- Quesitos e respostas: OK")

    # -------------------------------------------------------------------
    # Carrega de valida lista de tabelas
    # -------------------------------------------------------------------
    global Gmod_tabelas
    print()
    print_tela_log("- Tabelas de modelo SAPI: Iniciando validação")
    Gmod_tabelas = dict()
    # Tabelas obrigatórias
    tabelas_esperadas=dict()
    tabelas_esperadas['tabela_materiais']=0
    tabelas_esperadas['tabela_hashes']=0
    tabelas_esperadas['tabela_quesitacoes']=0
    tabelas_esperadas['tabela_materiais_devolvidos']=0
    for table in odt_localiza_todos(pai=Godt_office_text, tag='table:table'):
        # print(table)
        # print(table.attrib)
        # die('ponto643')
        nome_tabela = obtem_atributo_xml(table, 'table:name')
        # print(nome_tabela)
        tabelas_esperadas[nome_tabela]=1
        Gmod_tabelas[nome_tabela]=table

    # Verifica se alguma tabela esperada não foi encontrada
    for nome_tabela in tabelas_esperadas:
        if tabelas_esperadas[nome_tabela]==0:
            print_tela_log("- ERRO: Tabela obrigatória", nome_tabela, "não foi encontrada. Você deve ter excluído por engano.")
            return False
        else:
            print("- Encontrada", nome_tabela)

    print_tela_log("- Tabelas de modelo SAPI: OK")

    # ------------------------------------------------------------------
    # Valida formato da tabela de materiais
    # ------------------------------------------------------------------
    print()
    print_tela_log("- Tabelas de materiais: Iniciando validação")
    tabela_materiais = Gmod_tabelas['tabela_materiais']

    # odt_localiza_todos(pai=xxxxxxxx, tag='zzzzz')
    # tr_linhas = tabela_materiais.findall('table:table-row', Gxml_ns)
    tr_linhas = odt_localiza_todos(pai=tabela_materiais, tag='table:table-row')
    # Na realidade a tabela de materiais tem duas linhas
    # Mas uma das linhas é de cabeçalho (que se repete em todas as páginas)
    # e portanto tem outro tag
    qtd_linhas = len(tr_linhas)
    print("- Quantidade de linhas da tabela: ", qtd_linhas)
    if (qtd_linhas != 1):
        print("- ERRO: Tabela de materiais só pode ter duas linhas")
        print("- ERRO: A primeira linha deve ser de cabeçalho (se repete em todas as páginas)")
        print("- ERRO: A segunda linha deve conter o modelo de linha")
        print("- ERRO: Não insira nenhuma linha na tabela de materiais, ou altere a definição de linha de cabeçalho")
        return False

    # Valida linha de modelo da tabela de materiais
    tr_modelo = tr_linhas[0]

    # Recupera campos variáveis da linha de modelo da tabela de materiais
    # ------------------------------------------------------------------
    print("- Verificando campos variáveis da tabela de materiais")
    (sucesso, lista_cv_tabela_materiais) = odt_recupera_lista_campos_variaveis_sapi(tr_modelo)
    if not sucesso:
        return False

    if (len(lista_cv_tabela_materiais) == 0):
        print_tela_log("- ERRO: Não foi detectado nenhum campo variável na tabela de materiais")
        return False

    # Campos obrigatórios no modelo de linha da tabela de materiais
    cv_esperados=['sapiItemIdentificacao']
    for nome_cv in cv_esperados:
        if odt_procura_cv_lista(lista_cv_tabela_materiais, nome_cv) is None:
            print_tela_log("- ERRO: Não foi encontrado campo obrigatório da tabela de materiais:", nome_cv)
            return False
        else:
            print_tela_log("- Encontrado campo obrigatório:", nome_cv)

    print_tela_log("- Tabelas de materiais: OK")

    # ------------------------------------------------------------------
    # Valida formato da tabela de quesitacoes
    # ------------------------------------------------------------------
    print()
    print_tela_log("- Tabelas de quesitacoes: Iniciando validação")
    tabela_quesitacoes = Gmod_tabelas['tabela_quesitacoes']

    tr_linhas = odt_localiza_todos(pai=tabela_quesitacoes, tag='table:table-row')
    # A tabela de quesitações inicialmente tem apenas uma linha
    # Mas durante a geração e atualização de modelo vai recebendo novas linhas
    # O modelo permanece na primeira linha
    qtd_linhas = len(tr_linhas)
    print("- Quantidade de linhas:", qtd_linhas)
    if (qtd_linhas == 0):
        print("- ERRO: Tabela de quesitacoes NÃO TEM nenhuma linha")
        return False

    # Valida linha de modelo da tabela de quesitacoes
    tr_modelo = tr_linhas[0]

    # Recupera campos variáveis da linha de modelo da tabela de quesitacoes
    # ------------------------------------------------------------------
    print("- Verificando campos variáveis da tabela de quesitacoes")
    (sucesso, lista_cv_tabela_quesitacoes) = odt_recupera_lista_campos_variaveis_sapi(tr_modelo)
    if not sucesso:
        return False

    if (len(lista_cv_tabela_quesitacoes) == 0):
        print_tela_log(
            "- ERRO: Não foi detectado nenhum campo variável na linha de modelo de tabela de quesitações(primeira linha útil, desprezando a linha de cabeçalho)")
        if modo_debug():
            odt_dump(tr_modelo)
        return False

    # Campos obrigatórios no modelo de linha da tabela de quesitacoes
    cv_esperados = ['SapiQuesitacaoHash']
    for nome_cv in cv_esperados:
        if odt_procura_cv_lista(lista_cv_tabela_quesitacoes, nome_cv) is None:
            print_tela_log("- ERRO: Não foi encontrado campo obrigatório da tabela de quesitacoes:", nome_cv)
            return False
        else:
            print_tela_log("- Encontrado campo obrigatório:", nome_cv)

    print_tela_log("- Tabelas de quesitacoes: OK")  # Modelo válido


    # Ok, tudo certo
    print_tela_log("- Modelo de laudo SAPI: OK (sintaticamente correto)")
    return True


# ==================================================================================================================
# @*gl - Geração de laudo
# ==================================================================================================================

# Gera laudo
# ----------------------------------------------------------------------------------------------------------------------
def gerar_laudo():
    console_executar_tratar_ctrc(funcao=_gerar_laudo)


def _gerar_laudo():
    # # Fazendo teste...com modelo de laudo fixo
    # print("Em modo de desenvolvimento...desviando para teste1()")
    # caminho_laudo = "D:/Exames_andamento/memorando 1086_16 celulares/Laudo_2122_2016_SETEC_SR_PF_PR (23).odt"
    # ajustar_laudo_odt(caminho_laudo)
    # return

    print()
    print_centralizado(" Gera laudo ")

    # ------------------------------------------------------------------------------------------------------------------
    # Verifica se laudo pode ser gerado
    # ------------------------------------------------------------------------------------------------------------------
    if not laudo_pronto():
        # Mensagens já foram exibidas na rotina chamada
        print("- Geração de laudo não pode ser realizada nesta situação")
        print("- Em caso de dúvida, consulte a situação no SETEC3 (*s3)")
        print("- Comando cancelado")
        return

    # ------------------------------------------------------------------------------------------------------------------
    # Verifica dados básicos do exame
    # ------------------------------------------------------------------------------------------------------------------
    print("- Verificando dados gerais do exame.")

    # Método de entrega
    metodo_entrega = Gsolicitacao_exame['dados_exame']['metodo_entrega']
    if metodo_entrega=='indefinido':
        print_atencao()
        print("- Para gerar o laudo você deve primeiramente definir o método de entrega (mídia óptica, cópia storage, etc).")
        print("- Dica: Configure no SETEC3 (*s3) e em seguida retorne a esta opção.")
        print("- Comando cancelado.")
        return

    # ------------------------------------------------------------------------------------------------------------------
    # Seleciona o modelo do laudo
    # ------------------------------------------------------------------------------------------------------------------

    print()
    print("Passo 1: Selecione arquivo de laudo (modelo)")
    print("-------------------------------------------")
    print("- Informe o arquivo de modelo para o laudo no padrão SAPI, gerado no SisCrim.")
    print("- Na janela gráfica que foi aberta, selecione o arquivo .ODT correspondente")
    print("- Se você ainda gerou o modelo, cancele e utilize a opção *ML")


    # Cria janela para seleção de laudo
    root = tkinter.Tk()
    j = JanelaTk(master=root)
    caminho_laudo = j.selecionar_arquivo([('ODT files', '*.odt')], titulo="Abra arquivo contendo o modelo SAPI do Laudo (.ODT), gerado no Siscrim")
    root.destroy()

    # Exibe arquivo selecionado
    if (caminho_laudo == ""):
        print()
        print("- Nenhum arquivo de laudo foi selecionado.")
        print("- DICA: Se você ainda não gerou o arquivo de modelo, utilize o comando *ML")
        return

    print("- Arquivo de entrada selecionado:", caminho_laudo)

    # Tudo certo
    ajustar_laudo_odt(caminho_laudo)


# Confere método de entrega
# Retorna: True => Sucesso, False: Método não está ok
# ----------------------------------------------------------------------------------------------------------------------
def conferir_metodo_entregua(metodo_entrega, qtd_destino):

    # Remove o prefixo fixo
    metodo_entrega = metodo_entrega.replace("entrega_", "")

    if metodo_entrega=='midiadestino':
        if qtd_destino==0:
            print()
            print_atencao()
            print("- Você selecionou como método de entrega 'Material de destino'")
            print("- Contudo, não foi localizado nenhum material de destino na lista de materiais vinculados ao laudo")
            print("- O material de destino deve atender as seguintes condições (no SisCrim):")
            print("- 1) No cadastro do material de destino(Siscrim):")
            print("     - O campo Finalidade deve ser 'EXAME' (não pode ser mídia para espelhamento, ou qualquer outra coisa)")
            print("     - O campo Item do auto de apreensão (da seção Busca e apreensão) deve ser preenchido com 'destino'")
            print("- 2) O material de destino deve estar vinculado ao laudo: ")
            print("     - Na consulta do laudo, este material deve aparecer na seção 'Material examinado'")
            print("     - Se não aparecer, utilize opção 'Corrigir documento' e marque o material de destino'")
            print("- Dica: Utilize comando *S3 para navegar para a solicitação de exame (Setec3) e *CL para ir para o laudo (SisCrim)")
            return False

    if metodo_entrega != 'midiadestino':
        if qtd_destino > 0:
            print()
            print_atencao()
            print("- Situação inconsistente impede geração de laudo.")
            print("- Neste laudo existe material de destino.")
            print("- Contudo, o método de entrega selecionado no exame SAPI não é através de 'Material de destino'")
            print("- Para resolver esta inconsistência, altere o método de entrega para 'Material de Destino' (Setec3)")
            print("  ou retire o material de destino da lista de materiais vinculados ao laudo (SisCrim)")
            print("- Dica: Utilize comando *S3 para navegar para a solicitação de exame (Setec3) e *CL para ir para o laudo (SisCrim)")
            return False

    # Tudo certo
    return True


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


# Exibe lista de tarefas
# ----------------------------------------------------------------------------------------------------------------------
def exibir_situacao():

    # Monta resumo por mídia
    resumir_midia()

    # cabecalho geral
    print_linha_cabecalho()

    # Calcula largura da última coluna, que é variável (item : Descrição)
    # A constante na subtração é a soma de todos os campos e espaços antes da última coluna
    lid = Glargura_tela - 28
    lid_formatado = "%-" + str(lid) + "." + str(lid) + "s"

    string_formatacao = '%2s %2s %-13s %-6s ' + lid_formatado

    # Lista de itens
    q = 0
    qtd_nao_pronto = 0
    qtd_destino = 0
    for i in Gitens:
        q += 1

        # Sinalizador de Corrente
        corrente = "  "
        if (q == Gicor):
            corrente = '=>'

        # var_dump(i)
        # cabecalho
        if (q == 1):
            print(string_formatacao % (" ", "Sq", "Material", "Pronto", "Item : Descrição"))
            print_centralizado("")
        # Tarefa
        item_descricao = i["item"] + " : " + i["descricao"]

        # Pronto para laudo
        if i["pronto_para_laudo"] == 't':
            pronto_para_laudo = "Sim"
        else:
            pronto_para_laudo = "NÃO"
            qtd_nao_pronto += 1

        if i['item']=='destino':
            qtd_destino += 1

        # Elementos para exibição
        subpasta=i["subpasta"]
        t=i.get("tamanho_destino_bytes", None)
        if t is None:
            tamanho_destino_bytes=0
            tamanho_destino_str="Indef"
        else:
            tamanho_destino_bytes=int(i["tamanho_destino_bytes"])
            tamanho_destino_str=converte_bytes_humano(tamanho_destino_bytes)

        # Mídia de destino
        midia=Gitem_midia.get(i["item"],'?')

        print(string_formatacao % (corrente, q, i["material"], pronto_para_laudo,
                                   item_descricao))
        if (q == Gicor):
            print_centralizado("")

    # Observações gerais
    print_centralizado()
    if (q == 0):
        print("- Não existe nenhum material vinculado ao laudo. Corrija Laudo no SisCrim.")
    else:
        print("- A lista acima apresenta apenas os materiais vinculados ao laudo.")

    if (qtd_nao_pronto > 0):
        print_atencao()
        print("- Existem", qtd_nao_pronto,
              "itens/materiais que foram vinculados ao laudo que ainda não estão prontos (ver coluna 'Pronto'), ")
        print("  pois ainda possuem tarefas pendentes.")
        print("- Enquanto esta condição persistir, não será possível efetuar a geração de laudo (*GL)")
        print("- Caso não seja possível examinar os materiais restantes, vá ao SETEC3, entre nas tarefas correspondentes,")
        print("  e utilize a opção REPORTAR INEXEQUILIDADE, para finalizar a tarefa.")
        print("- Para acessar rapidamente o setec3, utilize o comando *S3")
        return

    # Confere o método de entrega
    metodo_entrega = Gsolicitacao_exame['dados_exame']['metodo_entrega']
    if not conferir_metodo_entregua(metodo_entrega, qtd_destino):
        # método de entrega não está ok
        return

    # Tudo certo
    print("- Dicas:")
    print("  - Utilize o comando *ML para gerar o modelo de laudo padrão SAPI no Siscrim")
    print("  - Em seguida seguida utilize comando *GL para gerar o laudo (substituir os campos variáveis)")
    return



# Avisa que dados vieram do estado
# print("Dados carregados do estado.sapi")
# sprint("Isto so deve acontecer em ambiente de desenvolvimento")

# Inicia procedimento de obtenção de laudo, cancelando com CTR-C
# Retorna: Verdadeiro se foi selecionado um laudo
# ----------------------------------------------------------------------------------------------------------------------
def obter_laudo_ok():
    try:
        # matricula = obter_laudo_parte1()
        return obter_laudo_parte2()
    except KeyboardInterrupt:
        print()
        print("- Operação interrompida pelo usuário <CTR><C>")
        return False


# Seleciona matricula
# ----------------------------------------------------------------------------------------------------------------------
def obter_laudo_parte1_deprecated():

    print()
    print_centralizado(" Seleção de Laudo ")
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
def obter_laudo_parte2():

    # Irá atualizar a variável global de itens
    global Glaudo
    global Gitens
    global Gstorages_laudo
    global GdadosGerais

    matricula = obter_param_usuario("matricula")

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
        try:
            print_log("Recuperando solicitações de exame para matrícula: ", matricula)
            (sucesso, msg_erro, dados) = sapisrv_chamar_programa(
                programa="sapisrv_obter_itens_laudo.php",
                parametros={'codigo_solicitacao_exame_siscrim': codigo_solicitacao_exame_siscrim,
                            'codigo_laudo': codigo_laudo}
            )

            # Insucesso. Servidor retorna mensagem de erro (exemplo: matricula incorreta)
            if (not sucesso):
                # Exibe mensagem de erro reportada pelo servidor e continua no loop
                print_erro()
                print("",msg_erro)
                print()
                continue

        except BaseException as e:
            # Provavel falha de comunicação
            print_falha_comunicacao()
            return False

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
        print("- Você não possui nenhum laudo para exame SAPI em andamento.")
        if pergunta_sim_nao("< Deseja criar um novo laudo"):
            criar_novo_laudo(matricula)
        # Irá ficar no loop
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
    print("- Consultando suas solicitações de exame SAPI WEB. Aguarde...")
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
        print("- No browser padrão foi invocada a página de criação de laudo no SisCrim.")
        print("- Caso a página não tenha sido aberta, acesse o SisCrim da forma tradicional.")
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

    GdadosGerais["data_hora_ultima_atualizacao_status"] = datetime.datetime.now().strftime('%H:%M:%S')

    # Verifica se o laudo é parcial, ou seja, se existem itens na solicitação de exame
    # que não fazem parte do laudo
    carregar_solicitacao_exame()

    return True


# Exibir informações sobre tarefa
# ----------------------------------------------------------------------
def dump_item():
    print("===============================================")

    var_dump(Gitens[Gicor])

    print("===============================================")


# Funções relacionada com movimentação nas tarefas
# ----------------------------------------------------------------------
def avancar_item():
    global Gicor

    if (Gicor < len(Gitens)):
        Gicor += 1


def recuar_item():
    global Gicor

    if (Gicor > 1):
        Gicor -= 1


def posicionar_item(n):
    global Gicor

    n = int(n)

    if (1 <= n <= len(Gitens)):
        Gicor = n


def obter_item_corrente():
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


# Recupera quesitos padrões selecionados pelo usuário
def obter_quesitos_padroes():

    # Recupera quesitos padrões
    while True:
        # 1) Pergunta parâmetros para determinação de quesitos repetidos
        print("- Na tela gráfica que foi aberta, informe os parâmetros para efetuar a busca de 'quesitos padrões'")
        # Obtem e autentica credencial de usuário (através de interface gráfica)
        # Retorna verdadeiro se autenticação foi efetuada
        # Cria dialogo para entrada de dados
        root = tkinter.Tk()
        dialogo = DialogoParametrosBuscaLaudo()
        root.geometry("600x350+300+300")
        root.mainloop()

        if len(dialogo.dados) == 0:
            print("- Nenhum parâmetro selecionado. Cancelando comando.")
            return (False, [], [])

        parametros=dialogo.dados

        solicitacao = texto('No mínimo',
                           parametros['quantidade_minima'],
                           'ocorrências entre',
                           parametros['data_inicial'],
                           ' e ', parametros['data_final'])

        # 2) Recuperar quesitos repetidos dos laudos passados
        print()
        print("- Agora será efetuado um acesso ao SAPI WEB para filtrar os quesitos, utilizando filtros informados:")
        print("=>", solicitacao)
        print("- Confirme se os parâmetros de busca acima estão ok.")
        if not prosseguir():
            return (False, [], [])

        parametros['unidade'] = obter_param_usuario('codigo_unidade_lotacao')
        # --- Por enquanto, vamos substituir a chamada por um valor já definido
        print("- Recuperando quesitos repetidos, para serem utilizados como quesitos padrões.")
        print("- Isto pode demorar ALGUNS MINUTOS e não haverá nenhum indicativo de progresso durante a busca. Aguarde...")
        print_log("Recuperando quesitos para",
                  "unidade:", parametros['unidade'],
                  "data_inicial:", parametros['data_inicial'],
                  "data_final:", parametros['data_final'],
                  "qtd_minima:", parametros['quantidade_minima'],
                  )
        set_http_timeout(5*60) # Amplia timeout, pois esta chamada pode demorar
        resultado = sapisrv_chamar_programa_sucesso_ok(
            "sapisrv_obter_quesitacao_padrao.php",
             {'unidade':         parametros['unidade'],
              'data_inicial':    parametros['data_inicial'],
              'data_final':      parametros['data_final'],
              'qtd_minima':      parametros['quantidade_minima']
              })
        reset_http_timeout() # Volta ao tempo normal

        # Separa em componentes do resultado
        quesitacoes=resultado['quesitacoes']
        print_log("Quantidade de laudos processados", resultado['qtd_laudos_processados'])
        print_log("Quantidade de laudos desprezados (erro de parse)", resultado['qtd_laudos_parse_erro'])


        # 3) Revisar os quesitos recuperados
        print("")
        qtd=len(quesitacoes)
        print_tela("- Foram processados:", resultado['qtd_laudos_processados'], "laudos")
        print_tela_log("- Com os parâmetros informados foram recuperados", qtd, "quesitos repetidos")
        # Ok, deu certo, finaliza while
        if qtd>0:
            break

        # Continua
        print_atencao()
        print("- Com os parâmetros informados não foi recuperado nenhum quesito")
        print("- Sugestão: Diminua a quantidade de repetições mínimas ou então amplie o período")
        continue



    # Tudo certo
    return (True, parametros, quesitacoes)



#-----------------------------------------------------------------------
# *aq : Adicionar quesitos
# ----------------------------------------------------------------------
def adicionar_quesitos():
    return console_executar_tratar_ctrc(funcao=_adicionar_quesitos)

def _adicionar_quesitos():

    # Cabeçalho
    cls()
    print_titulo("Adicionar quesitos para modelo de laudo SAPI da unidade",
                 obter_param_usuario('sigla_unidade_lotacao'))

    # Verifica se usuário tem direito de administrador
    if not obter_param_usuario("adm_sapi"):
        print("- ERRO: Para efetuar a configuração você precisa de direito de administrador no SAPI.")
        abrir_browser_wiki(Gwiki_sapi)
        return False

    if obter_param_usuario('fora_da_unidade_lotacao'):
        print_tela("- Operação reservada para administrador SAPI. Você não dispõe de direito de administrador do SAPI estando fora da sua unidade de lotação. Ver: ",Gwiki_sapi)
        return False

    # Informa arquivo de modelo atual
    # -----------------------------------
    print()
    print("Passo 1: Informe o arquivo que contém o modelo de laudo atual a sua unidade")
    print("---------------------------------------------------------------------------")
    print("- Informe o arquivo que contém o modelo de laudo ATUAL da sua unidade.")
    print("- Para garantir, é melhor baixar sempre a versão que está em vigor diretamente do Siscrim.")
    if pergunta_sim_nao("Você deseja baixar o modelo do SisCrim agora?", default="n"):
        abrir_browser_siscrim("/sistemas/criminalistica/modelo_usuario.php?acao=listar",
                              descricao_pagina="Administração do Sistema => Modelos de Usuário")

    print()
    print("- Na janela gráfica que foi aberta, selecione o arquivo .ODT correspondente")

    # Cria janela para seleção de laudo
    root = tkinter.Tk()
    j = JanelaTk(master=root)
    caminho_template = j.selecionar_arquivo([('ODT files', '*.odt')], titulo="Abra arquivo contendo o modelo SAPI do Laudo (.ODT), gerado no Siscrim")
    root.destroy()

    # Exibe arquivo selecionado
    if (caminho_template == ""):
        print()
        print("- Nenhum arquivo de modelo foi selecionado.")
        return

    print("- Arquivo de modelo selecionado:", caminho_template)

    # Nome do arquivo do arquivo que será criado
    pasta_atual, nome_arquivo_atual = os.path.split(caminho_template)
    nome_arquivo_saida = nome_arquivo_atual.replace(".odt", "_novo.odt")

    # Cria modelo da unidade, com quesitação retornada
    caminho_arquivo_saida_odt = criar_modelo_unidade(caminho_template, nome_arquivo_saida)
    if not caminho_arquivo_saida_odt:
        return False

    print()
    print("Passo 2: Recuperar quesitos padrões")
    print("-----------------------------------")
    (sucesso, parametros, quesitacoes) = obter_quesitos_padroes()
    if not sucesso:
        return False

    # Ajusta modelo da unidade, com quesitação retornada, adicionando os novos quesitos
    print("- Agora estes quesitos serão inseridos (se necessário) no modelo de laudo da sua unidade")
    espera_enter()
    sucesso = ajustar_modelo_unidade(caminho_arquivo_saida_odt, quesitacoes, parametros, adicionando=True)
    if sucesso:
        atualizar_modelo_siscrim()

    #
    return True


#-----------------------------------------------------------------------
# *gm : Gerar modelo de laudo SAPI para a Unidade
# ----------------------------------------------------------------------
def gerar_modelo_unidade():
    return console_executar_tratar_ctrc(funcao=_gerar_modelo_unidade)

def _gerar_modelo_unidade():

    # Cabeçalho
    cls()
    # kkkk
    print_titulo("Gerar modelo de laudo SAPI para unidade",
                 obter_param_usuario('sigla_unidade_lotacao'))

    # Instruções
    # --------------------------------------------------------------
    print("")
    print("A geração de um modelo SAPI consiste em duas etapas:")
    print("1) Será feita a leitura de um conjunto de laudos (laudos do último ano, por exemplo),")
    print("   e os quesitos repetidos serão considerados como quesitos padrões")
    print("2) Serão elaboradas respostas automáticas (padronizadas) para estes quesitos,")
    print("   criando um arquivo de modelo (.ODT) que deverá ser incluído nos modelos de laudo do SisCrim da sua unidade")
    print("- Posteriormente, você poderá efetuar customizações manuais, ajustando as respostas, definindo novas quesitações, etc")
    print()
    if not prosseguir():
        return False

    # Verifica se usuário tem direito de administrador
    if not obter_param_usuario("adm_sapi"):
        print("- ERRO: Para efetuar a configuração você precisa de direito de administrador no SAPI.")
        abrir_browser_wiki(Gwiki_sapi)
        return False

    if obter_param_usuario('fora_da_unidade_lotacao'):
        print_tela("- Operação reservada para administrador SAPI. Você não dispõe de direito de administrador do SAPI estando fora da sua unidade de lotação. Ver: ",Gwiki_sapi)
        return False

    # Cria arquivo de modelo para unidade
    # -----------------------------------
    # Recupera template geral (meta template)
    caminho_template = obter_template_laudo()
    # Nome do arquivo do arquivo que será criado
    sigla=str(obter_param_usuario('sigla_unidade_lotacao'))
    sigla=sigla.replace("SR/PF/", "")
    sigla=sigla.replace("/","_")
    sigla=sigla.replace("__","_")
    nome_arquivo_saida = "laudo_modelo_sapi_"+sigla+".odt"
    # Cria arquivo de destino
    caminho_arquivo_saida_odt = criar_modelo_unidade(caminho_template, nome_arquivo_saida)
    if not caminho_arquivo_saida_odt:
        return False


    print()
    print("Quesitos padrões")
    print("----------------")
    (sucesso, parametros, quesitacoes) = obter_quesitos_padroes()
    if not sucesso:
        return False


    # Ajusta modelo da unidade, com quesitação retornada
    print("- Agora será gerado o modelo de laudo da sua unidade")
    espera_enter()
    sucesso = ajustar_modelo_unidade(caminho_arquivo_saida_odt, quesitacoes, parametros)

    if sucesso:
       atualizar_modelo_siscrim()

    return True

# Baixa template do servidor
# Se obtiver sucesso, retorna o caminho para o template
# Caso contrário, retorna False
def obter_template_laudo():

    print_tela_log("- Recuperando template para geração de modelo de laudo SAPI")
    #
    # Adiciona .py no nome do programa
    nome_arquivo_template = "LAUDO_" + Gmodelo_versao_esperado + ".odt"

    # Efetua download do arquivo
    conteudo_arquivo = sapisrv_chamar_programa_sucesso_ok(
        programa="sapisrv_download.php",
        parametros={
            'arquivo': nome_arquivo_template,
            # O parâmetro abaixo faz com que a resposta retornada
            # seja apenas //dados//
            # Ou seja, não retorna a estrutura {sucesso, mensagem_erro, dados}
            # Neste caso isto foi necessário
            # pois a codificação JSON do arquivo ODT falhou
            'apenas_dados': 1
        })

    print_log("- Arquivo baixado com tamanho:", len(conteudo_arquivo))

    # Pasta em que será gravado o arquivo a atualização
    pasta_destino=get_parini('pasta_execucao')

    # Grava conteúdo do arquivo na pasta de destino
    caminho_template=os.path.join(pasta_destino,nome_arquivo_template)
    print_log("- Arquivo será gravado na pasta:", caminho_template)

    # Grava o arquivo recuperado
    try:
        # Se arquivo já existe, exclui para confirmar que não está aberto
        if os.path.isfile(caminho_template):
            os.remove(caminho_template)
            if os.path.isfile(caminho_template):
                print_tela_log("Não foi possível excluir arquivo:",caminho_template)
                return False

        # Grava o conteúdo baixado em tmp
        with open(caminho_template, 'wb') as novo_arquivo:
            novo_arquivo.write(conteudo_arquivo)

        print_log("Arquivo de template gravado em ", caminho_template)

    except BaseException as e:
        print_tela_log("[4434] Não foi possível gravar arquivo: ", e)
        return False

    return caminho_template


# ----------------------------------------------------------------------
# Diálogo para parametros de busca de laudos
# ----------------------------------------------------------------------
class DialogoParametrosBuscaLaudo(tkinter.Frame):

    def __init__(self):
        super().__init__()

        self.initUI()

        # Inicializa propriedadas da classe
        self.dados = dict()

    def initUI(self):

        self.master.title("Parâmetros para busca de laudo")
        self.pack()

        self.label_erro_validacao=ttk.Label(self, text="").pack()


        # Quantidade mínima
        ttk.Label(self, text="Informe os parâmetros para seleção de quesitos padrões",font=('bold')).pack(anchor=tkinter.W)
        ttk.Label(self, text="").pack(anchor=tkinter.W)

        # Quantidade mínima
        ttk.Label(self, text="Quantidade mínima que um quesito deve se repetir").pack(anchor=tkinter.W)
        ttk.Label(self, text="para ser considerado padrão:").pack(anchor=tkinter.W)
        self.entry_quantidade_minima = ttk.Entry(self,
                                                 validate='focusout',
                                                 validatecommand=self.validar_quantidade_minima)
        self.entry_quantidade_minima.insert(tkinter.END, "3")
        self.entry_quantidade_minima.pack(anchor=tkinter.W)


        # Data de início
        ttk.Label(self, text="").pack(anchor=tkinter.W)
        ttk.Label(self, text="Data inicial de emissão dos laudos a serem considerados:").pack(anchor=tkinter.W)
        self.entry_data_inicial = ttk.Entry(self, validate='focusout', validatecommand=self.validar_data_inicial)
        self.entry_data_inicial.insert(tkinter.END, "01/01/2017")
        self.entry_data_inicial.pack(anchor=tkinter.W)

        # Data Final
        ttk.Label(self, text="").pack(anchor=tkinter.W)
        ttk.Label(self, text="Data final do período dos laudos a serem considerados:").pack(anchor=tkinter.W)
        self.entry_data_final = ttk.Entry(self, validate='focusout', validatecommand=self.validar_data_final)
        default_data_final=datetime.datetime.now().strftime('%d/%m/%Y')
        #if ambiente_desenvolvimento():
        #    default_data_final = '30/06/2017'
        self.entry_data_final.insert(tkinter.END, default_data_final)
        self.entry_data_final.pack(anchor=tkinter.W)

        # Botão OK
        ttk.Label(self, text="").pack(anchor=tkinter.W)
        ttk.Button(self, text='OK', command=self.validar).pack(anchor=tkinter.W)

        self.master.bind('<Return>', self.validar)
        self.focus_force()


    def validar_quantidade_minima(self, dummy=0):

        # Valida quantidade mínima
        valor = str(self.entry_quantidade_minima.get())
        if not valor.isdigit():
            messagebox.showerror("Valor inválido", "Entre com um número inteiro")
            self.entry_quantidade_minima.focus_set()
            return False

        # Tudo certo
        return True

    def validar_data_inicial(self, dummy=0):

        valor=str(self.entry_data_inicial.get())
        if not validar_data(valor):
            messagebox.showerror("Valor inválido", "Entre com data no valor dd/mm/aaaa")
            self.entry_data_inicial.focus_set()
            return False

        # Tudo certo
        return True

    def validar_data_final(self, dummy=0):

        valor=str(self.entry_data_final.get())
        if not validar_data(valor):
            messagebox.showerror("Valor inválido", "Entre com data no valor dd/mm/aaaa")
            self.entry_data_final.focus_set()
            return False

        # Verifica se data final é maior que data inicial
        d_inicial = time.strptime(self.entry_data_inicial.get(), "%d/%m/%Y")
        d_final   = time.strptime(self.entry_data_final.get(), "%d/%m/%Y")

        if (d_final < d_inicial):
            messagebox.showerror("Valor inválido", "A data incial tem que ser menor que a data final")
            self.entry_data_inicial.focus_set()
            return False


        # Tudo certo
        return True


    def validar(self, dummy=0):

        # Executa validação de todos os campos
        if self.validar_quantidade_minima(self) and self.validar_data_inicial(self) and self.validar_data_final(self):

            # Armazena valores
            self.dados['quantidade_minima']=self.entry_quantidade_minima.get()
            self.dados['data_inicial']=self.entry_data_inicial.get()
            self.dados['data_final']=self.entry_data_final.get()

            # Tudo certo
            self.exit()
            return
        else:
            # Não precisa fazer nada
            # A rotinas de validação já deram as mensagens e pegar o foco
            return

    def exit(self):
        self.master.destroy()

# Obtem e autentica credencial de usuário (através de interface gráfica)
# Retorna verdadeiro se autenticação foi efetuada
def obter_parametros_busca_laudo():

    # Cria dialogo para entrada de dados
    root = tkinter.Tk()
    dialogo = DialogoParametrosBuscaLaudo()
    root.geometry("600x350+300+300")
    root.mainloop()

    sucesso=True
    if len(dialogo.dados)==0:
        sucesso=False

    return (sucesso, dialogo.dados)





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
    print("- Aguarde conexão com servidor...")
    print()

    # Inicialização de sapilib
    # -----------------------------------------------------------------------------------------------------------------
    print_log('Iniciando ', Gprograma, ' - ', Gversao)
    sapisrv_inicializar_ok(Gprograma, Gversao, auto_atualizar=True)

    # Efetua login no SAPi
    if not login_sapi():
        return False

    # Modo de configuração (acionado com --config) utilizado pelo administrador SAPI
    if modo_config():
        # Entra em modo administração
        execucao_admin()
    else:
        # Entra em modo usuário
        execucao_usuario()

    # Finaliza programa
    # Encerrando conexão com storage
    print()
    desconectar_todos_storages()

    # Finaliza
    print()
    print("FIM SAPI Laudo - Versão: ", Gversao)

# Modo administração
# Permitir criar modelo de laudo, configurar, etc
def execucao_admin():

    # Tem que ter direito de administrador.
    if not usuario_possui_direito_administrador():
        print("- Execução finalizada.")
        return False

    print()
    print("-"*100)
    print("- Você entrou em modo ADMINISTRADOR SAPI para a unidade", obter_param_usuario('sigla_unidade_lotacao'))
    print("- Escolha o comando a ser executado.")
    print("-"*100)
    print("- Caso esta seja a primeira execução, utilize o comando *GM para gerar o modelo de laudo SAPI da sua unidade")


    # Processamento de comandos
    # ---------------------------
    while (True):

        (comando, argumento) = console_receber_comando(Gmenu_admin)
        if comando is None:
            continue

        if comando == '':
            # Se usuário simplemeste der um <ENTER>, ignora
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
        # Comandos gerais
        if (comando == '*gm'):
            gerar_modelo_unidade()
            continue
        elif (comando == '*vm'):
            validacao_modelo_sapi()
            continue
        elif (comando == '*aq'):
            adicionar_quesitos()
            continue


# Modo usuário
def execucao_usuario():

    # Obtem laudo a ser processado
    if not obter_laudo_ok():
        # Se usuário interromper seleção de itens
        print("- Execução finalizada.")
        return

    # Processamento
    # ---------------------------
    exibir_situacao()

    # Processamento de comandos
    # ---------------------------
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
            dump_item()
            continue
        elif (comando == '*si'):
            exibir_situacao_item_corrente()
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
        elif (comando == '*cl'):
            abrir_browser_siscrim_documento(GdadosGerais["codigo_laudo"])
            continue
        elif (comando == '*ml'):
            abrir_browser_siscrim_modelo_usuario(GdadosGerais["codigo_laudo"])
            print("- Gere um modelo de laudo com padrão SAPI.")
            continue
        elif (comando == '*gl'):
            gerar_laudo()
            continue

            # Loop de comando



# -------------------------------------------------------
# ----------------- Para testes -------------------------


# Apenas para teste.
Gteste_texto_solicitacao_exame = ''''
  SERVIÇO PÚBLICO FEDERAL
                            MJ - DEPARTAMENTO DE POLÍCIA FEDERAL
                       SUPERINTENDÊNCIA REGIONAL NO ESTADO DO PARANÁ
              DRCOR - DELEGACIA REGIONAL DE COMBATE AO CRIME ORGANIZADO
                             GT/LAVA JATO/DRCOR/SR/DPF/PR


Memorando n° 6722/2015 - IPL 1315/14 SR/DPF/PR
                                                                                Em 26 de junho de 2015.


                                                               2691/15-SETEC/PR               |D15-1841



                                                             Material
                                                              3039/15   telefone celular,*

Ao Senhor Chefe do SETEC/SR/DPF/PR.                                       &r?x
Assunto: Solicita perícia - espelhamento BLACKBERRY o«t«
                  r            r                             Memorando 6722/15-SR/DPF/PR

Referência: MARCELO BAHIA ODEBRECHT             - CPF 487.956.235-15


                  A fim de instruir os autos do      Inquérito Policial n° IPL        1315/14-SR/DPF/PR
(Operação LAVA JATO 14), Equipe SP 06 - alvo MARCELO BAHIA ODEBRECHT, Endereço: Rua
Joaquim Cândido de Azevedo Marques, 750, casa 319, lote 19, quadra 3, Jardim Pignatari, São
Paulo/SP, no dia 19.06.2015, por força do Mandado de Busca e Apreensão n° 700000796211 -
Pedido de Busca e Apreensão Criminal n. 5024251-72.2015.4.04.7000/PR, expedido pelo MM. Juiz
Federal da 13a Vara Federal da Subseção Judiciária de Curitiba/PR, encaminho a Vossa Senhoria
O(s) (telefone(s) celulares)) relacionadO(s) no Auto de Apreensão N° 1315/15, cópia anexa,    solicitando
a elaboração de Laudo de Exame em Telefone Celular com respectiva duplicação do espelho
(destino) para fins de registro neste Grupo de Trabalho Lava Jato, devendo 0S(aS) senhores(aS)
          designados(as) responderem aos seguintes quesitos:

                                                Material

  ITEM          ITEM                                        DESCRIÇÃO
          ARRECADAÇÃO

     1.           02               UM CELULAR      BLACKBERRY - MOD.               RFL111LW - IMEI
                                   356112051170465 - COR PRETA (ENTREGUE POR ISABELA
                                   ALVAREZ)

     2.           10               UM   CELULAR    BLACKBERRY - MOD.               RCN72UW - IMEI
                                   354260040446975 - COR BRANCO (QUARTO DE ESTUDO
                                   DE MARCELO ODEBRECHT)

     3.           11               UM   CELULAR    BLACKBERRY -            MOD.     RST71UW -      IMEI
                                   980041002309076     -   COR    PRETA/PRATA            (QUARTO    DE
                                   ESTUDO DE MARCELO ODEBRECHT)

     4.           18               UM   CELULAR    BLACKBERRY - MOD.               RCN70UW - IMEI
                                   352060042645216 - COR BRANCA (QUARTO DE ESTUDO
                                   DE MARCELO ODEBRECHT)




                                                                                                          1/2
 1   Celular   marca
                       BLfiCKBERRY
                       BLfiCKBERRY
01   Celular   marca
                       BLPlCKBERRYAcom capa;
01   Celular   marca
                       BLfiCKBERRY de cor preta;
01   Celular   marca
01   Celular   marca
                       BLfiCKBERRY! de cor preta:
LACRE: 3107915.

 26/06/15 17:10
                                        SERVIÇO PÚBLICO FEDERAL
                                 MJ - DEPARTAMENTO DE POLÍCIA FEDERAL
                            SUPERINTENDÊNCIA REGIONAL NO ESTADO DO PARANÁ
                 DRCOR - DELEGACIA REGIONAL DE COMBATE AO CRIME ORGANIZADO
                                        GT/LAVA JATO/DRCOR/SR/DPF/PR
       5.              18             UM     CELULAR    BLACKBERRY       -   MOD.   RCN72UW-        IMEI
                                      354260040454524 - COR BRANCA (DANIFICADO) (QUARTO
                                      DE ESTUDO DE MARCELO ODEBRECHT)



                      Visando a agilização das análises e considerando que parte do material

será        encaminhado       a   perícia,    solicitamos     que    o   espelhamento        seja     feito

excepcionalmente em duas vias de iaual teor (mídias separadas).


                 1.    Qual a natureza e características dO(S) material(ais) submetido^) a exame?
             2. Quais os números telefônicos de habilitação associados?
             3. Há registros correspondentes às chamadas telefônicas recebidas, efetuadas e
não atendidas? Caso positivo, relacionar.
             4. Há registros constantes da(S) agenda^) telefônica(S)? Caso positivo, relacionar.
             5. Existem registros referentes a mensagens SMS? Caso positivo, relacionar.
             6. Há informações apagadas que puderam ser recuperadas?
             7. Extrair os dados e metadados relativos às comunicações eletrônicas (por
exemplo WhatsApp), fotos e vídeos eventualmente armazenadas nos dispositivos informáticos,
devendo a apresentação destes dados ser em formato de texto legível e navegável.
                 8.    É possível, a partir dos dados constantes no objeto de exame, identificar o
usuário do aparelho celular?
                 9.    É possível realizar despejo (dump) físico da memória interna dos dispositivos?
               10. Em caso positivo, é possível a recuperação de mensagens associadas ao
aplicativo BlackBerry Messengeft
               11. Outros dados julgados úteis.



                      Atenciosamente,




                                         Delegado^té Polícia Federal
                                              Matrícula n° 8.190




                                                                                                           2/2
                                                 SERVIÇO PUBLICO FEDERAL
                                        MJ - DEPARTAMENTO DE POLÍCIA FEDERAL
                                        SUPERINTENDÊNCIA REGIONAL NO PARANÁ
                              DELEGACIA REGIONAL DE COMBATE AO CRIME ORGANIZADO
                                            GT/LAVA JATO/DRCOR/SR/DPF/PR

                                         OPERAÇÃO LA VA JATO 14



                                                  IPL 1315/2014

                                                    EQUIPE SP 06



                                                       ODEBRECHT


                             AUTO DE APREENSÃO CELULAR
                                                       N° 1317/15

Pedido de Busca e Apreensão n° 5024251 -72.2015.4.04.7000/PR

Mandado de Busca e Apreensão n.° 700000796211


Ao(s) 25 dia(s) do mês de junho de 2015, nesta Superintendência de Policia Federal, em
Curitiba/PR, onde se encontrava EDUARDO MAUAT DA SILVA, Delegado de Policia
Federal, mat. 8.190, na presença das testemunhas WILIGTON GABRIEL PEREIRA, J
Agente de Polícia Federal, matrícula 9342, lotado na DPF/PGZ/PR e VANESSA NITTA, <-
Agente de Polícia Federal, matrícula 10753, lotado na DPF/CHI/RS e em exercício nesta
SR/DPF/pRi pe|0S mesmos foi determinado que se tornasse efetiva a apreensão, na
Um Ia    Ua   l_cl,   tiu   incuc/imi   auaiAu   uuo     m^w.


                                                         Material
          TEM ARRECADAÇÃO                                            DESCRIÇÃO
 ITEM

    1.                  01                 UM    CELULAR    IPHONE,  MOD.   A1457, IMEI:
                                           352049064551592 - COR PRETA/CINZA (QUARTO DE
                                            MARCELO ODEBRECHT)                                                    \
                        01                  UM CELULAR BLACKBERRY - MOD. RFL111LW - IMbi
    2.
                                           356112051170465 - COR PRETA (ENTREGUE POR
                                            ISABELA ALVAREZ)
    3.                  05                  UM      CELULAR      NOKIA         -   MOD.   6555   -   IMbi
                                            357693/01/01081313             -       COR    PRETA/PRATA
                                            (ESCRITÓRIO DE MARCELO ODEBRECHT)

                                                                                                            1/3
                                SERVIÇO PUBLICO FEDERAL
                          MJ - DEPARTAMENTO DE POLÍCIA FEDERAL
                          SUPERINTENDÊNCIA REGIONAL NO PARANÁ
                    DELEGACIA REGIONAL DE COMBATE AO CRIME ORGANIZADO
                               GT/LAVA JATO/DRCOR/SR/DPF/PR

                           OPERAÇÃO LA VA JA TO 14

  4.          10             UM CELULAR BLACKBERRY - MOD. RCN72UW - IMEI
                             354260040446975 - COR BRANCO (QUARTO DE
                             ESTUDO DE MARCELO ODEBRECHT)
  5.          11             UM CELULAR BLACKBERRY - MOD. RST71UW - IMEI
                             980041002309076 - COR PRETA/PRATA (QUARTO DE
                             ESTUDO DE MARCELO ODEBRECHT)
   6.         15             UM   CELULAR    ZTE  -  MOD.    Z432 -  IMEI
                             863487024185634 - NR 305.299.5725 COR PRETA
                             (QUARTO DO CASAL DE MARCELO ODEBRECHT)
   7.         15             UM   CELULAR    ZTE  -   MOD.   Z432 -  IMEI
                             86348702366078 - COR PRETA (QUARTO DO CASAL
                             DE MARCELO ODEBRECHT)
   8.         15             UM   CELULAR    ZTE   -  MOD.    Z432   -  IMEI
                             863487024168614 - NR 305.301.2994 - COR PRETA
                             (QUARTO DO CASAL DE MARCELO ODEBRECHT)
   9.         15             UM   CELULAR    ZTE   -  MOD.    Z432   -   IMEI
                             863487024169232 - NR 305.298.9116 - COR PRETA
                             (QUARTO DO CASAL DE MARCELO ODEBRECHT)
                             UM    CELULAR    IPHONE,   MOD.   A1332,   IMEI:
   10         15
                             012839005033920 - COR     PRETA    (QUARTO    DE
                             MARCELO ODEBRECHT)
   11         18             UM    CELULAR    IPHONE,   MOD.   A1428,  IMEI:
                             013423004159710 - COR PRETA/CINZA - DANIFICADO
                             - CONTENDO UM PAPEL COM LEMBRETE - NR 25629
                             (QUARTO DE ESTUDO - MARCELO ODEBRECHT)
   12          18            UM CELULAR BLACKBERRY - MOD. RCN70UW - IMEI
                             352060042645216 - COR BRANCA (QUARTO DE
                              ESTUDO DE MARCELO ODEBRECHT)
   13          18
                              UM CELULAR BLACKBERRY - MOD. RCN72UW- IMEI
                              354260040454524 - COR BRANCA (DANIFICADO)
                              (QUARTO DE ESTUDO DE MARCELO ODEBRECHT)
Os referidos materiais foram arrecadados na residência de MARCELO BAHIA
ODEBRECHT, Endereço: Rua Joaquim Cândido de Azevedo Marques, 750, casa 319, lote
19 quadra 3, Jardim Pignatari, São Paulo/SP, no dia 19.06.2015, por força do Mandado
de'Busca e Apreensão n° 700000796211 - Pedido de Busca e Apreensão Criminal n
5024251-72 2015.4.04.7000/PR, expedido pelo MM. Juiz Federal da 13a Vara Federal da
Subseção Judiciária de Curitiba/PR. Nada mais havendo, determinou a autoridade policial
o encerramento do presente auto, o qual depois de lido e achado conforme, vai assinado

                                                                                   V
                                   SERVIÇO PUBLICO FEDERAL
                           MJ - DEPARTAMENTO DE POLÍCIA FEDERAL
                           SUPERINTENDÊNCIA REGIONAL NO PARANÁ
                    DELEGACIA REGIONAL DE COMBATE AO CRIME ORGANIZADO
                                 GT/LAVA JATO/DRCOR/SR/DPF/PR

                                OPERAÇÃO LAVA JATO 14

por todos, inclusive pelos advogados VÍTOR AUGUSTO/SPRADA ROSSETIM, OAB/PR
70386, tel. (41) 325C       e CARLOS EDUARDO MAYE RE TREGLIA, OAB/PR 37525, e
por mim. Eu,                     Maurício Fjrmin0 Sobrinho, Escrivão de Polícia Federal,
matrícula 7580, que ft1avfe\.



AUTORIDADE POLICIAL:


TESTEMUNHA :


TESTEMUNHA:
               \


ADVOGADO: \

ADVOGADO:
'''


Gteste_texto_solicitacao_exame_inedita = ''''
  SERVIÇO PÚBLICO FEDERAL
                            MJ - DEPARTAMENTO DE POLÍCIA FEDERAL
                       SUPERINTENDÊNCIA REGIONAL NO ESTADO DO PARANÁ
              DRCOR - DELEGACIA REGIONAL DE COMBATE AO CRIME ORGANIZADO
                             GT/LAVA JATO/DRCOR/SR/DPF/PR


Memorando n° 6722/2015 - IPL 1315/14 SR/DPF/PR
                                                                                Em 26 de junho de 2015.


                                                               2691/15-SETEC/PR               |D15-1841



                                                             Material
                                                              3039/15   telefone celular,*

Ao Senhor Chefe do SETEC/SR/DPF/PR.                                       &r?x
Assunto: Solicita perícia - espelhamento BLACKBERRY o«t«
                  r            r                             Memorando 6722/15-SR/DPF/PR

Referência: MARCELO BAHIA ODEBRECHT             - CPF 487.956.235-15


                  A fim de instruir os autos do      Inquérito Policial n° IPL        1315/14-SR/DPF/PR
(Operação LAVA JATO 14), Equipe SP 06 - alvo MARCELO BAHIA ODEBRECHT, Endereço: Rua
Joaquim Cândido de Azevedo Marques, 750, casa 319, lote 19, quadra 3, Jardim Pignatari, São
Paulo/SP, no dia 19.06.2015, por força do Mandado de Busca e Apreensão n° 700000796211 -
Pedido de Busca e Apreensão Criminal n. 5024251-72.2015.4.04.7000/PR, expedido pelo MM. Juiz
Federal da 13a Vara Federal da Subseção Judiciária de Curitiba/PR, encaminho a Vossa Senhoria
O(s) (telefone(s) celulares)) relacionadO(s) no Auto de Apreensão N° 1315/15, cópia anexa,    solicitando
a elaboração de Laudo de Exame em Telefone Celular com respectiva duplicação do espelho
(destino) para fins de registro neste Grupo de Trabalho Lava Jato, devendo 0S(aS) senhores(aS)
          designados(as) responderem aos seguintes quesitos:

                                                Material

  ITEM          ITEM                                        DESCRIÇÃO
          ARRECADAÇÃO

     1.           02               UM CELULAR      BLACKBERRY - MOD.               RFL111LW - IMEI
                                   356112051170465 - COR PRETA (ENTREGUE POR ISABELA
                                   ALVAREZ)

     2.           10               UM   CELULAR    BLACKBERRY - MOD.               RCN72UW - IMEI
                                   354260040446975 - COR BRANCO (QUARTO DE ESTUDO
                                   DE MARCELO ODEBRECHT)

     3.           11               UM   CELULAR    BLACKBERRY -            MOD.     RST71UW -      IMEI
                                   980041002309076     -   COR    PRETA/PRATA            (QUARTO    DE
                                   ESTUDO DE MARCELO ODEBRECHT)

     4.           18               UM   CELULAR    BLACKBERRY - MOD.               RCN70UW - IMEI
                                   352060042645216 - COR BRANCA (QUARTO DE ESTUDO
                                   DE MARCELO ODEBRECHT)




                                                                                                          1/2
 1   Celular   marca
                       BLfiCKBERRY
                       BLfiCKBERRY
01   Celular   marca
                       BLPlCKBERRYAcom capa;
01   Celular   marca
                       BLfiCKBERRY de cor preta;
01   Celular   marca
01   Celular   marca
                       BLfiCKBERRY! de cor preta:
LACRE: 3107915.

 26/06/15 17:10
                                        SERVIÇO PÚBLICO FEDERAL
                                 MJ - DEPARTAMENTO DE POLÍCIA FEDERAL
                            SUPERINTENDÊNCIA REGIONAL NO ESTADO DO PARANÁ
                 DRCOR - DELEGACIA REGIONAL DE COMBATE AO CRIME ORGANIZADO
                                        GT/LAVA JATO/DRCOR/SR/DPF/PR
       5.              18             UM     CELULAR    BLACKBERRY       -   MOD.   RCN72UW-        IMEI
                                      354260040454524 - COR BRANCA (DANIFICADO) (QUARTO
                                      DE ESTUDO DE MARCELO ODEBRECHT)



                      Visando a agilização das análises e considerando que parte do material

será        encaminhado       a   perícia,    solicitamos     que    o   espelhamento        seja     feito

excepcionalmente em duas vias de iaual teor (mídias separadas).


 1. Qual a natureza e características do aparelho de telefone celular e chip submetido a exame?
 2. Qual o número habilitado no aparelho submetido a exame?
 3. Quais os números de telefone, datas e horas constantes dos registros das últimas ligações efetuadas e recebidas por tal aparelho?
 4. Quais os nomes e números de telefone constantes da agenda telefônica de tal aparelho/chip?'
 5. Quais os arquivos existentes e sua descrição (mensagens, etc) no aparelho e chip?
 6. Outros dados julgados úteis.

                      Atenciosamente,




                                         Delegado^té Polícia Federal
                                              Matrícula n° 8.190




                                                                                                           2/2
                                                 SERVIÇO PUBLICO FEDERAL
                                        MJ - DEPARTAMENTO DE POLÍCIA FEDERAL
                                        SUPERINTENDÊNCIA REGIONAL NO PARANÁ
                              DELEGACIA REGIONAL DE COMBATE AO CRIME ORGANIZADO
                                            GT/LAVA JATO/DRCOR/SR/DPF/PR

                                         OPERAÇÃO LA VA JATO 14



                                                  IPL 1315/2014

                                                    EQUIPE SP 06



                                                       ODEBRECHT


                             AUTO DE APREENSÃO CELULAR
                                                       N° 1317/15

Pedido de Busca e Apreensão n° 5024251 -72.2015.4.04.7000/PR

Mandado de Busca e Apreensão n.° 700000796211


Ao(s) 25 dia(s) do mês de junho de 2015, nesta Superintendência de Policia Federal, em
Curitiba/PR, onde se encontrava EDUARDO MAUAT DA SILVA, Delegado de Policia
Federal, mat. 8.190, na presença das testemunhas WILIGTON GABRIEL PEREIRA, J
Agente de Polícia Federal, matrícula 9342, lotado na DPF/PGZ/PR e VANESSA NITTA, <-
Agente de Polícia Federal, matrícula 10753, lotado na DPF/CHI/RS e em exercício nesta
SR/DPF/pRi pe|0S mesmos foi determinado que se tornasse efetiva a apreensão, na
Um Ia    Ua   l_cl,   tiu   incuc/imi   auaiAu   uuo     m^w.


                                                         Material
          TEM ARRECADAÇÃO                                            DESCRIÇÃO
 ITEM

    1.                  01                 UM    CELULAR    IPHONE,  MOD.   A1457, IMEI:
                                           352049064551592 - COR PRETA/CINZA (QUARTO DE
                                            MARCELO ODEBRECHT)                                                    \
                        01                  UM CELULAR BLACKBERRY - MOD. RFL111LW - IMbi
    2.
                                           356112051170465 - COR PRETA (ENTREGUE POR
                                            ISABELA ALVAREZ)
    3.                  05                  UM      CELULAR      NOKIA         -   MOD.   6555   -   IMbi
                                            357693/01/01081313             -       COR    PRETA/PRATA
                                            (ESCRITÓRIO DE MARCELO ODEBRECHT)

                                                                                                            1/3
                                SERVIÇO PUBLICO FEDERAL
                          MJ - DEPARTAMENTO DE POLÍCIA FEDERAL
                          SUPERINTENDÊNCIA REGIONAL NO PARANÁ
                    DELEGACIA REGIONAL DE COMBATE AO CRIME ORGANIZADO
                               GT/LAVA JATO/DRCOR/SR/DPF/PR

                           OPERAÇÃO LA VA JA TO 14

  4.          10             UM CELULAR BLACKBERRY - MOD. RCN72UW - IMEI
                             354260040446975 - COR BRANCO (QUARTO DE
                             ESTUDO DE MARCELO ODEBRECHT)
  5.          11             UM CELULAR BLACKBERRY - MOD. RST71UW - IMEI
                             980041002309076 - COR PRETA/PRATA (QUARTO DE
                             ESTUDO DE MARCELO ODEBRECHT)
   6.         15             UM   CELULAR    ZTE  -  MOD.    Z432 -  IMEI
                             863487024185634 - NR 305.299.5725 COR PRETA
                             (QUARTO DO CASAL DE MARCELO ODEBRECHT)
   7.         15             UM   CELULAR    ZTE  -   MOD.   Z432 -  IMEI
                             86348702366078 - COR PRETA (QUARTO DO CASAL
                             DE MARCELO ODEBRECHT)
   8.         15             UM   CELULAR    ZTE   -  MOD.    Z432   -  IMEI
                             863487024168614 - NR 305.301.2994 - COR PRETA
                             (QUARTO DO CASAL DE MARCELO ODEBRECHT)
   9.         15             UM   CELULAR    ZTE   -  MOD.    Z432   -   IMEI
                             863487024169232 - NR 305.298.9116 - COR PRETA
                             (QUARTO DO CASAL DE MARCELO ODEBRECHT)
                             UM    CELULAR    IPHONE,   MOD.   A1332,   IMEI:
   10         15
                             012839005033920 - COR     PRETA    (QUARTO    DE
                             MARCELO ODEBRECHT)
   11         18             UM    CELULAR    IPHONE,   MOD.   A1428,  IMEI:
                             013423004159710 - COR PRETA/CINZA - DANIFICADO
                             - CONTENDO UM PAPEL COM LEMBRETE - NR 25629
                             (QUARTO DE ESTUDO - MARCELO ODEBRECHT)
   12          18            UM CELULAR BLACKBERRY - MOD. RCN70UW - IMEI
                             352060042645216 - COR BRANCA (QUARTO DE
                              ESTUDO DE MARCELO ODEBRECHT)
   13          18
                              UM CELULAR BLACKBERRY - MOD. RCN72UW- IMEI
                              354260040454524 - COR BRANCA (DANIFICADO)
                              (QUARTO DE ESTUDO DE MARCELO ODEBRECHT)
Os referidos materiais foram arrecadados na residência de MARCELO BAHIA
ODEBRECHT, Endereço: Rua Joaquim Cândido de Azevedo Marques, 750, casa 319, lote
19 quadra 3, Jardim Pignatari, São Paulo/SP, no dia 19.06.2015, por força do Mandado
de'Busca e Apreensão n° 700000796211 - Pedido de Busca e Apreensão Criminal n
5024251-72 2015.4.04.7000/PR, expedido pelo MM. Juiz Federal da 13a Vara Federal da
Subseção Judiciária de Curitiba/PR. Nada mais havendo, determinou a autoridade policial
o encerramento do presente auto, o qual depois de lido e achado conforme, vai assinado

                                                                                   V
                                   SERVIÇO PUBLICO FEDERAL
                           MJ - DEPARTAMENTO DE POLÍCIA FEDERAL
                           SUPERINTENDÊNCIA REGIONAL NO PARANÁ
                    DELEGACIA REGIONAL DE COMBATE AO CRIME ORGANIZADO
                                 GT/LAVA JATO/DRCOR/SR/DPF/PR

                                OPERAÇÃO LAVA JATO 14

por todos, inclusive pelos advogados VÍTOR AUGUSTO/SPRADA ROSSETIM, OAB/PR
70386, tel. (41) 325C       e CARLOS EDUARDO MAYE RE TREGLIA, OAB/PR 37525, e
por mim. Eu,                     Maurício Fjrmin0 Sobrinho, Escrivão de Polícia Federal,
matrícula 7580, que ft1avfe\.



AUTORIDADE POLICIAL:


TESTEMUNHA :


TESTEMUNHA:
               \


ADVOGADO: \

ADVOGADO:
'''



# ==================================================================================================================
# Identifica a quesitação utilizada em um laudo
# ==================================================================================================================

# Gera laudo
# ----------------------------------------------------------------------------------------------------------------------
def sistema_escolhe_quesitacao(quesitos_respostas):

    # Recupera texto da solicitação de exame
    # TODO
    texto_solicitacao_exame = ""

    # Efetuar comparação do texto da solicitação de exame com o texto
    # Retona a lista de prováveis quesitações
    # kkkkk

    var_dump(quesitos_respostas)
    die('ponto3432')

def conta_hits(quesitacao, texto_solicitacao):

    var_dump(quesitacao)
    print()
    #die('ponto3180')
    #quesitos=quesitacao.split('?')
    #var_dump(quesitos)
    #die('ponto3181')



def debug_odt():
    # Debug de problemas no XML do ODT
    # Quando for pegar o texto "problemático", remover todas os prefixos
    # Ou seja, um tag como <text:p tem que ser colocado aqui como <p
    # Caso contrário, tem que definir o namespace...
    xml_string = '''<?xml version="1.0"?>
    <p style-name="P373">
       <soft-page-break/># Abaixo estão as definições de blocos que substituirão alguns componentes
       <span style-name="T350">referenciados </span>
       acima.
    </p>
    '''

    # odt_raiz = xml.etree.ElementTree.fromstring(xml_string)
    # x = odt_obtem_texto_recursivo(odt_raiz)
    # var_dump(x)
    # die('ponto3856')





# ----------------------------------------------------------------------------------------------------------------------
# Recebe o arquivo de entrada (modelo), sendo este um arquivo odt gerado a partir de um modelo SAPI no sisCrim.
# Gera um novo arquivo odt, substituindo os elementos sapi por dados coletados durante as tarefas sapi executadas.
# Retorna o caminho para o arquivo de saída
# ----------------------------------------------------------------------------------------------------------------------
def criar_modelo_unidade(caminho_arquivo_entrada_odt, nome_arquivo_saida):
    print_log("- Arquivo base para criação de novo modelo:", caminho_arquivo_entrada_odt)

    # Verifica se arquivo tem extensão odt
    if (".odt" not in caminho_arquivo_entrada_odt.lower()):
        print_tela_log("- ERRO interno [5986]: Arquivo de TEMPLATE", caminho_arquivo_entrada_odt, "não possui extensão .odt")
        return False

    # ---------------------------------------------------------------------------------------------------
    # Verifica se o arquivo de modelo da unidade pode ser criado
    # ---------------------------------------------------------------------------------------------------
    pasta_entrada, nome_arquivo_entrada = os.path.split(caminho_arquivo_entrada_odt)

    caminho_arquivo_saida_odt = os.path.join(pasta_entrada, nome_arquivo_saida)

    print_tela_log("- Novo arquivo de modelo será gravado em:", caminho_arquivo_saida_odt)
    if os.path.isfile(caminho_arquivo_saida_odt):
        print_atencao()
        print("- Arquivo de modelo já existe")
        print("- Se você continuar, este arquivo será sobreescrito")
        if not prosseguir():
            print("- Operação cancelada pelo usuário.")
            return False
    try:
        # Tenta copiar arquivo
        shutil.copyfile(caminho_arquivo_entrada_odt, caminho_arquivo_saida_odt)
    except BaseException as e:
        print_tela_log("- ERRO na criação do arquivo:", caminho_arquivo_saida_odt, "=>", str(e))
        print_tela_log("- Verifique se arquivo não está aberto, ou se existe alguma outra condição que possa estar impedindo a gravação")
        return None

    return caminho_arquivo_saida_odt


#
def ajustar_modelo_unidade(caminho_arquivo_odt, quesitacoes, parametros, adicionando=False):

    # Valida arquivo de modelo
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print_titulo("Ajustando modelo")
    print()
    print("a) Validação de arquivo de template")
    print("-----------------------------------")
    if not carrega_valida_modelo(caminho_arquivo_odt, template=True):
        print("- Validação de modelo falhou")
        return False

    # ------------------------------------------------------------------------------------------------------------------
    # Geração de tabela de quesitações
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("b) Montagem de tabelas de quesitações padrões")
    print("---------------------------------------------")

    # Tabela de quesitações
    # ---------------------------
    tabela_quesitacoes = Gmod_tabelas['tabela_quesitacoes']

    # Isola linha de modelo da tabela de materiais
    tr_linhas_quesitos = tabela_quesitacoes.findall('table:table-row', Gxml_ns)
    tr_modelo_quesito = tr_linhas_quesitos[0]

    #print()
    #odt_dump(tr_modelo)

    tab_quesitacoes = Godt_filho_para_pai_map[tr_modelo_quesito]

    # Insere no início da tabela, após linha de modelo de quesitação
    #pos = odt_determina_posicao_pai_filho(tab_quesitacoes, tr_modelo_quesito)
    # posicao_inserir_tab_quesitacoes = pos + 1

    # Insere no final da tabela, após ultima linha de quesitação atual
    pos = odt_determina_posicao_pai_filho(tab_quesitacoes, tr_linhas_quesitos[-1])
    posicao_inserir_tab_quesitacoes = pos + 1

    # Recupera campos variáveis da linha de modelo da tabela de materiais
    # ------------------------------------------------------------------
    print_log("- Recuperando campos variáveis da tabela de quesitacoes")
    (sucesso, lista_cv_tabela_quesitacoes) = odt_recupera_lista_campos_variaveis_sapi(tr_modelo_quesito)
    if (len(lista_cv_tabela_quesitacoes) == 0):
        print_tela_log(
            "ERRO: Não foi detectado nenhum campo variável na tabela de quesitacoes. Assegure-se de utilizar um template de modelo sapi")
        return False

    #odt_dump(tabela_quesitacoes)
    #var_dump(sucesso)
    #var_dump(lista_cv_tabela_quesitacoes)
    #die('ponto5448')



    # Determina a maior quantidade de quesitos na quesitação
    # ------------------------------------------------------------------
    max_qtd_quesitos = 0
    for quesitacao in quesitacoes:
        if quesitacao['qtd_quesitos']>max_qtd_quesitos:
            max_qtd_quesitos = quesitacao['qtd_quesitos']


    # ------------------------------------------------------------------
    # Gera linhas na tabela padrão de quesitações
    # ------------------------------------------------------------------
    quesitacoes_adicionadas=list()
    q = 0
    for qq in range(1,max_qtd_quesitos+1):
        for quesitacao in quesitacoes:

            # Despreza se não tiver a quantidade de quesitos desejado
            if quesitacao['qtd_quesitos']!=qq:
                continue
            # Ok, quesitação tem a quantide de quesitos em processamento


            q += 1

            #var_dump(quesitacao)
            #die('ponto1863')

            ques_hash = quesitacao['hash']

            print()
            print_tela_log("- Processando quesitação ", ques_hash)
            print_tela_log("- Qtd. quesitos: ", quesitacao['qtd_quesitos'])
            print_tela_log("- Ocorrências: ", quesitacao['ocorrencias'])

            if ques_hash in Gmod_quesitos_respostas:
                # Se já está na lista de quesitos, despreza
                print_tela_log("- Quesitação", ques_hash, "já está no modelo: DESPREZADA")
                continue

            # Processa item, criando nova linha na tabela de quesitacoes
            tr_nova_linha_item = criar_linha_quesitacao_padrao(tr_modelo_quesito, quesitacao, parametros)
            if tr_nova_linha_item is None:
                return

            # Insere nova linha na tabela de quesitacoes
            # Deixamos a primeira linha sempre como o modelo (+1 abaixo)
            tab_quesitacoes.insert(posicao_inserir_tab_quesitacoes, tr_nova_linha_item)
            posicao_inserir_tab_quesitacoes += 1

            # Coloca na lista de quesitos incluidos
            quesitacoes_adicionadas.append(ques_hash)

    # --- Fim do loop de processamento dos itens da tabela de quesitacoes
    # Não faremos isto, pois a linha tem que ser preservada para fazer append no futuro
    # Remove linha de modelo da tabela de quesitacoes
    # tab_quesitacoes.remove(tr_modelo)


    # ------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------
    # Customização do laudo
    # ------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("c) Conferência do modelo gerado")
    print("-------------------------------")

    # Gera novo documento e encerra
    if not odt_substitui_content_xml(Godt_raiz, caminho_arquivo_odt):
        print("- Comando cancelado")
        return False

    # Validação do arquivo gravado
    print()
    # Valida modelo, exibindo mensagens voltadas para Administrador SAPI
    validado_com_sucesso = carrega_valida_modelo(caminho_arquivo_odt, template=True)
    if validado_com_sucesso:
        print()
        print_tela("-" * 100)
        print("Quesitação")
        print_tela("-" * 100)
        _usuario_escolhe_quesitacao(Gmod_quesitos_respostas, apenas_listar=True)
        print()
        print_tela("- Arquivo contém um MODELO de laudo SAPI da unidade sintaticamente correto.")
    else:
        erro_fatal("[5863] Validação de modelo gerado pelo sistema falhou. Comunique desenvolvedor")

    # Tudo certo
    # Abre modelo gerado
    print()
    webbrowser.open(caminho_arquivo_odt)
    print_atencao()
    print_tela_log("- Modelo de laudo gerado com SUCESSO")
    print_tela_log("- Caminho: ", caminho_arquivo_odt)
    print("- Modelo foi aberto em programa compatível (normalmente libreoffice)")
    print("- Recomenda-se utilizar o LIBREOFFICE com versão superior a 5.2")
    espera_enter()

    print()
    print("d) Customização do laudo")
    print("------------------------")
    print()
    print("- Revise o modelo gerado e efetue a customização final, seguindo as instruções contidas no modelo.")
    if adicionando:
        if len(quesitacoes_adicionadas)==0:
            print("- AVISO: NÃO foi localizado nenhum quesito novo.")
            print("- Assegure-se que você forneceu parâmetros de busca corretos")
            # Finaliza
            return False
        else:
            print("- Foram adicionados",len(quesitacoes_adicionadas), "quesitacoes no fim da tabela de quesitos")
            print("- Estes quesitos tem os seguintes hashes: ", ",".join(quesitacoes_adicionadas))
    print()
    print("- Durante a customização é recomendável que você efetue verificações regulares da integridade do modelo.")
    print("- Para isto, recomenda-se que você entre em modelo de validação.")
    print()
    if pergunta_sim_nao("< Deseja entrar em modo de validação do modelo (*VM)?"):
        validado_com_sucesso = loop_validacao_modelo(caminho_arquivo_odt)

    return validado_com_sucesso


def atualizar_modelo_siscrim():

    print()
    print("Atualização do modelo no SisCrim")
    print("---------------------------------")
    print()
    print("- Para colocar o seu modelo em produção é necessários atualizar (fazer o upload) o Siscrim")
    if not pergunta_sim_nao("< Deseja atualizar o modelo no Siscrim agora", default="s"):
        return False

    abrir_browser_siscrim("/sistemas/criminalistica/modelo_usuario.php?acao=listar",
                          descricao_pagina="Administração do Sistema => Modelos de Usuário")

    print_atencao()
    print("- Na mesma tela de inclusão de modelo existem duas tabelas distintas: modelos de usuário e modelos da unidade")
    print("  Para que todos os usuários SAPI na sua unidade tenha acesso ao modelo, ")
    print("  o mesmo deve ser cadastrado como um MODELO DA UNIDADE (não como um modelo de Usuário)")
    print("- No campo NOME, coloque algo que lembre o SAPI, para facilitar a identificação pelo usuário.")
    print("- No 'Tipo de documento' escolha 'LAUDO'")
    print("- Na 'Classe de Laudo' deixe em branco uma vez existem serão produzidos laudos SAPI para várias classes")
    print("- Na 'SubClasse de Laudo' deixe em branco, pelo mesmo motivo acima.")
    print()

    return True


def odt_procura_bloco(dblocos, nome_bloco):
    bloco = dblocos.get(nome_bloco.lower(), None)
    if bloco is None:
        print_log("Não foi localizado bloco com nome",nome_bloco)
        return None

    return bloco


# Cria uma linha para tabela de quesitações
def criar_linha_quesitacao_padrao(tr_modelo_linha_quesitacao, quesitacao, parametros):

    # Duplica modelo para criar nova linha
    nova_linha = copy.deepcopy(tr_modelo_linha_quesitacao)

    # Procura por campos de substiuição na nova linha
    (sucesso, lista_cv_linha) = odt_recupera_lista_campos_variaveis_sapi(nova_linha)

    # Mapeamento filho para pai na nova linha
    filho_para_pai_linha_map = {
        c: p for p in nova_linha.iter() for c in p
        }

    # Cada quesitação vem com os seguintes campos:
    #'hash': '789a5d052be2432b4b1a56558e19836f',
    #'identificacao': 'Laudo 007/2017-SETEC/SR/PF/RN',
    #'ocorrencias': 1,
    #'ocorrencias_codigo_unidade': {'3641': 1},
    #'ocorrencias_sigla_unidade': {'SETEC/SR/PF/RN': 1},

    # Montagem de valores de campos para substituição
    observacao = texto(quesitacao['ocorrencias'],
                 'ocorrências entre',
                 quesitacao['data_primeira_ocorrencia'],
                 ' e ',
                 quesitacao['data_ultima_ocorrencia'])
    laudo_referencia =  texto(quesitacao['identificacao'],
                              '(',
                              quesitacao['codigo_documento_interno'],
                              ')')
    # substituição de campos na nova linha
    dcs = dict()
    dcs['sapiQuesitacaoHash']               = quesitacao['hash']
    dcs['sapiQuesitacaoObservacao']         = observacao
    dcs['sapiQuesitacaoLaudoReferencia']    = laudo_referencia
    for cs in dcs:
        odt_substitui_campo_variavel_texto(lista_cv_linha , cs, dcs[cs])

    # --------------------------------------------------------------------------------------------------
    # Montagem da seção de Quesitos (sapiQuesitosXXXX)
    # --------------------------------------------------------------------------------------------------
    # Localiza o campo variável sapiTextoQuesitacao
    campo_var="sapiTextoQuesitacao"
    (posicao_substituir,
     paragrafo_substituir,
     pai_paragrafo_substituir) = odt_determinar_coordenadas_substituicao_campo_var(
        lista_cv_linha,
        filho_para_pai_linha_map,
        campo_var)


    # Criar vários paràgrafos, um para cada quesito
    # ----------------------------------------------------------
    # var_dump(posicao_substituir)
    # var_dump(pai_paragrafo_substituir)
    # die('ponto1338')
    pos = posicao_substituir
    for texto_quesito in quesitacao['quesitos']:

        # Criar um novo parágrafo
        novo_paragrafo = copy.deepcopy(paragrafo_substituir)

        # Substitui texto variável
        odt_localiza_substitui_campo_variavel_ok(novo_paragrafo, campo_var, texto_quesito)

        # Insere o novo parágrafo
        pai_paragrafo_substituir.insert(pos, novo_paragrafo)
        pos += 1

    # odt_dump(tr_nova_linha_item)
    # odt_dump(pai_paragrafo_substituir)
    # die('ponto1427')

    # Após ter inserido todos os parágrafos do bloco,
    # remove o parágrafo que contém o campo variável de substituição
    # (ex: saiTextoQuesitacao)
    pai_paragrafo_substituir.remove(paragrafo_substituir)


    # --------------------------------------------------------------------------------------------------
    # Montagem da seção de Respostas (sapiRespostasXXXX)
    # --------------------------------------------------------------------------------------------------

    # Recupera bloco de identificação específico
    # para o tipo de componente
    # (ex: sapiIdentificacaoAparelho, sapiIdentificacaoSim)
    nome_bloco_componente = "sapiRespostaPadrao"
    bloco = Gmod_blocos.get(nome_bloco_componente.lower(), None)
    if bloco is None:
        print_tela_log(
            texto("Erro: Não foi localizado bloco com nome[",
                  nome_bloco_componente,
                  "] no seu documento.",
                  " Confira/corrija o seu modelo.",
                  "(Esclarecimento: Nome do bloco NÃO é case sensitive)"
                  )
        )
        return None

    # O bloco de sapiRespostas contém uma linha de quesitação e
    # várias linhas de respostas
    # Analisando certas palavras chaves nos quesitos
    # será montado a resposta padrão
    # ----------------------------------------------------------
    lista_novos_par = list()
    for texto_quesito in quesitacao['quesitos']:

        gerou_resposta = False

        # Analisa o quesito, para determinar quais respostas padrões são adequadas
        lista_respostas = obter_lista_respostas_padroes(texto_quesito)
        debug("Lista de respostas para quesito: ", ",".join(lista_respostas))

        for par in bloco:
            # Duplica parágrafo
            novo_paragrafo = copy.deepcopy(par)

            (sucesso, lista_cv_par) = odt_recupera_lista_campos_variaveis_sapi(novo_paragrafo)

            # Se a linha não contiver nenhuma variável (a linha em branco no final, por exemplo)
            # aceita a linha incondicionalmente
            if len(lista_cv_par)==0:
                lista_novos_par.append(novo_paragrafo)
                continue

            # Se for linha de quesito, efetua a substituição de variável por texto
            if odt_lista_contem_campo_variavel(lista_cv_par, 'sapiQuesitoPadrao'):
                odt_substitui_campo_variavel_texto(lista_cv_par, 'sapiQuesitoPadrao', texto_quesito)
                lista_novos_par.append(novo_paragrafo)
                continue


            # Aceita a linha se a mesma contém algum das respostas necessárias
            aceitar_linha = False
            for resposta in lista_respostas:
                if odt_lista_contem_campo_variavel(lista_cv_par, resposta):
                    aceitar_linha = True

            if aceitar_linha:
                lista_novos_par.append(novo_paragrafo)
                gerou_resposta = True

        # Leu todos os parágrafos no bloco
        if not gerou_resposta:
            print_tela_log("Quesito abaixo ficou sem resposta")
            print_tela_log(texto_quesito)
            print()
            print_tela_log("Conjunto de resposta associadas:", ",".join(lista_respostas))
            print_tela_log("Revise se o bloco sapiRespostaPadrao está integro e contém campos variáveis para todas as respostas acima")
            erro_fatal("ERRO [6040]: Não foi gerada resposta para quesito")

    # Substitui a varíavel SapiRespostaPadrao pelo conjunto de parágrafos seleiconados acima
    # ---------------------------------------------------------------------------------------------------
    # Localiza o campo variável para substituir
    campo_var = "sapiRespostaPadrao"
    (posicao_substituir,
     paragrafo_substituir,
     pai_paragrafo_substituir) = odt_determinar_coordenadas_substituicao_campo_var(
        lista_cv_linha,
        filho_para_pai_linha_map,
        campo_var)

    # Substitui variável por lista de parágrafos
    # ----------------------------------------------------------
    odt_substituir_paragrafo_por_lista(paragrafo_substituir, nova_linha, lista_novos_par)

    # odt_dump(tr_nova_linha_item)
    # odt_dump(pai_paragrafo_substituir)
    # die('ponto1427')

    # Após ter inserido todos os parágrafos do bloco,
    # remove o parágrafo que contém o campo variável de substituição
    # (ex: sapiItemIdentificacao)
    #pai_paragrafo_substituir.remove(paragrafo_substituir)


    return nova_linha


def obter_lista_respostas_padroes(texto_quesito):

    lista_respostas = list()

    resposta=dict()
    resposta['sapiRespostaCaracteristicasMaterial']= ['natureza', 'características', ' GSM']
    resposta['sapiRespostaNumeroTelefone'] = ['habilitação', 'habilitado', 'número de telefonia']
    resposta['sapiRespostaIdentificarUsuario'] = ['usuário']
    resposta['sapiRespostaIdentificarProprietario'] = ['proprietário', 'pertence']
    resposta['sapiRespostaLigacoesTelefonicas'] = ['ligações', 'discados', 'chamadas']
    resposta['sapiRespostaAgenda'] = ['agenda']
    resposta['sapiRespostaMensagens'] = ['mensagens', 'SMS', 'WhatsApp', 'comunicações eletrônicas']
    resposta['sapiRespostaArquivos'] = ['arquivos', 'áudios', 'fotos', 'vídeos']
    resposta['sapiRespostaCruzamento'] = ['cruzamento', 'trocadas entre']
    resposta['sapiRespostaBlackBerry'] = ['BlackBerry']
    resposta['sapiRespostaHash'] = [' Hash']
    resposta['sapiRespostaApagados'] = ['apagado', 'apagada']
    resposta['sapiRespostaConteudoPIJ'] = ['pornografia',
                                           'infantil',
                                           'adolescente',
                                           'sexo',
                                           'pedofilia',
                                           'nudez',
                                           'crianças']

    resposta['sapiRespostaOutrosDadosJulgadosUteis'] = ['julgados úteis']

    debug("Buscando respostas para quesitacao abaixo:")
    debug(texto_quesito)
    for nome_resposta in resposta:
        for termo in resposta[nome_resposta]:
            if (str(termo).lower() in str(texto_quesito).lower()):
                if (nome_resposta not in lista_respostas):
                    lista_respostas.append(nome_resposta)
                    debug("Resposta => ", nome_resposta)

    # Se não bateu com nenhuma das repostas acima,
    # retorna variável para gerar resposta específica
    if len(lista_respostas)==0:
        lista_respostas.append('sapiRespostaEspecifica')
        print_tela_log("- Quesito abaixo não se enquadrou em nenhuma resposta padrão. Associado com resposta específica")
        print_tela_log(texto_quesito)
        debug("Nenhuma associação com respostas padrões. Utilizando resposta específica")

    return lista_respostas



# Função que carrega o arquivo de modelo e valida sintaticamente
# True: Modelo carregado e válido
# False: Ocorreu algum erro (já indicado)
def teste_carrega_valida_modelo(caminho_arquivo_modelo_odt, template=False):

    odt_carrega_arquivo(caminho_arquivo_modelo_odt)
    var_dump(Godt_raiz)
    #odt_dump(Godt_raiz, nivel_max=1)
    return

    print()
    print("==================== Copiando arquivo ====")
    caminho_novo = "D:/tempr/xml/gravado.odt"
    print("- Copiando arquivo para", caminho_novo)
    if os.path.isfile(caminho_novo):
        if not pergunta_sim_nao("< Arquivo de saída já existe. Será substituido. Prosseguir?", default="n"):
            print("- Operação cancelada pelo usuário.")
            return
    try:
        # Tenta copiar arquivo
        shutil.copyfile(caminho_arquivo_modelo_odt, caminho_novo)
    except BaseException as e:
        print_tela_log("- ERRO na criação do arquivo", caminho_arquivo_modelo_odt, "=> ", str(e))
        print_tela_log("- Verifique se arquivo não está aberto, ou se existe alguma outra condição que possa estar impedindo a sua criação")
        return None

    print("- Arquivo copiado")

    # Salva o arquivo em um novo arquivo
    print()
    print("============= Atualizando content_xml do novo arquivo")
    if not odt_substitui_content_xml(Godt_raiz, caminho_novo):
        die('ponto6866')


    # Carrega o novo arquivo, para ver se name spaces foram preservados
    odt_carrega_arquivo(caminho_novo)
    die('ponto3190')


# Função que carrega o arquivo de modelo e valida sintaticamente
# True: Modelo carregado e válido
# False: Ocorreu algum erro (já indicado)
def teste_xml_edit():

    # Caminho original
    caminho_xml = "D:/tempr/xml/content.xml"
    print("==== Namespace ====")
    odt_print_ns(xml_parse_and_get_ns(caminho_xml))

    # Registra os namespace no xml_tree
    ns=xml_parse_and_get_ns(caminho_xml)
    #var_dump(ns)
    #die('ponto6921')
    qtd = 1
    for k in ns:
        prefix = k
        uri = ns[k]
        xml.etree.ElementTree.register_namespace(prefix, uri)
        print("registrando", prefix, uri)
        qtd = qtd+1

    # Faz parse no arquivo
    xml_tree = xml.etree.ElementTree.parse(caminho_xml)
    root = xml_tree.getroot()

    #var_dump(root)
    #die('ponto6868')

    # Grava novo arquivo
    caminho_xml1 = "D:/tempr/xml/content1.xml"
    xml_tree.write(caminho_xml1, xml_declaration=True, encoding='utf-8', method="xml")

    #Le namespace do arquivo gravado
    print("============== DEPOIS =====================")
    odt_print_ns(xml_parse_and_get_ns(caminho_xml1))
    # odt_dump(xml_odt)
    die('ponto6917')


def teste2():
    caminho_template = "D:/tempr/xml/LAUDO_MODELO_VERSAO_2_3.odt"
    odt_carrega_arquivo(caminho_template)
    print("="*100)
    odt_dump(Godt_raiz)
    print("="*100)
    odt_print_ns(Gxml_ns)
    die('ponto6950')


if __name__ == '__main__':


    #sapisrv_inicializar_ok(Gprograma, Gversao, auto_atualizar=True)

    #teste2()
    #die('ponto6950')
    #caminho_template = "D:/tempr/xml/LAUDO_MODELO_VERSAO_2_3.odt"
    #carrega_valida_modelo(caminho_template)
    #die('ponto6905')

    #caminho_template = "C:/Users/PCF-/Downloads/Laudo_1693_2018_SETEC_SR_PF_PR.odt"
    #print(caminho_template)
    #teste_xml_edit()
    #die('ponto6337')

    main()
    #quesitacoes=dict()
    #caminho_arquivo_entrada_odt='C:\\Users\\PCF-\\Dropbox\\desenvolvimento_python\\repositorio_github\\sapi\\LAUDO_MODELO_VERSAO_2_3.odt'
    #criar_modelo_unidade(caminho_arquivo_entrada_odt, quesitacoes)
    #die('ponto6777')

    #sapisrv_inicializar_ok(Gprograma, Gversao, auto_atualizar=True)
    #caminho_template=obter_template_laudo()
    #var_dump(caminho_template)
    #die('ponto6789')


    print()
    espera_enter("Programa finalizado. Pressione <ENTER> para fechar janela.")

