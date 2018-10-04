# -*- coding: utf-8 -*-
#
# ===== PYTHON 3 ======
#
# =======================================================================
# SAPI - Sistema de Apoio a Procedimentos de Informática
# 
# Componente: sapi_storage
# Objetivo: Agente para apoio na utilização de storages pelo SAPI
# Funcionalidades:
#  - Validação de dados de conexão
#  - Registro de storage
# Histórico:
#  - v2.0 : Inicial
# ======================================================================================================================

# Módulos utilizados
# ====================================================================================================
import platform
import sys
import xml.etree.ElementTree as ElementTree
import multiprocessing
import signal
import uuid

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
Gprograma = "sapi_storage"
Gversao = "2.0"

# Links para wiki
Gwiki_sapi = "http://setecpr.dpf.gov.br/wiki/index.php/SAPI_Manual_de_instalação_e_configuração"
Gwiki_storage = "http://setecpr.dpf.gov.br/wiki/index.php/Configurar_Storage_SAPI"
Gwiki_admin = "Administrador_SAPI"

# Pastas
Gpasta_tmp = "tmp_sapi_storage"

# Base de dados (globais)
GdadosGerais = dict()  # Dicionário com dados gerais
Gstorages = list()  # Lista de storages
Gconf_novo_storage = dict()

# Diversos sem persistência
Gicor = 1

# Controle de frequencia de atualizacao
GtempoEntreAtualizacoesStatus = 180  # Tempo normal de produção
# GtempoEntreAtualizacoesStatus = 10  # Debug: Gerar bastante log

# ------- Definição de comandos aceitos --------------
Gmenu_comandos = dict()
Gmenu_comandos['comandos'] = {
    # Comandos de navegação
    '+': 'Navegar para a storage seguinte da lista',
    '-': 'Navegar para a storage anterior da lista',

    # Comandos relacionados com a storage corrente
    '*con': 'Exibir configuração do storage',
    '*alt': 'Alterar configuração do storage',
    '*tst': 'Validar configuração do storage',
    '*sto': 'Conectar com storage para consulta',
    '*du': '(Dump) Mostrar todas as propriedades de uma storage (utilizado para Debug)',

    # Comandos exibição
    '*sg': 'Exibir situação atualizada dos storages registrados',

    # Comandos gerais
    '*inc': 'Incluir um novo storage',
    '*qq': 'Finalizar',

    # Comandos para diagnóstico de problemas
    '*log': 'Exibir log geral desta instância do sapi_storage. Utiliza argumento como filtro (exe: *log status => Exibe apenas registros de log contendo o string "status".',
    '*db': 'Ligar/desligar modo debug. No modo debug serão geradas mensagens adicionais no log.'

}

Gmenu_comandos['cmd_exibicao'] = ["*sg"]
Gmenu_comandos['cmd_navegacao'] = ["+", "-"]
Gmenu_comandos['cmd_item'] = ["*con", "*tst", "*alt", "*sto"]
Gmenu_comandos['cmd_geral'] = ["*inc", "*qq"]
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

# Recupera os componentes da storage correntes e retorna em tupla
# ----------------------------------------------------------------------
def obter_storage_corrente():
    # Não tem storage na lista
    if len(Gstorages)==0:
        return (None, None)

    return Gstorages[Gicor - 1]


# Exibe dados gerais da storage e item, para conferência do usuário
def exibe_dados_storage(storage):

    #var_dump(storage)

    print()
    print_centralizado(" Storage " + str(storage["storage_id"]))

    # Dados cadastrais do storage
    print("──── ","Dados cadastrais"," ────")
    print_formulario(label="Código do storage", largura_label=20, valor=storage.get("codigo_sapi_storage", ""))
    print_formulario(label="Storage id", largura_label=20, valor=storage.get("storage_id", ""))
    print_formulario(label="Descrição", largura_label=20, valor=storage["descricao"])
    print_formulario(label="Tipo", largura_label=20, valor=storage["tipo"])
    print_formulario(label="Habilitado", valor=storage['habilitado'])
    print_formulario(label="Data hora criação", largura_label=20, valor=storage["data_hora_criacao"])
    print()

    cfg=storage['configuracao']
    exibe_configuracao_storage(cfg)


