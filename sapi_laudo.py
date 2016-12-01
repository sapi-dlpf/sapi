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
# =======================================================================
# TODO: 
# - 
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
Gversao = "1.0"

# Para gravação de estado
Garquivo_estado = Gprograma + "v" + Gversao.replace('.', '_') + ".sapi"

# Base de dados (globais)
GdadosGerais = dict()  # Dicionário com dados gerais
Gitens = list()  # Lista de itens

# Diversos sem persistência
Gicor = 1
Glargura_tela = 129

# ------- Definição de comandos aceitos --------------
Gmenu_comandos = dict()
Gmenu_comandos['comandos'] = {
    # Comandos de navegacao
    '+': 'Navega para a tarefa seguinte da lista',
    '-': 'Navega para a tarefa anterior da lista',
    '*ir': 'Pula para a tarefa com sequencial indicado (ex: *ir 4, pula para a quarta tarefa da lista)',

    # Comandos relacionados com um item
    '*si': 'Exibe dados de laudo para o item corrente',
    '*du': 'Dump: Mostra todas as propriedades de uma tarefa (utilizado para Debug)',

    # Comandos gerais
    '*sg': 'Situação geral',
    '*gl': 'Gera laudo',
    '*qq': 'Finaliza'
}

Gmenu_comandos['cmd_navegacao'] = ["+", "-", "*ir"]
Gmenu_comandos['cmd_item'] = ["*si"]
Gmenu_comandos['cmd_geral'] = ["*sg", "*gl", "*qq"]

# Constantes para localização de seções do laudo
GsapiQuesitos = 'sapiQuesitos'
GsapiRespostas = 'sapiRespostas'

# Debug
Gverbose = True  # Aumenta a exibição de detalhes

# **********************************************************************
# PRODUCAO DEPLOYMENT AJUSTAR
# **********************************************************************

# Para código produtivo, o comando abaixo deve ser substituído pelo
# código integral de sapi_xxx.py, para evitar dependência
from sapilib_0_6 import *

# **********************************************************************
# PRODUCAO
# **********************************************************************

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
        self.directory = tkinter.filedialog.askdirectory()
        return self.directory


def get_clipboard():
    try:
        root = tkinter.Tk()
        root.withdraw()
        clip = root.clipboard_get()
    except BaseException as e:
        print("Nao foi possivel recuperado dados do clipboard: ", e)
        clip = ""

    return clip


def print_centralizado(texto='', tamanho=Glargura_tela, preenchimento='-'):
    direita = (tamanho - len(texto)) // 2
    esquerda = tamanho - len(texto) - direita
    print(preenchimento * direita + texto + preenchimento * esquerda)
    return


def exibir_secao_laudo(d):
    print("-" * 40, " Dados para laudo ", "-" * 40)

    lista_prop_descartar = ['nome', 'tipo']

    # Os dados para laudo estão estruturados em três níveis
    q = 0
    # Nível 1: categoria de dados (ex: 10-identificacao, 20-aquisicao)
    for categoria in sorted(d):
        q += 1
        # Pula linha
        if (q > 1):
            print()
        # print(str(q)+")",categoria)
        print(categoria)
        # Nível 2: Número sequencial que indica a qual componente diz
        # respeito os dados.
        for seq in sorted(d[categoria]):

            # O sequencial=0 contém dados gerais para a categoria
            # Por enquanto vamos desprezá-lo
            if (seq == '0'):
                continue

            # Imprime o nome do componente e tipo do componente
            print("  ", d[categoria][seq].get("nome", "*** nome indefinido ***"),
                  "(" + d[categoria][seq].get("tipo", "*** tipo indefinido ***") + ")")

            # Nível 3: Propriedades do componente
            for prop in sorted(d[categoria][seq]):

                # Descarta propriedades internas, que não servem
                # para conferência
                if (prop in lista_prop_descartar):
                    continue

                # Exibe campo para usuário
                print('    %12s : %s' % (prop, d[categoria][seq][prop]))

    print("-" * 100)

    # var_dump(d)

    return


