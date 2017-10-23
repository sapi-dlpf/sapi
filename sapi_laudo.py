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
#  - v1.0 : Inicial
#  - v1.3 (2017-05-16 Ronaldo): Ajuste para sapilib_0_7_1
#  - v1.4 (2017-05-17 Ronaldo):
#    Substituição de variáveis por blocos em respostas aos quesitos
#  - v1.5 (2017-05-22 Ronaldo):
#    sapi_lib_0_7_2 que efetua checagem de versão de programa
# =======================================================================
# TODO: 
# - Se laudo já foi concluído, desprezar o que está em cache (o mesmo
#   problema ocorre no sapi_cellebrite e todos os clientes que tem cache)
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
Gprograma = "sapi_laudo"
Gversao = "2.1"

# Para gravação de estado
Garquivo_estado = Gprograma + "v" + Gversao.replace('.', '_') + ".sapi"

# Base de dados (globais)
GdadosGerais = dict()  # Dicionário com dados gerais
Glaudo = None
Gitens = list()  # Lista de itens do laudo
Gtarefas = None
Gsolicitacao_exame = None
Gmateriais_solicitacao = None
Gstorages_laudo = list()  # Lista de storages associados a tarefas do laudo
Gmodelo_configuracao = list() # Dados coletados do modelo

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