# Exibe configuração do storage
def exibe_configuracao_storage(cfg, titulo="Configuração", completa=False):
    print("──── ",titulo," ────")
    print_formulario(label="storage_id", largura_label=20, valor=cfg.get("storage_id", ""))
    if completa: print_formulario(label="descricao", largura_label=20, valor=cfg.get("descricao", ""))
    print_formulario(label="IP", largura_label=20, valor=cfg.get("maquina_ip", ""))
    print_formulario(label="Nome netbios", largura_label=20, valor=cfg.get("maquina_netbios",""))
    print_formulario(label="Share", largura_label=20, valor=cfg.get("pasta_share",""))
    print_formulario(label="usuario", largura_label=20, valor=cfg.get("usuario",""))
    print_formulario(label="senha", largura_label=20, valor=cfg.get("senha",""))
    print_formulario(label="usuario_consulta", largura_label=20, valor=cfg.get("usuario_consulta",""))
    print_formulario(label="senha_consulta", largura_label=20, valor=cfg.get("senha_consulta",""))
    print_centralizado("")
    print()

# ---------------------------------------------------------------------------------------------------------------------
# Diversas funções de apoio
# ---------------------------------------------------------------------------------------------------------------------

def carrega_exibe_storage_corrente(exibir=True):

    # Recupera storage corrente
    storage = obter_storage_corrente()
    if storage is None:
        print("- Não existe nenhum storage corrente. Utilize *SG para dar refresh na lista de storages")
        return None

    # Ok, storage recuperado, exibe dados
    # ------------------------------------------------------------------
    if exibir:
        exibe_dados_storage(storage)

    # Retorna dados da storage
    return storage



# ======================================================================================================================
# @*sto - Exibe pasta do storage invocando o File Explorer
# ======================================================================================================================
def exibir_pasta_storage_file_explorer():

    print()
    print("- Exibir pasta no storage")
    print()

    storage=carrega_exibe_storage_corrente(exibir=False)
    if storage is None:
        return False

    # Montagem de storage
    # -------------------
    ponto_montagem = conectar_storage_consulta_ok(storage["configuracao"])
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        return

    # Determina a pasta
    pasta=ponto_montagem

    # Abre pasta no File Explorers
    print("- Abrindo pasta no programa File Explorer do Windows")
    os.startfile(pasta)
    print("- Pasta foi aberta no File Explorer")


# ======================================================================================================================
# @*tst - Validar configuração do storage corrente
# ======================================================================================================================
def validar_storage_corrente():

    print()
    print("- Validar configuração do storage corrente")
    print()

    storage=carrega_exibe_storage_corrente(exibir=True)
    if storage is None:
        return False

    # Extrai configuração
    cfg=storage['configuracao']

    #var_dump(cfg)
    #die('ponto220')

    print()
    print("- Iniciando validação do storage. Aguarde....")
    valido=validar_configuracao_storage(cfg)

    # Exibe resultado final
    print()
    print_centralizado("-")
    if valido:
        print("- Configuração do storage validada com SUCESSO")
    else:
        print("- ERRO: Configuração inválida")

    return


# ======================================================================================================================
# @*alt - Alterar configuração do storage corrente
# ======================================================================================================================
def alterar_storage_corrente():

    print()
    print("- Alterar configuração do storage corrente")
    print()

    storage=carrega_exibe_storage_corrente(exibir=True)
    if storage is None:
        return False

    # Extrai configuração
    cfg=storage['configuracao']

    # Entra em modo de edição
    # Se tudo der certo, a nova configuração será gravada
    return editar_storage(cfg)

def refresh_exibir_situacao():
    refresh_storages()
    exibir_situacao()
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
    print(GdadosGerais.get("pcf", None), "|",
          GdadosGerais.get("unidade_sigla", None), "|",
          GdadosGerais.get("data_hora_ultima_atualizacao_status", None), "|",
          Gprograma + str(Gversao),
          ambiente)
    print_centralizado()

# Exibe lista de storages
# ----------------------------------------------------------------------
def exibir_situacao(comando=''):

    global Gicor

    # Antes de mais nada, sanitiza Gicor no range de storages
    # É possível que uma exclusão de storage tenha feito o Gicor ficar maior que o tamanho da lista
    # de storages
    if Gicor>len(Gstorages):
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
    for storage in Gstorages:
        q += 1

        # Sinalizador de Corrente
        corrente = "  "
        if (q == Gicor):
            corrente = '=>'

        # Calcula largura da última coluna, que é variável (item : Descrição)
        # Esta constantes que está sendo subtraida é a soma de todos os campos e espaços antes do campo "Item : Descrição"
        lid = Glargura_tela - 40
        lid_formatado = "%-" + str(lid) + "." + str(lid) + "s"

        string_formatacao = '%2s %2s %20s %10s ' + lid_formatado

        habilitado="Sim"
        if int(storage["habilitado"])==0:
            habilitado="Não"

        # cabecalho
        if (q == 1):
            print(string_formatacao % (
                " ", "Sq", "storage".center(20), "habilitado", "Descricao"))
            print_centralizado()
        print(string_formatacao % (
            corrente, q, storage["storage_id"].center(20), habilitado.center(10), storage["descricao"]))

        if (q == Gicor):
            print_centralizado()

    print_centralizado()

    # Não tem nenhum elmento
    if q==0:
        print("*** Não existe nenhum storage registrado na sua unidade de lotação ***")
        print()
        print("- Para registar um storage, utilize o comando *inc")
        print()
        return

    print()
    if comando=='':
        print("- Para recuperar a situação atualizada do servidor (Refresh), utilize os comando *SG")
        print("- Para registrar um novo storage, utilize o comando *inc")

    return