# Exibe dados de laudo para um item
def exibir_dados_laudo_item(item):
    print()
    print("Exibição de dados de laudo para o item corrente")
    print("- Recuperando dados do servidor. Aguarde...")

    # Recupera as tarefas finalizadas de um item
    # ------------------------------------------------------------------
    (sucesso, msg_erro, tarefas) = sapisrv_chamar_programa(
        "sapisrv_obter_tarefas.php",
        {'codigo_solicitacao_exame_siscrim': GdadosGerais["codigo_solicitacao_exame_siscrim"],
         'item': item,
         'tipo': 'todos',
         'situacao': 'finalizada'
         })
    if (not sucesso):
        # Continua no loop
        print("Falha na busca de tarefas no servidor: ", msg_erro)
        return

    # ------------------------------------------------------------------
    # Exibe dados do item para usuário
    # ------------------------------------------------------------------
    dados_item = Gitens[obter_item_corrente()]
    print()
    print_centralizado("")
    print("Item: ", dados_item["item_apreensao"])
    print("Material: ", dados_item["material"])
    print("Descrição: ", dados_item["descricao"])
    print_centralizado("")

    # Exibe dados para laudo armazenados nas tarefas
    for t in tarefas:
        # var_dump(t["tarefa"]["dados_relevantes_json"])
        dados_relevantes_json = json.loads(t["tarefa"]["dados_relevantes_json"])
        dados_laudo = dados_relevantes_json["laudo"]
        # var_dump(dados_laudo)
        exibir_secao_laudo(dados_laudo)

    return


# Exibe dados de laudo para o item corrente
def exibir_dados_laudo_item_corrente():
    item = Gitens[obter_item_corrente()]["item"]
    # var_dump(item)
    # die('ponto609')
    exibir_dados_laudo_item(item)


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


def odt_busca_ancestral_com_tipo(elemento, raiz, tipo):
    # mapeamento de pai filho, para poder subir para o ancestral
    filho_para_pai = {
        c: p for p in raiz.iter() for c in p
        }

    ancestral = elemento
    while (True):
        tipo_ancestral = odt_get_tipo(ancestral)
        if (tipo_ancestral == tipo):
            return ancestral

        # Sobe para pai
        ancestral = filho_para_pai.get(ancestral, None)
        if (ancestral is None):
            # Chegou no topo, e não encontrou sapiCampoVar
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
                print_tela_log("Bloco [", nome_bloco, "] foi iniciado mas não foi concluído (", bloco_fim, ")")
                # Fracasso
                return (False, {})
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
                print_tela_log("Bloco [", nome_bloco, "] está duplicado")
                print(texto)
                # Fracasso
                return (False, {})

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
                print_tela_log(
                    "- Bloco finalizado em ser iniciado. Procure no texto por um '" + bloco_fim + "' sobrando")
                # Fracasso
                return (False, {})

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

    # die('ponto1063')

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
    # var_dump(dadosItem)
    # die('ponto1099')

    print_tela_log("- Recuperando dados para laudo das tarefas do item ", item)
    param = {'codigo_solicitacao_exame_siscrim': GdadosGerais["codigo_solicitacao_exame_siscrim"],
             'item': item,
             'tipo': 'todos',
             'situacao': 'finalizada'}
    if fase is not None:
        param['fase'] = fase
    (sucesso, msg_erro, tarefas) = sapisrv_chamar_programa(
        "sapisrv_obter_tarefas.php", param, registrar_log=Gverbose)
    if (not sucesso):
        print_tela_log("ERRO: Falha na busca de tarefas no servidor: ", msg_erro)
        return

    # Exibe dados para laudo armazenados nas tarefas
    for t in tarefas:
        # var_dump(t["tarefa"]["dados_relevantes_json"])
        dados_relevantes_json = json.loads(t["tarefa"]["dados_relevantes_json"])
        dados_laudo = dados_relevantes_json["laudo"]
        lista_dados_laudo.append(dados_laudo)
    # var_dump(dados_laudo)
    # var_dump(dados_laudo)
    # die('ponto1292')

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
            tipo = dados_componente['sapiTipoComponente']

            # Recupera bloco de identificação específico
            # para o tipo de componente
            # (ex: sapiIdentificacaoAparelho, sapiIdentificacaoSim)
            nome_bloco_componente = "sapiIdentificacao" + tipo
            bloco = dblocos.get(nome_bloco_componente.lower(), None)
            if bloco is None:
                print_tela_log("Erro: Não foi localizado bloco com nome[", nome_bloco_componente,
                               "] no seu documento. Confira/corrija. (Esclarecimento: Nome do bloco NÃO é case sensitive)")
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
                # odt_dump(novo_paragrafo)
                # var_dump(lista_cv)
                # die('ponto1358')

                # Substitui campos variáveis no parágrafo
                for substituir in dados_componente:
                    valor = dados_componente[substituir]
                    # var_dump(substituir)
                    # var_dump(valor)
                    # die('ponto1370')
                    odt_substitui_campo_variavel_texto(lista_cv, substituir, valor)
                    # odt_dump(novo_paragrafo)
                    # die('ponto1375')

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

    # var_dump(listaDadosLaudo)
    # die('ponto1486')

    for dados_tarefa in lista_dados_laudo:

        sapi_hashes = dados_tarefa.get('sapiHashes', None)
        if (sapi_hashes is None):
            # Tarefa não possui dados de hash
            continue

        # Processa a lista de hashes, gerando uma linha para cada hash
        for h in sapi_hashes:

            # var_dump(h)
            # die('ponto1498')

            # Duplica modelo para criar nova linha
            tr_nova_linha_item = copy.deepcopy(tr_modelo)

            # Mapeamento filho para pai na nova linha
            # Precisa disto???
            # filho_para_pai_tr_nova_linha_item_map = {
            #     c:p for p in tr_nova_linha_item.iter() for c in p
            #     }

            # Procura por campos de substiuição na nova linha
            (sucesso, lista_cv_tr_nova_linha_item) = odt_recupera_lista_campos_variaveis_sapi(tr_nova_linha_item)

            # Adiciona item na descrição do hash
            descricao = "Item " + dados_item['item'] + " - " + h["sapiHashDescricao"]

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