# Constantes para localização de seções do laudo, que serão substituídos por blocos de parágrafos
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
from sapilib_0_8_1 import *

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
            console_dump_formatado(dados_relevantes_json["laudo"], Glargura_tela)
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
===================== BIBLIOTECA ODT ===================================
========================================================================
'''

# Globais da biblioteca ODT
Gxml_ns = None
Gxml_ns_inv = None


def odt_set_xml_ns(xml_ns):
    # Irá alterar estas duas globais
    global Gxml_ns
    global Gxml_ns_inv

    # Guarda em global
    Gxml_ns = xml_ns

    # Inverte dicionário de namespace e guarda em global
    Gxml_ns_inv = {}
    for k in Gxml_ns:
        Gxml_ns_inv[Gxml_ns[k]] = k


def decompoe_ns_tag(ns_tag):
    partes = ns_tag.split('}')
    ns = partes[0] + '}'
    tag = partes[1]

    return (ns, tag)


def parse_and_get_ns(xml_string):
    events = "start", "start-ns"
    root = None
    ns = {}
    for event, elem in xml.etree.ElementTree.iterparse(xml_string, events):
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


# Recupera o texto do elemento e de todos os seus descendentes
def odt_obtem_texto_recursivo(elem):
    # Texto no próprio elemento
    t = ""
    if (elem.text is not None):
        # Texto no próprigo elemento
        t = t + elem.text

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
    for p in elemento.findall('text:p', Gxml_ns):
        odt_dump_paragrafo(p)
        print("========================================================")


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
        print_log("- Encontrando campo de usuário [" + cv["name"] + "]")
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
        # Verifica nome do campo
        nome = cv["name"].lower()
        if (nome[:4] != "sapi"):
            print_tela_log("- Campo [", cv["name"], "] com nome fora do padrão (Formato correto: sapiXXXX")
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
            print_tela_log("- Campo variável [", cv["name"],
                           "] mal formatado. Todo campo variável deve possuir um estilo para diferenciá-lo do restante do parágrafo. Posicione sobre o campo, digite F11 e na aba de estilo de caracter troque para o estilo 'sapiCampoVar'. Se o campo variável ocorrer mais de uma vez no texto, execute o procedimento para cada ocorrência.")
            erros += 1

        # Verifica se o valor do campo é compatível com o nome da variável
        # ---------------------------------------------------------------
        # Exemplo: Nome: sapiXyz => Valor: {sapiXyz}
        texto = cv['texto']
        texto_esperado = '{' + cv['name'] + '}'
        if (texto != texto_esperado):
            print_tela_log("- Campo variável '" + cv[
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
            print_tela_log("- Campo variável '" + cv["name"] + "' não tem estilo sapiCampoVar")
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
        erro_fatal("Erro de integridade entre pai e filho para substiuição de sapiItemIdentificacao")

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


# Função auxiliar para remover um ou mais arquivos de um zip
#
# A remoção de um arquivo .ODT é complicada, pois implica em recriar
# o arquivo, descartando os arquivos a serem removidos
#
# Uma vez que o ODT é um zip, permite remover componentes de um arquivo ODT
# Neste caso, esta função é utilizada para remover o content.xml
# para depois colocar um novo arquivo no lugar.
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


def odt_dump(elem, nivel=0):
    # Exibe pai
    odt_dump_print(elem, nivel)

    # Exibe filhos
    nivel += 1
    for filho in elem:
        # Recursivo
        odt_dump(filho, nivel)


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
def carrega_blocos(base):
    # Dicionário de blocos
    dblocos = {}

    # Recupera todos os parágrafos
    lista_p = odt_recupera_recursivamente(base, 'p')

    # Varre todRecupera e armazena Parágrafos do texto
    bloco_iniciado = False
    nome_bloco = None
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

            # Inicia bloco
            print_log("Bloco [", nome_bloco, "] iniciado em parágrafo:", q)
            lista_par = []
            # Remove parágrafo
            pai.remove(paragrafo)
            # Prossegue para o próximo parágrafo
            continue

        # Trata fim de bloco
        # if (False):
        # if (blocoFim.lower() in texto.lower()):
        if (texto.lower()[:len(bloco_fim)] == bloco_fim.lower()):

            if (not bloco_iniciado):
                msg_erro = "Bloco finalizado sem ser iniciado. Procure no texto por um '" + bloco_fim + "' sobrando"
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
            pai.remove(paragrafo)
            # Prossegue para o próximo parágrafo
            continue

        # Trata parágrafos do bloco
        if (bloco_iniciado):
            # Adiciona parágrafo na lista de parágrafos do bloco
            lista_par.append(paragrafo)
            # Remove parágrafo
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

    # Substitui campos gerais do item
    # --------------------------------------------------------------
    dcs = dict()
    dcs['sapiItem'] = dados_item['item']
    dcs['sapiDescricaoSiscrim'] = dados_item['descricao']
    dcs['sapiMaterialSiscrim'] = dados_item['material']

    # Pode não existir lacre de entrada
    if (dados_item['lacre_anterior'] is not None):
        dcs['sapiLacre'] = dados_item['lacre_anterior']

    for cs in dcs:
        odt_substitui_campo_variavel_texto(lista_cv_tr_nova_linha_item, cs, dcs[cs])

    # Recupera dados para laudo tarefas do item da fase de aquisição
    lista_dados_laudo = recupera_dados_para_laudo_das_tarefas_item(dados_item, fase='10-aquisicao')

    lista_novos_par = []  # Lista de parágrafos que será gerada
    for dados_tarefa in lista_dados_laudo:

        quantidade_componentes = dados_tarefa['sapiQuantidadeComponentes']
        print_log("Item possui", quantidade_componentes, " componentes")

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
                    texto("Erro: Não foi localizado bloco com nome[",
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

            # Próximo componente
            q_comp += 1

            # -- Fim do processamento do componente

    # -- Fim do processamento da lista de dados para laudo

    # Terminou o processamento de todos os componentes do item
    # Logo, já tem a lista de parágrafos que serão utilizados
    # Agora tem que efetuar a substituição na linha de modelo da tabela
    # de materiais
    #
    # Localiza o campo variável de sapiItemIdentificacao
    # --------------------------------------------------------------
    posicao_substituir = None
    paragrafo_substituir = None
    pai_paragrafo_substituir = None
    for cv in lista_cv_tr_nova_linha_item:
        if (cv["name"] == 'sapiItemIdentificacao'):
            # O avô do span de texto variável é o que será substituído
            # <text:p text:style-name="P70">
            # 	<text:span text:style-name="sapiCampoVar">
            # 		<text:user-field-get text:name="sapiItemIdentificacao">{sapiItemIdentificacao}</text:user-field-get>
            # 	</text:span>
            # </text:p>
            pai = cv["pai"]
            avo = filho_para_pai_tr_nova_linha_item_map[pai]

            # var_dump(cv)
            # var_dump(pai)
            # var_dump(avo)
            if (odt_get_tipo(avo) != 'p'):
                erro_fatal("Tipo de ancestral do campo 'sapiItemIdentificacao' não é parágrafo")
            paragrafo_substituir = avo

            # die('ponto1213')

            # Localiza o pai do parágrafo alvo
            pai_paragrafo_substituir = filho_para_pai_tr_nova_linha_item_map[paragrafo_substituir]
            posicao_substituir = odt_determina_posicao_pai_filho(pai_paragrafo_substituir, paragrafo_substituir)
            if (posicao_substituir is None):
                erro_fatal("Erro de integridade entre pai e filho para substiuição de sapiItemIdentificacao")

    if (paragrafo_substituir is None):
        erro_fatal("Campo de substituição {sapiItemIdentificacao} não localizado na linha de tabela de materiais")

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
            print(resumo_quesitos)
            die('ponto1400')

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


def _usuario_escolhe_quesitacao(quesitos_respostas):
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
            pergunta = "< Informe a quantidade de quesitos da quesitação (ou * para listar todas): "
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
                  "  Nome da quesitação:", nome_quesito
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

        print()
        print("- Dica:  No nome da quesitação identifica-se também a unidade de origem (ex: cac, lda)")
        print("- Escolha a quesitação que mais se aproxima da quesitação da solicitação.")
        print('- Caso a quesitação da solicitação de exame não seja idêntica a nenhuma das quesitações padrões,')
        print('  selecione a que possuir maior semelhança, efetue os ajustes diretamente no seu laudo')
        print('  e posteriormente notique o gestor do GTPI (informando o número do laudo), para que este avalie')
        print('  a necessidade de ampliação dos modelos de quesitação.')
        print('- Em função de limitações da console,  é possível que alguns caracteres acentuados tenham ')
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
def determina_quesitacao_old(quesitos_respostas, dblocos):
    # Usuário escolhe quesitação, em modo interativo
    quesitacao_selecionada = usuario_escolhe_quesitacao(quesitos_respostas)

    if quesitacao_selecionada is None:
        return None, None

    nome_bloco_quesitos = quesitacao_selecionada["nome_bloco_quesitos"]
    nome_bloco_respostas = quesitacao_selecionada["nome_bloco_respostas"]

    # Recupera listas de parágrafos das perguntas e respostas
    lista_par_quesitos = odt_clonar_bloco(nome_bloco_quesitos, dblocos)
    lista_par_respostas = odt_clonar_bloco(nome_bloco_respostas, dblocos)

    return lista_par_quesitos, lista_par_respostas



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

    # -------------------------------------------------------------------
    # Copia arquivo de entrada xxxx.odt para
    # arquivo de saída xxxx_sapi.odt
    # -------------------------------------------------------------------

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
    print("Passo 2: Validação de modelo do laudo")
    print("-------------------------------------")

    # -------------------------------------------------------------------
    # Extrai arquivo de conteúdo (content.xml) do odt
    # -------------------------------------------------------------------

    # Um arquivo ODT é um ZIP contendo arquivos XML
    # Logo, primeiriamente é necessário abrir o zip
    print_log("- Unzipando arquivo de saída")
    zf = zipfile.ZipFile(caminho_arquivo_saida_odt, 'r')
    # listarArquivos(zf)
    # exibirInfo(zf)

    # Cria pasta temporária para extrair arquivo
    pasta_tmp = tempfile.mkdtemp()

    # O conteúdo propriamente dito do arquivo ODT
    # está armazenado no arquivo content.xml
    arq_content_xml = "content.xml"
    if not arq_content_xml in zf.namelist():
        print_tela_log("- ERRO: Não foi encontrado arquivo: " + arq_content_xml)
        return

    # Extrai e converte arquivo content.xml para um string xml
    try:
        # Extração de content.xml para arquivo em pasta temporária
        zf.extract(arq_content_xml, pasta_tmp)
        print_log("- Arquivo content_xml extraído para [", pasta_tmp, "]")
        caminho_arq_content_xml = pasta_tmp + "/" + arq_content_xml

        # Le todo o arquivo content.xml e armazena em string
        xml_string = zf.read(arq_content_xml)
    except BaseException as e:
        print_tela_log("'ERRO: Não foi possível ler arquivo " + arq_content_xml)
        print_tela_log("Erro: ", e)
        return None

    # Verifica se arquivo foi criado com sucesso
    if (os.path.isfile(caminho_arq_content_xml)):
        print_log("- Extraído arquivo de conteúdo (content.xml) com sucesso para [", caminho_arq_content_xml, "]")
    else:
        print_tela_log("- Extração de arquivo de conteúdo (content.xml) para [", caminho_arq_content_xml,
                       "] FALHOU. Arquivo não foi encontrado.")
        return

    # -------------------------------------------------------------------
    # Início de parse de content.xml
    # -------------------------------------------------------------------

    # Obtém namespaces do arquivo xml
    # e salva em global Gxml_ns
    odt_set_xml_ns(parse_and_get_ns(caminho_arq_content_xml))

    # Obrigatoriamente tem que existir um namespace "text"
    if (Gxml_ns.get("text", None) is None):
        # Se não existe a seção text, tem algo esquisito...
        print_tela_log(
            "- ERRO: Falhou no parse dos namespaces. Não encontrado seção 'text'. Assegure-se que o arquivo informado é um ODT bem formado")
        return

    # Faz parse geral do arquivo, que já foi lido e armazenado em string
    odt_raiz = xml.etree.ElementTree.fromstring(xml_string)

    # Antes de mais nada, vamos remover todos os comentários
    # Um comentário é um parágrafo iniciado por #
    odt_remove_comentarios(odt_raiz)

    #var_dump(Gmodelo_configuracao)
    #print(Gmodelo_configuracao)
    modelo_versao="MODELO_VERSAO_3_0"
    if (modelo_versao not in Gmodelo_configuracao):
        print_tela_log(
            texto("- ERRO: Este programa requer um laudo padrão SAPI",
                  modelo_versao)
        )
        print_tela("- Retorne ao SisCrim e gere o modelo na versão mais atualizada.")
        return

    # odt_dump(odt_raiz)
    # die('ponto1434')

    # Localiza blocos xml relevantes
    # O mais importante é office:text
    office_body = odt_raiz.find('office:body', Gxml_ns)
    office_text = office_body.find('office:text', Gxml_ns)

    # Monta mapeamento para elemento pai de todos os elemento de office:text
    # Isto é necessário, pois no ElementTree não existe mecanismo
    # para navegar para o pai (apenas para os filhos)
    filho_para_pai_map = {c: p for p in office_text.iter() for c in p}

    # -------------------------------------------------------------------
    # Recupera e valida lista de campos váriaveis
    # -------------------------------------------------------------------

    print_log("- Recuperando e validando referência a campos variáveis")
    (sucesso, lista_cv_office_text) = odt_recupera_lista_campos_variaveis_sapi(office_text)
    #var_dump(lista_cv_office_text)
    #die('ponto1881')
    if (not sucesso):
        print_tela_log(
            "ERRO => Campos variáveis inválidos: Providencie o ajuste dos campos variáveis no modelo (consulte o gestor do GTPI)")
        return
    if (len(lista_cv_office_text) == 0):
        print_tela_log(
            "ERRO: Não foi detectado nenhum campo variável no padrão sapi. Assegure-se de utilizar um modelo de ODT sapi para a geração do laudo")
        return

    # -------------------------------------------------------------------
    # Carrega blocos de parágrafos
    # -------------------------------------------------------------------
    print_tela_log("- Recuperando definições de blocos de parágrafos")
    # Recupera blocos de parágrafos
    (sucesso, dblocos) = carrega_blocos(office_text)
    if (not sucesso):
        return

        # ------------------------------------------------------------------
        # Otimização....
        # Atualmente está buscando as tarefas duas vezes
        # (para montar tabela de materiais e montar tabela de hashes)
        # TODO: Guardar tarefas com itens, evitando repetição de consulta
        # no servidor
        # ------------------------------------------------------------------
    # for dadosItem in Gitens:
    # 	tarefas=obter_tarefas_finalizadas_item(dadosItem["item"])
    # 	var_dump(tarefas)
    # 	die('ponto1933')


    # -------------------------------------------------------------------
    # Verifica quesitação
    # -------------------------------------------------------------------
    print_tela_log("- Verificando definições de quesitação")
    (sucesso, quesitos_respostas) = parse_quesitos_respostas(dblocos)
    if (not sucesso):
        print_tela_log("- Corrija blocos de quesitação conforme indicado")
        return

    # ------------------------------------------------------------------------------------------------------------------
    # Solicita que usuário escolha a quesitação
    # ------------------------------------------------------------------------------------------------------------------
    print()
    print("Passo 3: Escolha da quesitação")
    print("------------------------------")

    # Usuário escolhe quesitação, em modo interativo
    quesitacao_selecionada = usuario_escolhe_quesitacao(quesitos_respostas)

    if quesitacao_selecionada is None:
        return

    nome_bloco_quesitos = quesitacao_selecionada["nome_bloco_quesitos"]
    nome_bloco_respostas = quesitacao_selecionada["nome_bloco_respostas"]

    # Recupera listas de parágrafos das perguntas e respostas
    lista_par_quesitos = odt_clonar_bloco(nome_bloco_quesitos, dblocos)
    lista_par_respostas = odt_clonar_bloco(nome_bloco_respostas, dblocos)

    #lista_par_quesitos, lista_par_respostas = determina_quesitacao(quesitos_respostas, dblocos)
    #if lista_par_quesitos is None:
    #    return

    # ------------------------------------------------------------------------------------------------------------------
    # Substitui sapiQuesitos
    # ------------------------------------------------------------------------------------------------------------------
    cv_sapi_quesitos = odt_localiza_campo_variavel(lista_cv_office_text, 'sapiQuesitos')
    if (cv_sapi_quesitos is None):
        print_tela_log("ERRO: Modelo sapi mal formado. Não foi localizado campo de substituição 'sapiQuesitos'.")
        return

    paragrafo_substituir_sapi_quesitos = odt_busca_ancestral_com_tipo(cv_sapi_quesitos['pai'], raiz=odt_raiz, tipo='p')
    # var_dump(ancestral)
    # odt_dump(ancestral)
    # die('ponto1836')
    if (paragrafo_substituir_sapi_quesitos is None):
        print_tela_log("ERRO 1938: Não encontrado parágrafo onde se localiza 'sapiQuesitos'")
        return

    odt_substituir_paragrafo_por_lista(paragrafo_substituir_sapi_quesitos, odt_raiz, lista_par_quesitos)

    # ------------------------------------------------------------------------------------------------------------------
    # Substitui sapiRespostas
    # ------------------------------------------------------------------------------------------------------------------
    cv_sapi_respostas = odt_localiza_campo_variavel(lista_cv_office_text, GsapiRespostas)
    if (cv_sapi_respostas is None):
        print_tela_log(
            "ERRO: Modelo sapi mal formado. Não foi localizado campo de substituição '" + GsapiRespostas + "'.")
        return

    paragrafo_substituir_sapi_respostas = odt_busca_ancestral_com_tipo(cv_sapi_respostas['pai'], raiz=odt_raiz,
                                                                       tipo='p')
    if (paragrafo_substituir_sapi_respostas is None):
        print_tela_log("ERRO 1955: Não encontrado parágrafo onde se localiza '" + GsapiRespostas + "'")
        return

    # Por fim, substitui os parágrafos das respostas aos quesitos
    odt_substituir_paragrafo_por_lista(paragrafo_substituir_sapi_respostas, odt_raiz, lista_par_respostas)

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
    tabela_materiais = None
    for table in office_text.findall('table:table', Gxml_ns):
        # print(table)
        # print(table.attrib)
        # die('ponto643')
        nome_tabela = obtem_atributo_xml(table, 'table:name')
        # print(nome_tabela)
        if (nome_tabela == 'tabela_materiais'):
            print_log("- Localizada tabela de materiais")
            tabela_materiais = table

    if (tabela_materiais is None):
        print_tela_log("- ERRO: Não foi localizada a tabela de materiais.")
        print_tela_log("A tabela de materiais é caracterizada através da propriedade nome=tabela_materiais.")
        print_tela_log("Verifique se o arquivo de modelo a partir do qual foir gerado o laudo atende este requisito.")
        return None

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
    tr_linhas = tabela_materiais.findall('table:table-row', Gxml_ns)
    qtd_linhas = len(tr_linhas)
    if (qtd_linhas != 2):
        # Não é comum ter mais de duas linhas...então é melhor avisar
        print_tela_log("- Tabela de materiais contém", qtd_linhas, " linhas, o que é incomum.")
        print_tela_log("- Assumindo que a linha de modelo para substituição é a última linha da tabela de materiais")
    tr_modelo = tabela_materiais.findall('table:table-row', Gxml_ns)[qtd_linhas - 1]

    tab_materiais = filho_para_pai_map[tr_modelo]
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
    # Ordena lista de itens
    # ------------------------------------------------------------------
    # Por enquanto não vamos precisar disto, pois o servidor está
    # retornando os itens ordenados por item...
    # Mas talvez mais tarde precise deste código.
    # dicItem={}
    # ix=0
    # for dadosItem in Gitens:
    # 	dicItem[dadosItem["item"]]=ix
    # 	ix=ix+1
    #
    # for d in sorted(dicItem):
    # 	ix=dicItem[d]
    # 	print(d,ix)
    # #var_dump(keys(dicItem))
    # die('ponto1565')


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
        tr_nova_linha_item = criar_linha_para_item(tr_modelo, dados_item, dblocos)
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
        qtd_substituicoes = odt_substitui_campo_variavel_texto(lista_cv_office_text, substituir, novo_valor)
        if (qtd_substituicoes == 0):
            print("Falhou na substituição de '" + substituir + "'")
            return
        else:
            print("- Substituído", substituir)

    # ------------------------------------------------------------------------------------------------------------------
    # Substitui sapiEntrega
    # ------------------------------------------------------------------------------------------------------------------

    nome_bloco_entrega=None
    cv_sapi_entrega = odt_localiza_campo_variavel(lista_cv_office_text, GsapiEntrega)
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

        # A substituição será feita no próximo passo, uma
        # vez que agora o campo sapiEntrega está dentro de um bloco variável

        ## Recupera bloco de parágrafos do método de entrega selecionado

        ## Recupera listas de parágrafos do bloco de substituição
        # lista_par_entrega = odt_clonar_bloco(nome_bloco_entrega, dblocos)
        # # Substitui bloco de parágrafo
        # # Procurar parágrafo que será substituido
        # paragrafo_substituir_sapi_entrega = odt_busca_ancestral_com_tipo(
        #     cv_sapi_entrega['pai'],
        #     raiz=odt_raiz,
        #     tipo='p',
        #     debug=True)
        #
        # #var_dump(cv_sapi_entrega)
        # var_dump(paragrafo_substituir_sapi_entrega)
        # odt_dump_paragrafo(paragrafo_substituir_sapi_entrega)
        # die('ponto2187')
        # if (paragrafo_substituir_sapi_entrega is None):
        #     print_tela_log("ERRO 2239: Não encontrado parágrafo onde se localiza '" + GsapiEntrega + "'")
        #     # Não é um erro fatal....
        #     #return
        #
        # odt_substituir_paragrafo_por_lista(paragrafo_substituir_sapi_entrega, odt_raiz, lista_par_entrega)
        # --- Fim substituição de sapiEntrega



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
        (sucesso, lista_cv) = odt_recupera_lista_campos_variaveis_sapi(odt_raiz)
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

            if dblocos.get(nome_bloco_substituir, None) is None:
                # Não existe bloco com o nome de campo variável. Despreza variável.
                print_log(passada, "Não foi encontrado bloco ", nome_bloco_substituir, "para substituir variável " + nome_campo_variavel)
                continue

            # Recupera lista de blocos do parágrafo
            lista_par_bloco = odt_clonar_bloco(nome_bloco_substituir, dblocos)

            # Localiza parágrafo pai onde está localizado a variável
            # uma vez que o parágrafo (inteiro) será substituido pelo conjunto de parágrafos do bloco
            # Atenção: Isto impede que um parágrafo contenha mais de uma variável
            paragrafo_substituir = odt_busca_ancestral_com_tipo(campo['pai'], raiz=odt_raiz,
                                                                         tipo='p')

            # Recupera elemento pai do parágrafo aonde aparece variável
            elemento_pai = odt_determinar_elemento_pai(paragrafo_substituir, odt_raiz)

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
                odt_substituir_paragrafo_por_lista(paragrafo_substituir, odt_raiz, lista_par_bloco)
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
    for table in office_text.findall('table:table', Gxml_ns):
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
    if (qtd_linhas != 2):
        # Não é comum ter mais de duas linhas...então é melhor avisar
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
    for table in office_text.findall('table:table', Gxml_ns):
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

    # Gera novo documento e encerra
    gera_novo_odt(odt_raiz, caminho_arquivo_saida_odt)

    return


def odt_remove_comentarios(base):
    global Gmodelo_configuracao
    #
    # Remove todos os comentários do documento gerado
    # Um comentário é um parágrafo iniciado por #
    lista_paragrafos = odt_recupera_lista_paragrafos(base)

    for p in lista_paragrafos:
        paragrafo = p["elemento"]
        texto = odt_obtem_texto_total_paragrafo(paragrafo)

        # Se começa por #, remove
        if len(texto) >= 1 and (texto[0] == "#"):
            pai = p["pai"]
            if len(texto) >= 3 and texto[1]=='@':
                #Linha de configuração do modelo
                texto=texto.replace('#@','')
                texto=texto.strip()
                Gmodelo_configuracao.append(texto)
                # Não remove parâmetro de configuração
                continue

            # Remove
            pai.remove(paragrafo)


def odt_remove_apos_fim_laudo(base):
    #
    # Remove todos os comentários do documento gerado
    # Um comentário é um parágrafo iniciado por #
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


def gera_novo_odt(odt_raiz, caminho_arquivo_saida_odt):
    #
    # Remove todos os comentários do documento gerado
    # Um comentário é um parágrafo iniciado por #
    odt_remove_comentarios(odt_raiz)

    # Remove qualquer coisa apos tag de finalização de laudo
    odt_remove_apos_fim_laudo(odt_raiz)

    # Gravar arquivo odt com conteúdo modificado
    # ------------------------------------------------------------------
    # Gera string do xml completo
    xml_string_alterado = xml.etree.ElementTree.tostring(odt_raiz, encoding="utf-8")

    # Remove content.xml do zip
    componente_trocar = "content.xml"
    remove_from_zip(caminho_arquivo_saida_odt, [componente_trocar])

    # Adiciona novo content.xml (modificado)
    with zipfile.ZipFile(caminho_arquivo_saida_odt, mode='a', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(componente_trocar, xml_string_alterado)

    print()
    print("- Laudo SAPI ajustado gravado em: ", caminho_arquivo_saida_odt)
    if pergunta_sim_nao("< Deseja abrir o arquivo de laudo para edição?"):
        webbrowser.open(caminho_arquivo_saida_odt)
        print("- Laudo SAPI foi aberto em programa compatível (normalmente libreoffice)")
        print("- Recomenda-se utilizar o LIBREOFFICE com versão superior a 5.2")

    return


# # Código para teste
# # **** Testar gravação de arquivo com substitução ****
# for c in root:
# 	# print(c.tag, c.attrib)
# 	#print(c.tag)
# 	#print(c.attrib)
# 	#die('ponto415')
# 	(ns, tag)=decompoe_ns_tag(c.tag)
# 	if (tag=='body'):
# 		office_body=c
#
# #print(elem_body)
#
# for c in office_body:
# 	#print(c.tag, c.attrib)
# 	(ns, tag)=decompoe_ns_tag(c.tag)
# 	print(tag)
# 	if (tag=='text'):
# 		office_text=c
#
# for c in office_text:
# 	(ns, tag)=decompoe_ns_tag(c.tag)
# 	print(ns)
# 	print(tag)
#    #print(c.tag)
#
# 	#print(c.tag, c.attrib)
# 	#(ns, tag)=decompoe_ns_tag(c.tag)
# 	#print(tag)
# 	#if (tag=='text'):
# 	#	office_text=c
#
#
#
# die('ponto421')
#
# #import xml.dom.minidom
#
# #xml = xml.dom.minidom.parseString(xml_string)
# #pretty_xml_as_string = xml.toprettyxml()
#
# #print(pretty_xml_as_string)
#
# #print(ElementTree_pretty.prettify(root))
#
# #print(prettify(root))
# #die('ponto408')
#
# #var_dump(doc)
#
# #print(doc)
# #print
# #print
# #print(prettify(doc))
#
#
# #import xml.dom.minidom
#
# #xml_x = xml.dom.minidom.parseString(xml_string)
# #pretty_xml_as_string = xml_x.toprettyxml()
# #print(pretty_xml_as_string)
# #die('ponto376')




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
        print("- Comando cancelado")
        return

    # ------------------------------------------------------------------------------------------------------------------
    # Verifica dados básicos do exame
    # ------------------------------------------------------------------------------------------------------------------
    print("- Verificando dados gerais do exame.")

    # Método de entrega
    metodo_entrega = Gsolicitacao_exame['dados_exame']['metodo_entrega']
    if metodo_entrega=='indefinido':
        print_centralizado(" ERRO ")
        print("- Para gerar o laudo você deve primeiramente definir o método de entrega (mídia óptica, cópia storage, etc).")
        print("- Configure no SETEC3 e em seguida retorne a esta opção.")
        return

    # ------------------------------------------------------------------------------------------------------------------
    # Seleciona o modelo do laudo
    # ------------------------------------------------------------------------------------------------------------------

    print()
    print("Passo 1: Selecione arquivo de laudo (modelo)")
    print("-------------------------------------------")
    print("- Informe o arquivo de modelo para o laudo no padrão SAPI, gerado no SisCrim.")
    print("- Na janela gráfica que foi aberta, selecione o arquivo .ODT correspodente")

    # Cria janela para seleção de laudo
    root = tkinter.Tk()
    j = JanelaTk(master=root)
    caminho_laudo = j.selecionar_arquivo([('ODT files', '*.odt')])
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
        print("- ATENÇÃO: Existem ", qtd_nao_pronto,
              "materiais que não estão prontos para laudo (ver coluna 'Pronto'), pois ainda possuem tarefas pendentes.")
        print("  Enquanto esta condição persistir, não será possível efetuar a geração de laudo (*GL)")
        print("- Em caso de dúvida, consulte o setec3 (comando *S3)")

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
        matricula = obter_laudo_parte1()
        return obter_laudo_parte2(matricula)
    except KeyboardInterrupt:
        print()
        print("- Operação interrompida pelo usuário <CTR><C>")
        return False


# Seleciona matricula
# ----------------------------------------------------------------------------------------------------------------------
def obter_laudo_parte1():

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

    # Obtem lista de itens, solicitando o memorando
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
            print("- Gere um modelo padrão sapi, por exemplo: GTPI/SAPI - Celular v2.0 (Geral)")
            continue
        elif (comando == '*gl'):
            gerar_laudo()
            continue

            # Loop de comando

    # Finaliza programa
    # Encerrando conexão com storage
    print()
    desconectar_todos_storages()

    # Finaliza
    print()
    print("FIM SAPI Laudo - Versão: ", Gversao)

if __name__ == '__main__':

    main()

    print()
    espera_enter("Programa finalizado. Pressione <ENTER> para fechar janela.")