def refresh_storages():
    # Irá atualizar a variável global de storages
    global Gstorages
    global GdadosGerais
    global Gicor

    print()
    print("- Consultando situação de storages no SETEC3 para unidade. Aguarde...")

    try:
        (sucesso, msg_erro, storages) = sapisrv_chamar_programa(
            "sapisrv_obter_lista_storage.php",
            {'tipo': 'trabalho',
             'unidade': GdadosGerais['unidade']
             }
        )
    except BaseException as e:
        print_tela_log("- Não foi possível recuperar a situação atualizada das storages do servidor:", str(e))
        return False

    # Insucesso. Algo estranho aconteceu
    if (not sucesso):
        # Sem sucesso
        print_log("[1073] Recuperação de situação de storages FALHOU: ", msg_erro)
        return False

    # Guarda na global de storages
    Gstorages = storages

    # Ajusta índice, pois pode ter ocorrido exclusão de storages, deixando o índice com valor inválido
    if Gstorages is None or Gicor>len(Gstorages):
        Gicor=1

    # Guarda data hora do último refresh de storages
    GdadosGerais["data_hora_ultima_atualizacao_status"] = datetime.datetime.now().strftime('%H:%M:%S')

    return True


# Exibir informações sobre storage
# ----------------------------------------------------------------------
def dump_storage():
    print("===============================================")
    var_dump(Gstorages[Gicor])
    print("===============================================")


# Funções relacionada com movimentação na lista de itens
# ----------------------------------------------------------------------
def avancar_item():
    global Gicor

    if (Gicor < len(Gstorages)):
        Gicor += 1


def recuar_item():
    global Gicor

    if (Gicor > 1):
        Gicor -= 1


def posicionar_item(n):
    global Gicor

    n = int(n)

    if (1 <= n <= len(Gstorages)):
        Gicor = n


# Retorna True se realmente deve ser finalizado
def finalizar_programa():

    # Tudo certo, finalizar
    return True



#-----------------------------------------------------------------------
# *inc : Incluir um novo storage
# ----------------------------------------------------------------------
def registrar_storage():
    return console_executar_tratar_ctrc(funcao=_registrar_storage)

def _registrar_storage():

    global Gconf_novo_storage

    # Cabeçalho
    cls()
    print("Registro de um novo storage")
    print("===========================")

    # Instruções
    # --------------------------------------------------------------
    print("")
    print("- Pré-requisitos para registrar um novo storage:")
    print("1) Possuir direito de administração no SAPI.")
    print("2) Ter executado os procedimentos de instalação/configuração no servidor conforme descrito em:")
    print("   " + Gwiki_storage)
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

    # Solicitar configuração do storage na variável global
    # Desta forma, se retomar a configuração, os dados serão mantidos
    return solicitar_configuracao_storage(Gconf_novo_storage, novo=True)

#-----------------------------------------------------------------------
# *inc : Incluir um novo storage
# ----------------------------------------------------------------------
def editar_storage(conf_storage):
    return console_executar_tratar_ctrc(_editar_storage, conf_storage)

def _editar_storage(conf_storage):

    '''
    # Para teste de atualização
    conf_storage = dict()
    conf_storage['id'] = 'gtpi-sto-03'
    conf_storage['maquina_netbios'] = 'gtpi-sto-03'
    conf_storage['nome_storage'] = 'gtpi-sto-03/storage'
    conf_storage['pasta_share'] = 'storage'
    conf_storage['usuario'] = 'sapi'
    conf_storage['senha'] = 'sapi2017'
    conf_storage['usuario_consulta'] = 'consulta'
    conf_storage['senha_consulta'] = 'sapi'
    '''

    return solicitar_configuracao_storage(conf_storage, novo=False)