def odt_clonar_bloco(nome_bloco, dblocos):
    lista_par = []

    bloco = dblocos.get(nome_bloco.lower(), None)
    if (bloco is None):
        erro_fatal("Erro: Não foi localizado bloco com nome[", nome_bloco, "] odt_clonar_bloco")

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
            print_tela_log("- Encontrada quesitação e resposta com label '" + q + "'")
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
            # Ajusta string
            texto = odt_obtem_texto_total_paragrafo(p)
            # Ajusta e sintetiza
            texto = filtra_apenas_ascii(texto)
            # print(texto)
            parte_inicial = texto[0:32].strip(' .')
            parte_inicial = parte_inicial + '.' * (34 - len(parte_inicial)) + " "
            # print(len(parte_inicial))
            # Adiciona ao texto resumo
            resumo_quesitos = resumo_quesitos + parte_inicial
            qtd_quesitos += 1

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
def usuario_escolhe_quesitacao(quesitos_respostas):
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
    print("-" * 110)
    aviso1 = '''
Observe na lista abaixo o resumo dos modelos de quesitos e selecione o mais adequado.
Em função de problemas de acentuação, é possível que alguns caracteres acentuados tenham sido substituídos por '.' no resumo abaixo.
Contudo, no laudo gerado (.odt) os caracteres acentuados serão exibidos corretamente.
'''
    aviso2 = '''
Caso a quesitação do memorando não seja idêntica a nenhuma das quesitações padrões,
selecione a que possuir maior semelhança, efetue os ajustes no seu laudo,
e por fim notique o gestor do GTPI (informando o número do laudo), para que este avalie a necessidade de ampliação dos modelos de quesitação.
'''

    print(formata_frases(aviso1, 105))
    print()
    print(formata_frases(aviso2, 105))

    qtd_opcoes = 0
    for qtd_nome in lista:

        qtd_opcoes += 1

        # Separa o nome da chave de ordenação e recupera quesitação
        nome_quesito = qtd_nome.split("^")[1]
        quesitacao = quesitos_respostas[nome_quesito]
        resumo_quesitos = quesitacao["resumo_quesitos"]
        # var_dump(quesitacao)
        quantidade_quesitos = quesitacao["quantidade_quesitos"]

        print_centralizado("")
        print(qtd_opcoes, ":", int(quantidade_quesitos), "quesitos (nome do bloco: ", nome_quesito, ")")
        print_centralizado("")
        # Imprime o resumo de três quesitos por linha
        tam_linha = 105
        for i in range(0, len(resumo_quesitos), tam_linha):
            print("  ", resumo_quesitos[i:i + tam_linha])

    # Solicita o número de sequencia da quesitação
    while True:
        pergunta = "Digite o número de sequencia da quesitação escolhida (1 a " + str(qtd_opcoes) + "): "
        print()
        seq = input(pergunta)
        seq = seq.strip()

        # Verifica se número de sequencia é válido
        if not seq.isdigit(): continue
        seq = int(seq)
        if (seq < 1): continue
        if (seq > qtd_opcoes): continue

        # Retorna definição de  quesitos e respostas
        nome_quesitacao = lista[seq - 1].split("^")[1]
        quesitacao_selecionada = quesitos_respostas[nome_quesitacao]
        return quesitacao_selecionada


