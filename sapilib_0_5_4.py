# **********************************************************************
# **********************************************************************
# **********************************************************************
#        BIBLIOTECA DE FUNÇÕES GERAIS DO SAPI PARA PYTHON (SAPILIB)
# 
#
# - Utilizada em agentes python do sistema SAPI
# - Para evitar colocar na produção um código com dependência,
#   utiliza-se a inserção desta biblioteca no código de produção.
# - Durante o estágio de desenvolvimento esta biblioteca
#   é mantida em arquivo separado,  
#   e importada integralmente para os programas sapi agente, 
#   através do comando: from sapi import *
# - Para o código de produção, o comando acima é substituido
#   pelo código integral desta biblioteca
# - Isto evita dependência (na produção) e evita redundância de código
#   (durante o desenvolvimento)
#   
# 
# - Histórico:
#   0.5.3 - Agregou funções que estavam no agente_demo
#   0.5.4 - Ajustes diversos....
# 
# **********************************************************************
# **********************************************************************
#                  INICIO DO SAPI_LIB
# **********************************************************************
# **********************************************************************

# Módulos utilizados
import codecs
import datetime
import json
import os
import pprint
import sys
import urllib
import urllib.parse
import urllib.request

# ------------ Constantes (na realidade variáveis Globais) -------------
# Valores de codigo_situacao_status (para atualizar status de tarefas)
GSemPastaNaoIniciado = 1
GAbortou = 8
GPastaDestinoCriada = 30
GEmAndamento = 40
GFinalizadoComSucesso = 95

# Se mais tarde tiver dois endereços
# (talvez um proxy para o setec3 na VLAN)
# vai ter que aprimorar isto aqui
GconfUrlBaseSapi = "http://10.41.84.5/setec3_dev/"
Gdesenvolvimento = True

# Retorna verdadeiro se execução está sendo efetuada em ambiente de 
# desenvolvimento
# ----------------------------------------------------------------------
def ambiente_desenvolvimento():
    if (Gdesenvolvimento == True):
        return True

    #
    return False


# Assegura que o cliente tem comunicação com servidor
# ----------------------------------------------------------------------
def assegura_comunicacao_servidor_sapi():
    sys.stdout.write("Testando conexao com servidor SAPI...")
    try:
        url = GconfUrlBaseSapi + "sapisrv_ping.php"
        f = urllib.request.urlopen(url)
        resposta = f.read()
    except BaseException as e:
        print_ok("Nao foi possivel conectar com: ", url)
        print_ok("Erro: ", str(e))
        print_ok("Verifique configuracao de rede")
        sys.exit(1)

    # Confere resposta
    if (resposta == "pong"):
        # Tudo bem
        sys.stdout.write('ok')
        print()
        print()
        return
    else:
        print()
        print_ok("Servidor conectado em (", url, "), porem com resposta inesperada:")
        print_ok(resposta)
        sys.exit(1)


# Invoca Sapi server (sapisrv)
# Explica e aborta se houver erro de conexão.
# Explica e aborta se página de retorno não estiver em formato json.
# ----------------------------------------------------------------------
def sapisrv_invocar_url(url):
    # Chama url e le pagina resultante
    try:
        f = urllib.request.urlopen(url)
        resultado = f.read()
    except BaseException as e:
        print
        print_ok("Nao foi possivel conectar com:", url)
        print_ok("Erro: ", str(e))
        print_ok("Verifique configuracao de rede")
        sys.exit(1)

    # O resultado vem em 'bytes',
    # exigindo uma conversão explícita para UTF8
    try:
        resultado = resultado.decode('utf-8')
    except BaseException as e:
        print_ok()
        print_ok("Falha na codificação UTF-8 da resposta de: ", url)
        print_ok("===== Pagina retornada =========")
        print_ok(resultado)
        print_ok("===== Fim da pagina =========")
        # print_ok("Erro: ", str(e))
        print_ok("Verifique programa sapisrv")
        sys.exit(1)

    # Processa pagina resultante em formato JSON
    try:

        # Carrega json.
        # Se houver algum erro de parsing, indicando que o servidor
        # não está legal, irá ser tratado no exception
        d = json.loads(resultado)

    except BaseException as e:
        print_ok()
        print_ok("Resposta invalida (não está no formato json) de: ", url)
        print_ok("===== Pagina retornada =========")
        print_ok(resultado)
        print_ok("===== Fim da pagina =========")
        # print_ok("Erro: ", str(e))
        print_ok("Verifique programa sapisrv")
        sys.exit(1)

    # Tudo certo
    return d


# Chama sapisrv, esperando sucesso como resultado
# Se o retorno não for sucesso, aborta com erro fatal
# ----------------------------------------------------------------------
def sapisrv_sucesso(url):
    # Chama servico
    d = sapisrv_invocar_url(url)

    # Se não foi sucesso, aborta
    if (d["sucesso"] == "0"):
        print
        print_ok("Erro inesperado reportado por: ", url)
        print_ok(d["msg_erro"])
        sys.exit(1)

    # Tudo certo
    return d