# Pergunta e valida todos os campos de configuração
# - True: Recebeu e validou todos os campos
# - False: Interrompido/abandonado
def solicitar_configuracao_storage(conf_storage, novo=False):

    # Entrada e validação de configuração
    # -----------------------------------
    while True:
        print()
        print("Entre com os parâmetros de configuração do storage")
        print("==================================================")
        print("Dica: Para interromper, utilize CTR-C")
        print()

        # Se estiver atualizando, exibe o storage-id para orientação
        if not novo:
            print()
            print("Storage id: ", conf_storage['storage_id'])
            print()

        # IP
        while True:
            solicita_campo_configuracao(conf_storage, 'maquina_ip')
            if validar_ip(conf_storage):
                break

        # Netbios
        while True:
            solicita_campo_configuracao(conf_storage, 'maquina_netbios')
            if validar_netbios(conf_storage):
                break

        # --- Simulação de alguns erros, para testar ---
        #  Credencial de consulta incorreta
        # conf_storage['senha_consulta']='simulada'
        # Credencial de atualização incorreta
        # conf_storage['senha']='simulada'
        # Conta de consulta com direito de atualização
        # conf_storage['usuario_consulta']= conf_storage['usuario']
        # conf_storage['senha_consulta']=conf_storage['senha']
        # Conta de atualização apenas com direito de consulta
        # conf_storage['usuario']= conf_storage['usuario_consulta']
        # conf_storage['senha']=conf_storage['senha_consulta']

        while True:
            solicita_campo_configuracao(conf_storage, 'pasta_share')
            solicita_campo_configuracao(conf_storage, 'usuario')
            solicita_campo_configuracao(conf_storage, 'senha')
            if validar_credencial_atualizacao(conf_storage):
                # Ok, validado
                break
            if not tentar_novamente():
                return False

        if not validacao_estrutura_storage(conf_storage):
            return False


        while True:
            solicita_campo_configuracao(conf_storage, 'usuario_consulta')
            solicita_campo_configuracao(conf_storage, 'senha_consulta')
            if validar_credencial_consulta(conf_storage):
                # Ok, validado
                break
            if not tentar_novamente():
                return False

        if novo:
            while True:
                # Se for um novo storage, solicita storage_id
                solicita_campo_configuracao(conf_storage, 'storage_id')
                # Valida
                if validar_storage_id(conf_storage):
                    # Ok, validado
                    break
                if not tentar_novamente():
                    return False

        solicita_campo_configuracao(conf_storage, 'descricao')

        # Fixo por enquanto, pois só temos storage do tipo trabalho
        # Quando tiver outros tipos, solicitar este campo
        conf_storage['tipo']='trabalho'

        # Se chegou até aqui, é porque foi tudo validado
        break


    # Tudo certo

    # Guarda dados sobre o configurador na variável de configuração
    # --------------------------------------------------------------
    conf_storage['agenteSAPI']                      = Gprograma
    conf_storage['agenteSAPI_versao']               = Gversao
    conf_storage['configurador_conta_usuario']      = obter_param_usuario('conta_usuario')
    conf_storage['configurador_nome_guerra']        = obter_param_usuario('nome_guerra')
    conf_storage['configurador_unidade']            = obter_param_usuario('codigo_unidade_lotacao')
    conf_storage['configurador_unidade_sigla']      = obter_param_usuario('sigla_uni')
    conf_storage['configurador_ip']                 = obter_param_usuario("ip_cliente")
    conf_storage['configurador_hostname']           = socket.gethostname()

    # Se está no ambiente de desenvolvimento, ajusta parâmetro para deixas storage
    # registrado exclusivo para ambiente de desenvolvimento
    conf_storage['desenvolvimento'] = 0
    if ambiente_desenvolvimento():
        conf_storage['desenvolvimento'] = 1

    # Confirma e grava configuração
    return confirmar_gravar_configuracao(conf_storage)


# Valida todos os campos de configuração
# - True: Configuração válida
# - False: Algum problema
def validar_configuracao_storage(conf_storage):

    if not validar_ip(conf_storage):
        return False

    if not validar_netbios(conf_storage):
        return False

    if not validar_credencial_atualizacao(conf_storage):
        return False

    if not validacao_estrutura_storage(conf_storage):
        return False

    if not validar_credencial_consulta(conf_storage):
        return False

    # Tudo certo
    return True




def confirmar_gravar_configuracao(conf_storage):
    # --------------------------------------------------------------------
    # Confirma configuração antes de gravar
    # --------------------------------------------------------------------
    print()
    print_centralizado()
    print("Confirmação Final")
    print_centralizado()

    exibe_configuracao_storage(conf_storage, completa=True)

    print("- Confira se a configuração acima está correta.")
    print("- Se você prosseguir, a configuração do storage será registrada no SETEC3.")
    if not prosseguir_configuracao():
        return False

    # Registrar configuração
    #------------------------
    unidade=obter_param_usuario('codigo_unidade_lotacao')
    storage_id=conf_storage['storage_id']
    print("- Registrando storage no SETEC3. Aguarde...")
    (sucesso, msg_erro) = sapisrv_registrar_storage(
        storage_id=storage_id,
        configuracao=conf_storage,
        unidade=unidade)
    if not sucesso:
        print("- ERRO: ", msg_erro)
        return False

    # Finalizado com sucesso
    # ------------------------
    print()
    print("SUCESSO")
    print("-------")
    print("- Configuração do storage ", storage_id, "registrada com sucesso no servidor SETEC3")
    print()
    espera_enter()
    return True