def determina_quesitacao(quesitos_respostas, dblocos):
    # Usuário escolhe quesitação, em modo interativo
    quesitacao_selecionada = usuario_escolhe_quesitacao(quesitos_respostas)

    nome_bloco_quesitos = quesitacao_selecionada["nome_bloco_quesitos"]
    nome_bloco_respostas = quesitacao_selecionada["nome_bloco_respostas"]

    # Recupera listas de parágrafos das perguntas e respostas
    lista_par_quesitos = odt_clonar_bloco(nome_bloco_quesitos, dblocos)
    lista_par_respostas = odt_clonar_bloco(nome_bloco_respostas, dblocos)

    return lista_par_quesitos, lista_par_respostas


# Recebe o arquivo de entrada, sendo este um arquivo
# odt gerado a partir de um modelo SAPI no sisCrim.
#
# Gera um novo arquivo odt, substituindo os elementos sapi
# por dados coletados durante as tarefas sapi executadas.
#
# Retorna o caminho para o arquivo de saída
# ----------------------------------------------------------------------
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

    print_tela_log("- Copiando arquivo para: " + caminho_arquivo_saida_odt)

    try:
        # Tenta duplicar arquivo, para equivalente com extensão SAPI
        shutil.copyfile(caminho_arquivo_entrada_odt, caminho_arquivo_saida_odt)
    except BaseException as e:
        print_tela_log("- ERRO: Criação do arquivo de destino '" + caminho_arquivo_saida_odt + "'")
        print_tela_log("- ERRO: ", e)
        print_tela_log(
            "- Verifique se arquivo não está aberto, ou se existe alguma outra condição que possa estar impedindo a sua criação")
        return None

    shutil.copyfile(caminho_arquivo_entrada_odt, caminho_arquivo_saida_odt)
    print_tela_log("- Todos os ajustes serão feitos no arquivo de saída. O arquivo de entrada não será alterado")

    # -------------------------------------------------------------------
    # Extrai arquivo de conteúdo (content.xml) do odt
    # -------------------------------------------------------------------

    # Um arquivo ODT é um ZIP contendo arquivos XML
    # Logo, primeiriamente é necessário abrir o zip
    print_tela_log("- Unzipando arquivo de saída")
    zf = zipfile.ZipFile(caminho_arquivo_saida_odt, 'r')
    # listarArquivos(zf)
    # exibirInfo(zf)

    # Cria pasta temporária para extrair arquivo
    pasta_tmp = tempfile.mkdtemp()

    # O conteúdo propriamente dito do arquivo ODT
    # está armazenado no arquivo content.xml
    arq_content_xml = "content.xml"
    if (arq_content_xml in zf.namelist()):
        print_tela_log("- OK, arquivo contém " + arq_content_xml)
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
        print_tela_log("- Extraído arquivo de conteúdo (content.xml) com sucesso para [", caminho_arq_content_xml, "]")
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
            "Falhou no parse dos namespaces. Não encontrado seção 'text'. Assegure-se que o arquivo informado é um ODT bem formado")
        return

    # Faz parse geral do arquivo, que já foi lido e armazenado em string
    odt_raiz = xml.etree.ElementTree.fromstring(xml_string)

    # Antes de mais nada, vamos remover todos os comentários
    # Um comentário é um parágrafo iniciado por #
    odt_remove_comentarios(odt_raiz)

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

    print_tela_log("- Recuperando e validando referência a campos variáveis")
    (sucesso, lista_cv_office_text) = odt_recupera_lista_campos_variaveis_sapi(office_text)
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
        erro_fatal("Falha no parse de blocos")

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

    # ------------------------------------------------------------------
    # Substitui textos gerais do corpo do laudo
    # ------------------------------------------------------------------

    print_tela_log("Substituindo campos gerais do Laudo")

    # Recupera dados gerais da solicitação de exame
    # ------------------------------------------------------------------
    (sucesso, msg_erro, solicitacao) = sapisrv_chamar_programa(
        "sapisrv_consultar_solicitacao_exame.php",
        {'codigo_solicitacao_exame_siscrim': GdadosGerais["codigo_solicitacao_exame_siscrim"]
         })
    if (not sucesso):
        # Continua no loop
        print("Falha na busca de dados da solicitação de exame no servidor: ", msg_erro)
        return

    # Monta dicionário de substituição
    dsub = dict()
    dsub['sapiAlvo'] = solicitacao["local_busca"]
    dsub['sapiAlvo'] = solicitacao["local_busca"]

    # Substitui cada componente
    for substituir in dsub:

        # Efetua substituição de texto
        novo_valor = dsub[substituir]
        qtd_substituicoes = odt_substitui_campo_variavel_texto(lista_cv_office_text, substituir, novo_valor)
        if (qtd_substituicoes == 0):
            print("Falhou na substituição de '" + substituir + "'")
            return

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
    lista_par_quesitos, lista_par_respostas = determina_quesitacao(quesitos_respostas, dblocos)

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
        print_tela_log("ERRO: Não encontrado parágrafo onde se localiza 'sapiQuesitos'")
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
        print_tela_log("ERRO: Não encontrado parágrafo onde se localiza '" + GsapiRespostas + "'")
        return

    odt_substituir_paragrafo_por_lista(paragrafo_substituir_sapi_respostas, odt_raiz, lista_par_respostas)

    # ------------------------------------------------------------------------------------------------------------------
    # Geração de tabela de hash
    # ------------------------------------------------------------------------------------------------------------------

    # Procura tabela de hashes
    # ---------------------------
    tabela_hashes = None
    for table in office_text.findall('table:table', Gxml_ns):
        nome_tabela = obtem_atributo_xml(table, 'table:name')
        if (nome_tabela == 'tabela_hashes'):
            print_tela_log("- Localizada tabela de hashes")
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
    print_tela_log("- Recuperando campos variáveis da tabela de hashes")
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
    for dadosItem in Gitens:

        item = dadosItem['item']

        print_tela_log("- Tabela de hashes. Processando item ", item)

        # Processa item, gerando uma ou mais linhas de hash
        linhas_hash = criar_linhas_hash_para_item(tr_modelo_linha_hash, dadosItem)

        for linha in linhas_hash:
            # Insere nova linha na tabela de hashes
            tabela_hashes.insert(posicao_inserir_tab_hashes, linha)
            posicao_inserir_tab_hashes += 1

    # --- Fim do loop de processamento dos itens da tabela de hashes
    # Remove linha de modelo da tabela
    tabela_hashes.remove(tr_modelo_linha_hash)

    # -------------------------------------------------------------------
    # Geração de tabela de materiais examinados
    # -------------------------------------------------------------------

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

    # print(tabela_materiais)
    # die('ponto1223')

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
    print_tela_log("- Recuperando campos variáveis da tabela de materiais")
    (sucesso, lista_cv_tabela_materiais) = odt_recupera_lista_campos_variaveis_sapi(tr_modelo)
    if (len(lista_cv_tabela_materiais) == 0):
        print_tela_log(
            "ERRO: Não foi detectado nenhum campo variável na tabela de materiais. Assegure-se de utilizar um modelo de ODT sapi para a geração do laudo")
        return

        # ------------------------------------------------------------------
        # Gera linhas na tabela de materiais para cada um dos itens
        # ------------------------------------------------------------------

        # Monta lista de itens ordenados
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

    q = 0
    for dadosItem in Gitens:
        q += 1

        item = dadosItem['item']
        print_tela_log("- Processando item ", item)

        # Processa item, criando nova linha na tabela de materiais
        tr_nova_linha_item = criar_linha_para_item(tr_modelo, dadosItem, dblocos)

        # Insere nova linha na tabela de materiais
        tab_materiais.insert(posicao_inserir_tab_materiais, tr_nova_linha_item)
        posicao_inserir_tab_materiais += 1

    # --- Fim do loop de processamento dos itens da tabela de materiais
    # Remove linha de modelo da tabela de materiais
    tab_materiais.remove(tr_modelo)

    # Gera novo documento e encerra
    gera_novo_odt(odt_raiz, caminho_arquivo_saida_odt)