# Invoca Sapi server (sapisrv)
# Explica e aborta se houver erro de conexão.
# Explica e aborta se página de retorno não estiver em formato json.
# ----------------------------------------------------------------------
def sapisrv_chamar_programa(programa, parametros, abortar_insucesso=False, registrar_log=False):
    parametrosFormatados = urllib.parse.urlencode(parametros)
    url = GconfUrlBaseSapi + programa + "?" + parametrosFormatados

    if (registrar_log):
        print_log_dual(url)

    if (abortar_insucesso):
        # Chama função que efetua tratamento de insucesso
        # Se houver insucesso, será abortado
        retorno = sapisrv_sucesso(url)
    else:
        # Função normal de chamada do sapisrv.
        # Sucesso ou insucesso será tratado pelo chamador
        retorno = sapisrv_invocar_url(url)

        # if (programa=='sapisrv_atualizar_tarefa.php'):
    #	var_dump(retorno)
    #	die('ponto171')


    # Ajusta sucesso para booleano
    sucesso = False
    if (retorno["sucesso"] == "1"):
        sucesso = True

    # Outros dados
    msg_erro = retorno["msg_erro"]
    dados = retorno["dados"]

    # Retorna o resultado, decomposto nos seus elementos
    return (sucesso, msg_erro, dados)


# Tratamento para erro fatal
# ----------------------------------------------------------------------
def erro_fatal(*args):
    sys.stdout.write("Sapi Erro Fatal: ")
    print_ok(*args)
    print_ok("Para maiores informações, consulte o arquivo de log (sapi_log.txt)")
    sys.exit(1)


# Aborta programa
# ----------------------------------------------------------------------
def die(s):
    print(s)
    sys.exit(1)


# Dump "bonitinho" de uma variável
# ----------------------------------------------------------------------
def var_dump(x):
    print(type(x))
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(x)


# Limpa tela, linux e nt
# ----------------------------------------------------------------------
def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


# Valores dos bytes em hexa de um string
# ----------------------------------------------------------------------
def print_hex(s):
    r = ""
    for x in s:
        r = r + hex(ord(x)) + ":"
    print_ok(r)


# Substitui o convert_unicode no python3, que já é unicode nativo
# Converte todos os argumentos para string e concatena
# ----------------------------------------------------------------------
def concatena_args(*arg):
    s = ""
    for x in arg:
        # Se não for string, converte para string
        if not type(x) == str:
            x = str(x)
        # Concatena
        s = s + x

    return s


# Paleativo para resolver problema de utf-8 no Windows
# e esta confusão de unicode no python
# Recebe um conjunto de parâmetros string ou unicode
# Converte tudo para unicode e exibe
# Exemplo de chamada:
# print_ok(x, y, z)
# Atenção: Se tentar concatenar antes de chamar, pode dar erro de 
# na concatenação (exemplo: print_ok(x+y+z))
# Se isto acontecer, utilize o formato de multiplos argumentos (separados
# por virgulas)
# 
# Lógica para python 2 foi desativada.
# Mantendo chamadas ao wrapper da função print por precaução....
# para poder eventualmente compatibilizar um programa com python 2 e 3
# ----------------------------------------------------------------------
def print_ok(*arg):
    if (len(arg) == 0):
        print()
        return

    # Este código é para python 2
    # Como eu espero que tudo funcione em python 3, vamos desabilitá-lo
    # Se mais tarde for necessário algo em python2, terá que colocar
    # alguma esperteza aqui
    # print converte_unicode(*arg)

    # Python3, já tem suporte para utf-8...basta exibir
    print(*arg)


# Grava em arquivo de log
# ----------------------------------------------------------------------
def print_log(*arg):
    # Monta linha para gravação no log
    pid = os.getpid()
    hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Código para python2. Por enquanto desativado
    # linha="["+str(pid)+"] : "+hora+" : "+converte_unicode(*arg)

    linha = "[" + str(pid) + "] : " + hora + " : " + concatena_args(*arg)

    with codecs.open("sapi_log.txt", 'a', "utf-8") as sapi_log:
        sapi_log.write(linha + "\r\n")

    sapi_log.close()

    return linha


# Grava no arquivo de log e exibe também na tela
# ----------------------------------------------------------------------
def print_log_dual(*arg):
    linha = print_log(*arg)
    print(linha)


# Exibe mensagem recebida na tela
# e também grava no log
# ----------------------------------------------------------------------
def print_tela_log(*arg):
    print_ok(*arg)
    print_log(*arg)


# Imprime se o primeiro argumento for verdadeiro
# ----------------------------------------------------------------------
def if_print_ok(exibir, *arg):
    # o primeiro campo tem que ser do tipo booleano
    # Um erro bastante comum é esquecer de passar este parâmetro
    # Logo, geramos um erro fatal aqui
    if type(exibir) != bool:
        print("Chamada inválida para if_print_ok, sem parâmetro de condição")
        print("Argumento: ", exibir, *arg)
        sys.exit()

    # O primeiro elemento deve ser um booleano
    # Se o primeiro parâmetro não for verdadeiro, não faz nada
    if (not exibir):
        return

    # Imprime, expurgando o primeiro elemento
    print(*arg)