def solicita_campo_configuracao(conf_storage, campo):

    # Entrada dos campos
    if campo=='maquina_ip':
        conf_storage[campo]=entrada_campo(
            label="IP do storage",
            explicacao="Entre com o ip do storage (exemplo: 10.41.87.235)",
            default=conf_storage.get(campo, ""),
            tipo_campo='ip')
        return

    if campo == 'maquina_netbios':
        conf_storage[campo] = entrada_campo(
            label="Nome netbios",
            explicacao="Informe nome netbios do storage, exemplo: storage-01",
            default=conf_storage.get(campo, ""),
            tipo_campo='token_texto_simples')
        return

    if campo == 'pasta_share':
        conf_storage[campo] = entrada_campo(
            label="Compartilhamento",
            explicacao="Informe o nome que foi dado ao compartilhamento SMB. Exemplo: storage",
            default=conf_storage.get(campo, ""),
            tipo_campo='token_texto_simples')
        return

    if campo == 'usuario':
        conf_storage[campo] = entrada_campo(
            label="Conta do usuário de ATUALIZAÇÃO",
            explicacao="Informe a conta do usuário com direito de atualização no compartilhamento (Exemplo: sapi)",
            default=conf_storage.get(campo, ""),
            tipo_campo='token_texto_simples')
        return

    if campo == 'senha':
        conf_storage[campo] = entrada_campo(
            label="Senha do usuário de atualização",
            explicacao="Informe a senha da conta do usuário com direito de atualização",
            default=conf_storage.get(campo, ""),
            tipo_campo='token_texto_simples')
        return


    if campo == 'usuario_consulta':
        conf_storage[campo] = entrada_campo(
            label="Conta do usuário de CONSULTA",
            explicacao="Informe a conta do usuário com direito APENAS DE CONSULTA no compartilhamento (Exemplo: consulta)",
            default=conf_storage.get(campo, ""),
            tipo_campo='token_texto_simples')
        return

    if campo == 'senha_consulta':
        conf_storage[campo] = entrada_campo(
            label="Senha do usuário de consulta",
            explicacao="Informe a senha da conta do usuário com direito de CONSULTA",
            default=conf_storage.get(campo, ""),
            tipo_campo='token_texto_simples')
        return

    if campo == 'storage_id':
        conf_storage[campo] = entrada_campo(
            label="Identificador (storage id)",
            explicacao="Identificação do storage. Este identificador deve ser ÚNICO na sua unidade.\n  Sugestão: utilizar valor igual ao nome netbios (se o servidor só tem um compartilhamento para o SAPI).",
            # Se não estiver preenchido, coloca como default o nome netbios
            default=conf_storage.get(campo, conf_storage.get('maquina_netbios',"")),
            tipo_campo='token_texto_simples')
        return


    if campo == 'descricao':
        conf_storage[campo] = entrada_campo(
            label="Descrição",
            explicacao="Esta descrição irá ser exibida para o usuário, para ajudá-lo a reconhecer o storage.",
            # Se não estiver preenchido, coloca como default o nome netbios
            default=conf_storage.get(campo, conf_storage.get('descricao',"")),
            tipo_campo='texto_livre')
        return

    # Não deveria chegar aqui...foi passado um nome de campo incorreto
    erro_fatal("- Nome de campo inválido: ", campo)



def validar_ip(conf_storage):

    ip=conf_storage['maquina_ip']
    (sucesso, saida) = ping(ip)
    if not sucesso:
        print("- ERRO: Ping para", ip, "falhou")
        print()
        return False

    # Tudo certo
    return True

def validar_netbios(conf_storage):

    # Valida
    nome_netbios=conf_storage['maquina_netbios']
    (sucesso, saida_netbios) = ping(nome_netbios)
    if not sucesso:
        print("- ERRO: Ping para", nome_netbios, "falhou")
        return False

    # Verifica se nome netbios foi resolvido para o mesmo ip informado
    ip = conf_storage['maquina_ip']
    hostbyname = socket.gethostbyname(nome_netbios)
    if ip not in saida_netbios and ip not in hostbyname:
        print("- ERRO: Nome netbios não está sendo resolvido para o IP informado")
        print_tela(saida_netbios)
        debug("- Por gethostbyname foi resolvido para: " + str(hostbyname))
        print("- Verifique se o hostname e IP correspondem REALMENTE à mesma máquina")
        print("- Dica: Se você está executando o sapi_storage na mesma máquina que está o SMB share, PARE agora.")
        print("        Situações anômalas irão ocorrer (esta pode ser uma delas).")
        return False

    return True