def odt_remove_comentarios(base):
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
            pai.remove(paragrafo)


def gera_novo_odt(odt_raiz, caminho_arquivo_saida_odt):
    #
    # Remove todos os comentários do documento gerado
    # Um comentário é um parágrafo iniciado por #
    odt_remove_comentarios(odt_raiz)

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

    print("Novo arquivo gravado em: ", caminho_arquivo_saida_odt)
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


# Gera laudo
# ----------------------------------------------------------------------------------------------------------------------
def gerar_laudo():
    # Fazendo teste...com modelo de laudo fixo
    print("Em modo de desenvolvimento...desviando para teste1()")
    caminho_laudo = "D:/Exames_andamento/memorando 1086_16 celulares/Laudo_2122_2016_SETEC_SR_PF_PR (23).odt"
    ajustar_laudo_odt(caminho_laudo)
    return

    # ------------------------------------------------------------------------------------------------------------------
    # Seleciona o modelo do laudo
    # ------------------------------------------------------------------------------------------------------------------
    while True:

        # Loop para selecionar arquivo
        selecionada_pasta = False
        while not selecionada_pasta:
            print()
            print("2) Modelo do Laudo")
            print("- Entre no SisCrim e gere para o laudo informado um modelo SAPI.")
            print("- Na janela gráfica que foi aberta, informe o arquivo .ODT do modelo do laudo.")

            # Cria janela para seleção de laudo
            root = tkinter.Tk()
            j = Janela(master=root)
            caminho_laudo = j.selecionar_arquivo()
            root.destroy()

            # Exibe a pasta obtida do clipboard, para usuário conferir
            print("- Arquivo do modelo do laudo: ", caminho_laudo)
            print()
            selecionada_pasta = pergunta_sim_nao("Prosseguir? ", default="n")

        # Verificação básica do arquivo
        # if not validaModeloLaudo(pasta=caminho_laudo, explicar=True):
        #     Pede novamente a pasta
        #     continue

        # Ok, tudo certo
        print()
        print("Pasta de origem contém arquivos típicos de uma extração do Cellebrite.")
        break