# Converte para string para um formato hexa, para debug
# ----------------------------------------------------------------------
def string_to_hex(s):
    return ":".join("{:02x}".format(ord(c)) for c in s)


# Filtra apenas caracteres ascii de um string
# Os demais caracteres, substitui por '.'
# É útil quando não está conseguindo exibir um string na tela,
# em função da complexidade do esquema de encoding do python
# ----------------------------------------------------------------------
def filtra_apenas_ascii(texto):
    asc = ""
    for c in texto:
        # Se não for visível em ascii, troca para '.'
        if (ord(c) > 160):
            c = '.'
        asc = asc + c

    return asc


# Retorna verdadeiro se está rodando em Linux
# ----------------------------------------------------------------------
def estaRodandoLinux():
    if (os.name == 'posix'):
        # Linux
        return True

    if (os.name == 'nt'):
        # Windows
        return False

    # Algum outro sistema (talvez tenha que tratar os OSx se não vier
    # posix)
    # Por enquanto vamos abortar aqui, e ir refinando o código
    print_ok("Sistema operacional desconhecido : ", os.name)
    sys.exit(1)


# Verifica se usuário tem direito de root
# ----------------------------------------------------------------------
def temDireitoRoot():
    if not estaRodandoLinux():
        return False

    if os.geteuid() != 0:
        return False

    # Ok, tudo certo
    return True


# Pergunta Sim/Não via via input() e retorna resposta
# - pergunta: String que será exibido para o usuário
# - default: (s ou n) resposta se usuário simplesmente digitar <Enter>. 
# O retorno é True para "sim" e False para não
def pergunta_sim_nao(pergunta, default="s"):
    validos = {"sim": True, "s": True,
               "não": False, "n": False}
    if default is None:
        prompt = " [s/n] "
    elif default == "s":
        prompt = " [S/n] "
    elif default == "n":
        prompt = " [s/N] "
    else:
        raise ValueError("Valor invalido para default: '%s'" % default)

    while True:
        sys.stdout.write(pergunta + prompt)
        escolha = input().lower()
        if default is not None and escolha == '':
            return validos[default]
        elif escolha in validos:
            return validos[escolha]
        else:
            sys.stdout.write("Responda com 's' ou 'n'\n")


# Funções agregadas na versão 0.5.3 (antes estavam em código separados)

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
    suffixIndex = 0
    while size > 1024 and suffixIndex < 8:
        suffixIndex += 1  # increment the index of the suffix
        size = size / 1024.0  # apply the division
    return "%.*f%s" % (precision, size, suffixes[suffixIndex])


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


# Verifica se storage já está montado.
# Se não estiver, monta	em Linux
# Retorna (True/False, mensagem_erro)
# =============================================================
def acesso_storage_linux(ponto_montagem, conf_storage):
    # Um storage do sapi sempre deve conter na raiz o arquivo abaixo
    arquivo_controle = ponto_montagem + 'storage_sapi_nao_excluir.txt'

    # Se pasta para ponto de montagem não existe, então cria
    if not os.path.exists(ponto_montagem):
        os.makedirs(ponto_montagem)

    # Confirma se pasta existe
    # Não deveria falhar em condições normais
    # Talvez falhe se estiver sem root
    if not os.path.exists(ponto_montagem):
        print_ok("Criação de pasta para ponto de montagem [", ponto_montagem, "] falhou")
        return False

    # Verifica se arquivo de controle existe no storage
    if os.path.isfile(arquivo_controle):
        # Tudo bem, storage montado e confirmado
        return True

    # Monta storage
    # O comando é algo como:
    # mount -t cifs //10.41.87.239/storage -o username=sapi,password=sapi /mnt/smb/gtpi_storage
    comando = (
        "mount -v -t cifs " +
        "//" + conf_storage["maquina_ip"] +
        "/" + conf_storage["pasta_share"] +
        " -o username=" + conf_storage["usuario"] +
        ",password=" + conf_storage["senha"] +
        " " + ponto_montagem
    )

    # print_ok(comando)
    os.system(comando)

    # Verifica se arquivo de controle existe no storage
    if os.path.isfile(arquivo_controle):
        # Tudo certo, montou
        return True
    else:
        print_ok(comando)
        print_ok("Após montagem de storage, não foi encontrado arquivo de controle[", arquivo_controle, "]")
        print_ok("Ou montagem do storage falhou, ou storage não possui o arquivo de controle.")
        print_ok("Se for este o caso, inclua na raiz o arquivo de controle com qualquer conteúdo.")
        return False

# **********************************************************************
# **********************************************************************
#                  FINAL DO SAPI_LIB
# **********************************************************************
# **********************************************************************