def validar_credencial_atualizacao(conf_storage):

    print()
    print("Validando credencial de atualização")
    print("-----------------------------------")
    string_conexao= "\\\\"+conf_storage['maquina_netbios']+"\\"+conf_storage['pasta_share']+" utilizando conta:"+conf_storage['usuario'] + " e senha:" + conf_storage['senha']
    print("- Acessando compartilhamento", string_conexao)

    # Efetua conexão no storage
    # -------------------------
    # Desconecta mapeamento com conta de consulta, caso esteja conectado
    #var_dump(conf_storage)
    #die('ponto4268')
    if not desconecta_mapeamento_atualizacao(conf_storage):
        return False

    # Efetua conexão com a conta de atualização
    ponto_montagem = conectar_storage_atualizacao_ok(conf_storage, ignorar_falta_arquivo_controle=True)
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        print("- ERRO: Credencial de atualização não foi aceita para este compartilhamento.")
        print("- Um ou mais dos campos abaixo não está com valor correto:")
        print("  Compartilhamento => ", conf_storage['pasta_share'])
        print("  Conta            => ", conf_storage['usuario'])
        print("  Senha            => ", conf_storage['senha'])
        print("- Dica: Caso esteja tendo dificuldade em diagnosticar o problema,")
        print("  tente efetuar a conexão no compartilhamento através do explorer do windows no")
        print("  compartilhamento", string_conexao)
        return False

    # Verifica se está permitindo gravação na pasta
    # ---------------------------------------------
    pasta_teste=os.path.join(ponto_montagem, Gpasta_tmp, "teste_gravacao_"+str(uuid.uuid4()))
    print("- Teste de gravação. Criando pasta:", pasta_teste)
    try:
        os.makedirs(pasta_teste)
    except PermissionError as e:
        print("- ERRO: Não permitiu gravação no storage: ", str(e))
        return False

    # Confere se realmente conseguiu gravar
    if (not os.path.exists(pasta_teste)):
        print("- ERRO: Conta não está permitindo atualização")
        print("- Apesar do sistema operacinal não ter acusado erro, não foi encontrada pasta que deveria ter sido gravada")
        print("- Concede direito para gravação para esta conta e/ou verifique se você informou a conta correta")
        return False
    print("- Pasta criada com sucesso")

    # Exclui toda a pasta temporária
    # ------------------------------
    pasta_tmp = os.path.join(ponto_montagem, Gpasta_tmp)
    print("- Excluindo pasta temporária:", pasta_tmp)
    try:
        shutil.rmtree(pasta_tmp)
    except OSError as e:
        print("- ERRO: ", str(e))
        return False
    except BaseException as e:
        print("- Erro:", str(e))
        return False
    # Confirme se foi realmente excluída
    time.sleep(5)
    if os.path.exists(pasta_tmp):
        print("- ERRO: Não foi possível excluir pasta temporária")
        return False
    print("- Pasta excluída")

    # Encerra
    # --------------------------------
    # Desconecta
    print("- Desconectadndo mapeamento de atualização")
    if not desconecta_mapeamento_atualizacao(conf_storage):
        return False
    print("- Desconectado")

    # Tudo certo
    print("- SUCESSO. Credencial de atualização OK")
    return True


def validacao_estrutura_storage(conf_storage):

    print()
    print("Validando estrutura do storage")
    print("------------------------------")

    # Efetua conexão com a conta de atualização
    ponto_montagem = conectar_storage_atualizacao_ok(conf_storage, ignorar_falta_arquivo_controle=True)
    if ponto_montagem is None:
        # Mensagens de erro já foram apresentadas pela função acima
        print("- ERRO: Credencial de atualização é inválida. Confira conta e senha")
        return False

    # Verifica se na raiz do storage existe arquivo de caracterização do storage
    arquivo_controle = os.path.join(ponto_montagem, Garquivo_controle)
    print_tela_log("- Procurando arquivo de controle:", arquivo_controle)
    criar_arquivo_controle=False
    if os.path.isfile(arquivo_controle):
        print_tela_log("- Arquivo localizado")
        criar_arquivo_controle = False
    else:
        print_tela_log("- Arquivo não foi encontrado")
        criar_arquivo_controle = True

    # Cria arquivo de controle
    if criar_arquivo_controle:
        print_tela_log("- Criando arquivo: ", arquivo_controle)
        try:
            # Grava arquivo de controle
            with codecs.open(arquivo_controle, 'w', "utf-8") as arq:
                arq.write("NÃO EXCLUA este arquivo\r\n")
                arq.write("Este é um arquivo de controle do SAPI\r\n")
        except BaseException as e:
            print("- ERRO na criação do arquivo: ", str(e))
            return False

        # Confere se realmente gravou
        if not os.path.isfile(arquivo_controle):
            print_tela_log("- ERRO: Gravação de arquivo falhou")
            return False
            print_tela_log("- Arquivo criado com sucesso")
        print_atencao()
        print("- Foi criado automaticamente na raiz do storage um arquivo denominado", arquivo_controle)
        print("- JAMAIS EXCLUA ESTE ARQUIVO, ")
        print("  pois o mesmo é essencial para que o SAPI possa reconhecer que o storage está adequadamente montado,")
        print("  particularmente em agentes linux")
        espera_enter()
        print()

    # Tudo certo
    print_tela_log("- SUCESSO. Estrutura do storage está ok")
    return True