# Exibe lista de tarefas
# ----------------------------------------------------------------------------------------------------------------------
def exibir_situacao():
    cls()

    # Exibe cabecalho (Memorando/protocolo)
    print(GdadosGerais["identificacaoLaudo"])
    print('-' * 129)

    # Lista de itens
    q = 0
    for i in Gitens:
        q += 1

        # Sinalizador de Corrente
        corrente = "  "
        if (q == Gicor):
            corrente = '=>'

        # var_dump(i)
        # cabecalho
        if (q == 1):
            print('%2s %2s %15s %-101.101s' % (" ", "Sq", "Material", "Item : Descrição"))
            print('-' * 129)
        # Tarefa
        item_descricao = i["item"] + " : " + i["descricao"]
        print('%2s %2s %15s %-101.101s' % (corrente, q, i["material"], item_descricao))

        if (q == Gicor):
            print('-' * 129)

    print()
    if (q == 0):
        print("Não existe nenhum item pronto para laudo nesta solicitação de exame.")
    else:
        print("A lista acima apresenta apenas os itens da solicitação de exame que estão prontos para laudo.")
    print(
        "Um item está pronto para laudo quando todas as tarefas programadas para o mesmo foram concluídas com êxito.")
    print("Em caso de dúvida, consulte o setec3")
    print()
    return