def validar_credencial_consulta(conf_storage):

    # Efetua conexão com conta de consulta
    # ------------------------------------
    print()
    print("Validando credencial de consulta")
    print("---------------------------------")
    print("- Credencial de consulta informada:", conf_storage["usuario_consulta"], "/", conf_storage["senha_consulta"])

    if conf_storage["usuario_consulta"]==conf_storage["usuario"]:
        print("- ERRO: A conta de consulta não pode ser igual à conta de atualização")
        return False

    # Conecta com conta de consulta
    # -----------------------------
    # Desconecta mapeamento com conta de consulta, caso esteja conectado
    if not desconecta_mapeamento_consulta(conf_storage):
        return False

    # Efetua conexão com conta de consulta
    # Caminho para storage pelo nome netbios
    ponto_montagem = conectar_storage_consulta_ok(conf_storage)
    if ponto_montagem is None:
        print("- ERRO: Credencial de consulta é inválida. Confira conta e senha")
        return False

    # Verifica se está apenas com direito de leitura
    # ----------------------------------------------
    # Verifica se está permitindo gravação na pasta
    pasta_teste=os.path.join(ponto_montagem, Gpasta_tmp, "teste_gravacao_"+str(uuid.uuid4()))
    print_tela_log("- Teste de gravação.")
    print_log("Criando pasta:", pasta_teste)
    try:
        os.makedirs(pasta_teste)
    except PermissionError as e:
        print("- Tudo bem, gravação foi bloqueada")
        print_log("- Tentativa de gravação com conta de consulta corretamente bloqueada:", str(e))

    # Confirma se realmente não conseguiu gravar
    if (os.path.exists(pasta_teste)):
        print("- Pasta foi criada.")
        print("- ERRO: Conta de consulta está permitindo gravação")
        print("- Remova o direito de gravação para esta conta e/ou verifique se você informou a conta correta")
        return False

    # Encerra
    # --------------------------------------------------------
    print("- Desconectando mapeamento de consulta")
    if not desconecta_mapeamento_consulta(conf_storage):
        return False

    # Tudo certo
    print("- SUCESSO. Credencial de consulta OK")
    return True



def desconecta_mapeamento_consulta(conf_storage):

    # Caminho para storage pelo nome netbios
    caminho_storage=obter_caminho_storage(conf_storage, utilizar_ip=False)

    # Procurar mapemaento já existente, para alguma letra
    print("- Verificando se storage já está mapeado")
    letra=procurar_mapeamento_letra(caminho_storage, ignorar_falta_arquivo_controle=True)

    if letra is None:
        # Tudo bem, Não tem mapeamento para netbios
        print("- Nenhum mapeamento encontrado")
        return True

    # Tem mapeamento associado a uma letra
    print("- Storage já está mapeado para", letra)
    print("- Desconectando. Aguarde...")
    (sucesso, erro, saida)=desconectar_mapeamento_forcado(letra)
    if not sucesso:
        print("- Desconexão falhou: ", erro)
        print("- Se o problema persistir, tente desconectar todos os mapeamentos manualmente (net use xxxx /del)")
        return False

    # Confere se realmente desconectou
    time.sleep(5) # Tempo para evitar que o Windows responda falsamente que mapeamento ainda existe
    letra=procurar_mapeamento_letra(caminho_storage)
    if letra is not None:
        print("- Apesar de não retornar erro, NÃO foi possível desconectar o mapeamento para", letra)
        print("-Se o problema persistir, tente desconectar manualmente (net use xxxx /del")
        return False

    # Ok, conseguiu desconectar
    print("- Desconectado com sucesso")
    return True

def desconecta_mapeamento_atualizacao(conf_storage):

    # Caminho para storage pelo nome netbios
    caminho_storage=obter_caminho_storage(conf_storage, utilizar_ip=True)

    # Verifica se storage já está montado
    (mapeado, linha)= procurar_mapeamento(caminho_storage)
    if not mapeado:
        # Tudo bem, não está mapeado
        debug("Storage não estava montado em", caminho_storage)
        return True

    # Tem mapeamento
    print("- Storage em modo de atualização já está mapeado:", caminho_storage)
    print("- Desconectando. Aguarde...")
    (sucesso, erro, saida)=desconectar_mapeamento_forcado(caminho_storage)

    if not sucesso:
        print("- Desconexão falhou: ", erro)
        print("- Tente desconectar todos os mapeamentos manualmente (net use xxxx /del)")
        return False

    # Confere se realmente desconectou
    (mapeado, linha)= procurar_mapeamento(caminho_storage)
    if mapeado:
        # Algo estranho aconteceu
        print("- Desconexão falhou, apesar de windows não acusar erro")
        print("- Tente desconectar todos os mapeamentos manualmente (net use xxxx /del)")
        return False

    # Ok, conseguiu desconectar
    print("- Desconectado com sucesso")
    return True



def validar_storage_id(conf_storage):

    # Verifica se storage id já existe
    # ------------------------------------
    unidade=obter_param_usuario('codigo_unidade_lotacao')
    storage_id=conf_storage['storage_id']
    print("- Verificando ser storage_id é válido. Aguarde...")
    (sucesso, msg_erro, resultado) = sapisrv_consultar_storage(
        storage_id=storage_id,
        unidade=unidade)
    if not sucesso:
        print("- ERRO: ", msg_erro)
        return False

    # Storage ID já existe na unidade
    if resultado is not None:
        print("- ERRO: Já existe um storage com id", storage_id,"na sua unidade")
        return False

    # Tudo bem, storage_id não existe
    return True


# Confirma se usuário deseja prosseguir com configuração
def prosseguir_configuracao():
    if not pergunta_sim_nao("< Prosseguir?", default="n"):
        print("- Configuração cancelada pelo usuário.")
        return False

    # Usuário deseja prosseguir
    return True


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
    nome_arquivo_log = "log_sapi_storage.txt"
    sapisrv_inicializar_ok(Gprograma, Gversao, auto_atualizar=True, nome_arquivo_log=nome_arquivo_log)
    print_log('Inicializado com sucesso', Gprograma, ' - ', Gversao)

    # Instrução inicial
    print_atencao()
    print("- O sapi_storage não funcionará adequadamente quando executado no próprio servidor aonde está o share SMB.")
    print("- Haverá problema de resolução de nome netbios e outras falhas inesperadas.")
    print("- Execute o sapi_storage em uma máquina em que não está o share SMB do storage,")
    print("  preferencialmente em uma máquina em que rodará um agente SAPI qualquer.")
    print()
    espera_enter()

    if not login_sapi():
        return False

    # Verifica se usuário tem direito de administrador
    if not obter_param_usuario("adm_sapi"):
        print("- ERRO: Para efetuar a configuração você precisa de direito de administrador no SAPI.")
        if pergunta_sim_nao("Deseja ver ajuda no wiki?"):
            abrir_browser_wiki(Gwiki_admin)
        return False


    # Armazena alguns dados para uso futuro
    GdadosGerais["pcf"] = obter_param_usuario("nome_guerra")
    GdadosGerais["unidade"]=obter_param_usuario("codigo_unidade_lotacao")
    GdadosGerais["unidade_sigla"]=obter_param_usuario("sigla_unidade_lotacao")

    # Exibe storages da unidade
    # -------------------------
    refresh_exibir_situacao()

    # Processamento de comandos
    # -------------------------
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

        # Comandos de storage
        if (comando == '*du'):
            dump_storage()
            continue
        elif (comando == '*con'):
            carrega_exibe_storage_corrente()
            continue
        elif (comando == '*tst'):
            validar_storage_corrente()
            continue
        elif (comando == '*alt'):
            if alterar_storage_corrente():
                refresh_exibir_situacao()
            continue
        elif (comando == '*sto'):
            exibir_pasta_storage_file_explorer()
            continue

        # Comandos gerais
        if (comando == '*sg'):
            if refresh_storages():
                exibir_situacao(comando)
            continue
        elif (comando == '*log'):
            exibir_log(comando='*log', filtro_base='', filtro_usuario=argumento)
            continue
        elif (comando == '*inc'):
            if registrar_storage():
                refresh_exibir_situacao()
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

    # Encerrando conexão com storage
    print()
    desconectar_todos_storages()

    # Finaliza
    print()
    print("FIM SAPI Cellebrite - Versão: ", Gversao)




if __name__ == '__main__':

    main()

    print()
    espera_enter("Programa finalizado. Pressione <ENTER> para fechar janela.")