# Salva situação atual para arquivo
# ----------------------------------------------------------------------
def salvar_estado():
    # Monta dicionario de estado
    estado = dict()
    estado["Gitens"] = Gitens
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
    global Gitens
    global GdadosGerais

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


# Seleciona laudo
# ----------------------------------------------------------------------
def obter_laudo_itens():
    print()

    # Solicita que o usuário se identifique através da matricula
    # ----------------------------------------------------------
    lista_laudos = list()
    while True:
        matricula = input("Entre com sua matrícula: ")
        matricula = matricula.lower().strip()

        if (matricula == ''):
            print("Nenhuma matrícula informada. Programa finalizado.")
            sys.exit()

        if (not matricula.isdigit()):
            print("Matrícula deve ser campo numérico (ex: 15123).")
            continue

        (sucesso, msg_erro, lista_laudos) = sapisrv_chamar_programa(
            "sapisrv_obter_laudos_pcf.php",
            {'matricula': matricula})

        # Insucesso....normalmente matricula incorreta
        if (not sucesso):
            # Continua no loop
            print("Erro: ", msg_erro)
            continue

        # Matricula ok, vamos ver se tem solicitacoes de exame
        if (len(lista_laudos) == 0):
            print("Não existe nenhum laudo para exame SAPI na carga da matrícula indicada. Verifique no SisCrim")
            continue

        # Tudo certo, encerra loop
        break

    # Exibe lista de laudos do usuário
    # -----------------------------------------------
    print()
    q = 0
    for d in lista_laudos:
        q += 1
        if (q == 1):
            # Cabecalho
            print('%2s  %10s %10s  %s' % ("N.", "Laudo", "Protocolo", "Solicitação de exame"))
            print('-' * 129)
        protocolo_ano = d["numero_protocolo"] + "/" + d["ano_protocolo"]
        laudo_ano = d["numero_documento"] + "/" + d["ano_documento"]
        # var_dump(d)
        # die('ponto1961')
        print('%2d  %10s %10s  %s' % (q, laudo_ano, protocolo_ano, d["identificacao"]))

    # Usuário escolhe a solicitação de exame de interesse
    # --------------------------------------------------------
    itens = list()
    while True:
        #
        print()
        num_solicitacao = input("Selecione o laudo (pelo número de sequencia): ")
        num_solicitacao = num_solicitacao.strip()
        if not num_solicitacao.isdigit():
            print("Entre com o numero do laudo")
            continue

        # Verifica se existe na lista
        num_solicitacao = int(num_solicitacao)
        if not (1 <= num_solicitacao <= len(lista_laudos)):
            # Número não é válido
            print("Entre com o numero do laudo, entre 1 e ", str(len(lista_laudos)))
            continue

        ix_solicitacao = int(num_solicitacao) - 1

        # Ok, selecionado
        print()
        laudo = lista_laudos[ix_solicitacao]
        GdadosGerais["identificacaoLaudo"] = (
            "Laudo: " +
            laudo["numero_documento"] + "/" + laudo["ano_documento"] +
            " Solicitação: " +
            laudo["identificacao"] +
            " Protocolo: " +
            laudo["numero_protocolo"] + "/" + laudo["ano_protocolo"])
        # print("Laudo:",solicitacao["identificacao"])
        # var_dump(GdadosGerais["identificacaoLaudo"])
        # die('ponto2001')

        print("Buscando itens prontos para " + GdadosGerais["identificacaoLaudo"])
        print("Aguarde...")

        # Carrega os itens que estão pronto para laudo
        # --------------------------------------------------------------
        codigo_solicitacao_exame_siscrim = laudo["codigo_documento_externo"]
        GdadosGerais["codigo_solicitacao_exame_siscrim"] = codigo_solicitacao_exame_siscrim

        (sucesso, msg_erro, itens) = sapisrv_chamar_programa(
            "sapisrv_obter_itens_laudo.php",
            {'codigo_solicitacao_exame_siscrim': codigo_solicitacao_exame_siscrim},
            abortar_insucesso=True
        )

        # var_dump(sucesso)
        # var_dump(msg_erro)
        # var_dump(itens)
        # die('ponto2022')

        # Tem que ter ao menos um item pronto para laudo
        if (len(itens) == 0):
            print()
            print("A solicitação de exame deste laudo NÃO TEM NENHUM ITEM PRONTO PARA LAUDO")
            print("Verifique no SETEC3.")
            print()
            continue

        # Confirma se itens que estão disponíveis atende expectativa
        # -----------------------------------------------
        print()
        print()
        q = 0
        for item in itens:
            # var_dump(item)
            # die('ponto2028')
            q += 1
            if (q == 1):
                # Cabecalho
                print('%10s %s' % ("item", "Descrição"))
                print('-' * 129)
            print('%10s %s' % (item["item"], item["descricao"]))

        print()
        print("Total de itens disponíveis para laudo: ", q)
        print()
        print()

        # Confirma se lista está ok
        print()
        prosseguir = pergunta_sim_nao("Prosseguir? ", default="n")
        if not prosseguir:
            continue

        # Tudo certo, encerra loop
        sys.stdout.write("OK")
        break

    # Retorna itens para o memorando selecionado
    return itens


def refresh_itens():
    # Irá atualizar a variável global de itens
    global Gitens

    print("Buscando situação atualizada do servidor. Aguarde...")

    codigo_solicitacao_exame_siscrim = GdadosGerais["codigo_solicitacao_exame_siscrim"]

    # Carrega os itens que estão pronto para laudo
    # --------------------------------------------------------------
    (sucesso, msg_erro, itens) = sapisrv_chamar_programa(
        "sapisrv_obter_itens_laudo.php",
        {'codigo_solicitacao_exame_siscrim': codigo_solicitacao_exame_siscrim},
        abortar_insucesso=True
    )

    # Guarda na global
    Gitens = itens


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


# ======================================================================
# Código para teste
# ======================================================================

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

if __name__ == '__main__':

    # Iniciando
    # ---------
    print()
    print(Gprograma, " (Versao " + Gversao + ")")
    print_centralizado("")
    print()
    print("Dicas:")
    print(
        "- Se a linha de separador ---- está sendo quebrada, configure o buffer de tela e tamanho de janela com largura de 130 caracteres")
    print("  para ter uma visualização perfeita.")
    print("- Para interromper entrada de dados, utilize CTR-C")
    print()

    # Inicialização de sapilib
    print_log('Iniciando ', Gprograma, ' - ', Gversao)
    sapisrv_inicializar(Gprograma, Gversao)

    # Obtem lista de itens que irão para o laudo
    # ------------------------------------------
    carregar_estado()
    if (len(Gitens) == 0):
        # Se não carregou nada, solicita laudo
        Gitens = obter_laudo_itens()
    # Salva estado atual
    salvar_estado()

    # Apenas em teste...para ir direto
    # debug
    # ============= Reabilitar após revisão de sapilib 0.6
    # gerarLaudo()
    # die('ponto1304')

    # Processamento
    # ---------------------------
    exibir_situacao()

    # Recebe comandos
    while (True):
        (comando, argumento) = interface_receber_comando_ok(Gmenu_comandos)

        if comando == '':
            # Se usuário simplemeste der um <ENTER>, exibe a situação
            exibir_situacao()
            continue

        if (comando == '*qq'):
            print("Finalizado por comando do usuario")
            salvar_estado()
            break

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
            exibir_dados_laudo_item_corrente()
            continue

        # Comandos gerais
        if (comando == '*sg'):
            refresh_itens()
            exibir_situacao()
            continue
        elif (comando == '*gl'):
            gerar_laudo()
            continue

            # Loop de comando

    # Finaliza
    print()
    print("FIM ", Gprograma, " (Versão ", Gversao, ")")
