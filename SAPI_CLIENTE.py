# encoding: utf-8
# -*- coding: utf_8 -*-
# =======================================================================
# SAPI - Sistema de Apoio a Procedimentos de Informática
# 
# Componente: sapi_tableau_td3
# Objetivo: Agente para execução de imagem via Tableau TD3
# Funcionalidades:
#  - Conexão com o servidor SAPI para obter lista de tarefas
#    de imagem e reportar situação de execução das imagens
#  - Invoca Tableau TD3 via WEB preenchendo todos os campos necessários
#
# Autor: PCF Rodrigo (SETEC/PR)
#
# Histórico:
#  - v1.0 : Inicial
# =======================================================================
# TODO: 
# - configurações do cliente ficarem no servidor, com cadastro de clientes e as ferramentas habilitadas
# =======================================================================
'''
@created: 25/06/2016

@author: RODRIGO LANGE
'''

import configparser  # pip install -U configparser
import glob
import hashlib
import shutil
import socket
import time
import subprocess
import sys

import autoit  # pip install -U pyautoit
from selenium import webdriver  # pip install -U selenium
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

from sapilib_0_6 import *

# =======================================================================
# GLOBAIS
# =======================================================================
Gversao = "0.4"

Gdesenvolvimento = True  # Ambiente de desenvolvimento
# Gdesenvolvimento=False #Ambiente de producao

# Base de dados (globais)
GdadosGerais = {}  # Dicionário com dados gerais
Gtarefas = []  # Lista de tarefas

# Define nome do agente, que será repassado ao servidor sapi
Gnome_agente = socket.gethostbyaddr(socket.gethostname())[0]

# Utilizado para debug, imprime dicionario identado
Gpp = pprint.PrettyPrinter(indent=4)

# Se mais tarde tiver dois endereços 
# (talvez um proxy para o setec3 na VLAN)
# vai ter que aprimorar isto aqui
# GconfUrlBaseSapi="http://10.41.84.5/setec3_dev/"
GconfUrlBaseSapi = "http://10.41.84.5/setec3/"

# Controle de tempos/pausas
GtempoEntreAtualizacoesStatus = 180
GdormirSemServico = 15

# Valores de codigo_situacao_status (para atualizar status de tarefas)
GSemPastaNaoIniciado = 1
GAbortou = 8
GPastaDestinoCriada = 30
GEmAndamento = 40
GFinalizadoComSucesso = 95


# ======================================================================
# Rotina Principal 
# ======================================================================
def main():
    # Se o arquivo de configurações (CLIENTE.INI) não existir, cria um novo com os valores padrão
    if not os.path.exists('CLIENTE.ini'):
        print_log_dual(
            'Arquivo de configuração CLIENTE.ini não foi encontrado. Criando esse arquivo com opções padrão.')
        configura()
        print_log_dual('Arquivo de configuração CLIENTE.ini criado.')

    # VERIFICA A VERSÃO E ATUALIZA AS FERRAMENTAS HABILITADAS

    print_log_dual('Verificando quais ferramentas estão habilitadas e se estão atualizadas.')
    verifica_ferramentas()
    print_log_dual('Ferramentas atualizadas e verificadas.')

    # Obtém a listagem das ferramentas que estão habilitadas
    ferramentas_habilitadas = lista_ferramentas_habilitadas()

    # Busca tarefas para cada ferramenta
    for x in range(0, len(ferramentas_habilitadas)):
        print_log_dual("=========================================")
        print_log_dual('Procurando tarefa para a ferramenta: ' + ferramentas_habilitadas[x])
        executa_tarefas(ferramentas_habilitadas[x])

    # INFORMA TAREFAS FINALIZADAS OU COM ERRO

    # Finaliza
    sys.exit(0)


# =======================================================================
# FUNÇÕES GERAIS DO SAPI - CLIENTE 
# =======================================================================

# VERIFICA A VERSÃO E ATUALIZA AS FERRAMENTAS HABILITADAS
def verifica_ferramentas():
    config = configparser.ConfigParser()
    # Lê o arquivo de configuração
    config.read("CLIENTE.ini")
    # Lê quantas ferramentas existem
    lista_ferramentas = config.sections()
    for x in range(1, len(lista_ferramentas)):
        # Verifica se a ferramenta está disponível no cliente
        if config.getboolean("FERRAMENTAS", lista_ferramentas[x]):
            print_log_dual("Verificando se a ferramenta " + lista_ferramentas[x] + " está atualizada")
            # VERIFICA A PASTA SE EXISTE. SE NÃO EXISTIR, COPIA DA ORIGEM
            pasta_ferramenta = config.get(lista_ferramentas[x], "pasta")
            pasta_origem = config.get(lista_ferramentas[x], "origem")
            tipo_ferramenta = config.get(lista_ferramentas[x], "tipo")  # PASTA / EXECUTÁVEL
            if tipo_ferramenta == 'Pasta': # Basta copiar a pasta, sem instalação
                print_log_dual("Verificando se a pasta da ferramenta " + lista_ferramentas[x] + " existe.")
                if not os.path.exists(pasta_ferramenta):  # PASTA DE DESTINO DA FERRAMENTA NÃO EXISTE
                    print_log_dual("A pasta " + pasta_ferramenta + " não existe. Copiando...")
                    if os.path.exists(pasta_origem):  # SE A PASTA DE ORIGEM EXISTE COPIA
                        print_log_dual(
                            "A pasta de origem " + pasta_origem + " existe. Copiando para " + pasta_ferramenta)
                        shutil.copytree(pasta_origem, pasta_ferramenta)
                    else:  # PASTA DE ORIGEM NÃO EXISTE
                        print_log_dual("A pasta de origem " + pasta_origem + " não existe. Não dá para copiar. Saindo.")
                        sys.exit(1)
            elif tipo_ferramenta == 'Executavel': # Necessita de instalação, não basta copiar a pasta
                print_log_dual("Verificando se o programa " + lista_ferramentas[x] + " está instalado.")
                arquivo_ferramenta = pasta_ferramenta + "/" + config.get(lista_ferramentas[x], "executavel")
                # verifica se a pasta existe OU se o hash do executável é igual ao estipulado no arquivo de configuração
                if not os.path.exists(pasta_ferramenta) or hashlib.md5(
                        open(arquivo_ferramenta, 'rb').read()).hexdigest() != config.get(lista_ferramentas[x],
                                                                                         "hash_executavel"):
                    print_log_dual("Programa não instalado. Instalando o programa...")
                    comando = pasta_origem
                    comando += " "
                    comando += config.get(lista_ferramentas[x], "parametros")  #
                    print_log_dual(comando)
                    if os.path.exists(comando):
                        autoit.run(comando)
                        autoit.win_wait_active("Setup - Internet Evidence Finder")
                        autoit.win_wait_close("Setup - Internet Evidence Finder")
                        time.sleep(2)
                        print_log_dual("Programa " + lista_ferramentas[x] + "instalado.")
                    else:
                        print_log_dual("O arquivo de instalação do programa " + lista_ferramentas[
                            x] + " não foi encontrado. Saindo.")
                        sys.exit(1)
            print_log_dual("A ferramenta " + lista_ferramentas[x] + " está atualizada.")

    return


def iped(origem, destino, pasta_iped):
    print("... Processando com o IPED")
    # VERIFICA SE EXISTE A PASTA DE IMAGEM/PASTA DE ORIGEM
    if not os.path.exists(origem):
        print("Pasta/imagem de origem não existe...")

    # VERIFICA SE EXISTE A PASTA DE DESTINO
    if not os.path.exists(destino):
        print("Pasta/imagem de destino não existe...")

    # VERIFICA SE JÁ TEM PROCESSAMENTO DO IPED NA PASTA DE DESTINO PARA SABER SE USA O '--append'
    if not os.path.exists(destino + '/Ferramenta de Pesquisa.exe'):
        resultado = subprocess.check_output(['java', '-jar', '-Xmx24G', pasta_iped, '-d', origem, '-o', destino])
    else:
        resultado = subprocess.check_output(
            ['java', '-jar', '-Xmx24G', pasta_iped, '-d', origem, '-o', destino, '--append'])

    print(resultado)
    if 'IPED finalizado.' in resultado:
        print("PROCESSOU OK")
    elif 'ERRO!!!' in resultado:
        print("PROCESSOU COM ERROS")
    else:
        print("NÃO SEI COMO ACABOU")

    return


# Função do IEF. Parâmetros:
# origem = pasta de origem
# destino = pasta de destino
# tipo_execução = se vai usar o AUTOIT ou linha de comando (CLI)
# perfil_execucao = informa qual o perfil utilizado:
#    ief = executa com as opções padrão, sem vídeo nem imagem
#    ief-mobile = executa a versão padrão e mobile
#    ief-completo = executa a versão padrão, mobile e sistema operacional, inclusive vídeo e imagens
def ief(origem, destino, tipo_execucao, perfil_execucao):
    config = configparser.ConfigParser()
    # Lê o arquivo de configuração
    config.read("CLIENTE.ini")
    # Cria o perfil desejado do IEF
    ief_config(config.get('IEF', "pasta"), perfil_execucao)
    pasta_ief = config.get('IEF', "pasta") + "\\" + config.get('IEF', "executavel")
    if tipo_execucao == 'autoit':  # USANDO O AUTOIT
        print_log_dual("... Processando com o IEF - AUTOIT")
        print_log_dual(origem)
        autoit.run("C:\Program Files (x86)\Internet Evidence Finder\ief.exe")
        autoit.win_wait_active("Magnet IEF v6.8.1.2634")
        time.sleep(1)
        versao_ief = "Magnet IEF v" + config.get('IEF', "versao")
        autoit.win_move(versao_ief, 0, 0)
        time.sleep(1)
        autoit.mouse_click("left", 560, 332)
        time.sleep(2)
        autoit.send(origem.replace("/", "\\"))
        time.sleep(1)
        autoit.send("{ENTER}")
        time.sleep(5)
        autoit.send("{ENTER}")
        time.sleep(5)
        autoit.send("{TAB}")
        time.sleep(1)
        autoit.send("{ENTER}")
        time.sleep(5)
        autoit.mouse_click("left", 1080, 614)  # clica no NEXT
        time.sleep(5)
        autoit.mouse_click("left", 1080, 614)  # clica no NEXT
        time.sleep(5)
        autoit.send(destino.replace("/", "\\"))
        time.sleep(5)
        autoit.mouse_click("left", 1080, 614)  # clica no NEXT
    elif tipo_execucao == 'cli':  # USANDO LINHA DE COMANDO
        print_log_dual("Processando com o IEF - LINHA DE COMANDO")
        comando = '"' + pasta_ief + '"' + ' -i ' + '"' + origem + '" -s full -o ' + '"' + destino + '"'
        comando = comando.replace("/", "\\")
        print_log_dual("Comando executado: " + comando)
        resultado = subprocess.check_output(comando)
        print_log_dual("O resultado da execução da ferramenta IEF foi: ")
        print_log_dual(resultado)

    # GERANDO O RELATORIO
    print_log_dual("Gerando relatório do IEF")
    comando = '"' + 'C:\Program Files (x86)\Internet Evidence Finder\IEF Report Viewer\IEFrv.exe' + '" ' + '"' + destino.replace(
        "/", "\\") + '"'
    print_log_dual(comando)
    autoit.run(comando)
    versao_report = "IEF Report Viewer v" + config.get('IEF', "versao")
    autoit.win_wait_active(versao_report)
    time.sleep(1)
    autoit.win_move(versao_report, 0, 0)
    time.sleep(1)
    autoit.mouse_click("left", 26, 36)
    time.sleep(2)
    autoit.mouse_click("left", 87, 177)
    time.sleep(2)
    autoit.mouse_click("left", 640, 431)
    time.sleep(2)
    autoit.win_wait_active(versao_report, 0, text="Export completed.")
    time.sleep(2)
    autoit.win_close(versao_report)
    time.sleep(4)
    autoit.win_close('ief')
    time.sleep(2)
    autoit.win_close(versao_report)
    time.sleep(2)
    print_log_dual("Relatório do IEF gerado com sucesso.")
    return True


def ief_config(pasta_ief, perfil_execucao):
    print_log_dual("Gerando arquivo de configuração do IEF.")
    for f in glob.glob(pasta_ief + "/profiles/*.ini"):
        os.remove(f)
    arquivo = open(pasta_ief + "/profiles/config.ini", 'w')
    # if perfil_execucao == 'ief-mobile':
    arquivo.write("[main]")
    arquivo.write("default=True")
    arquivo.write("version=6.8.2.3062")
    arquivo.write("")
    arquivo.write("[Computer Artifact Selection]")
    arquivo.write("Torrent=True")
    arquivo.write("SafeBrowser=True")
    arquivo.write("Adium=True")
    arquivo.write("Flash Cookies=True")
    arquivo.write("AIM=True")
    arquivo.write("Android Backups=True")
    arquivo.write("Ares=True")
    arquivo.write("BeBo=True")
    arquivo.write("Bing Bar=True")
    arquivo.write("Bitcoin=True")
    arquivo.write("Browser Activity=True")
    arquivo.write("Carbonite=True")
    arquivo.write("Chatroulette=True")
    arquivo.write("Chrome=True")
    arquivo.write("Cortana=True")
    arquivo.write("Dropbox=True")
    arquivo.write("Edge=True")
    arquivo.write("EML(X) Files=True")
    arquivo.write("Emule=True")
    arquivo.write("Encrypted Files=True")
    arquivo.write("Encryption/Anti-forensics Tools=True")
    arquivo.write("Excel=True")
    arquivo.write("Facebook=True")
    arquivo.write("File System Information=True")
    arquivo.write("Firefox=True")
    arquivo.write("Flickr=True")
    arquivo.write("Gigatribe=True")
    arquivo.write("Gmail=True")
    arquivo.write("GMX Webmail=True")
    arquivo.write("Google Analytics=True")
    arquivo.write("GoogleDocs=True")
    arquivo.write("GoogleDrive=True")
    arquivo.write("Google Maps=True")
    arquivo.write("Google Talk=True")
    arquivo.write("Google Bar=True")
    arquivo.write("Google Plus=True")
    arquivo.write("Hangul Word Processor=True")
    arquivo.write("Hotmail=True")
    arquivo.write("Hushmail=True")
    arquivo.write("iChat=True")
    arquivo.write("ICQ=True")
    arquivo.write("iMessage=True")
    arquivo.write("Instagram=True")
    arquivo.write("Internet Explorer=True")
    arquivo.write("iOS Backups=True")
    arquivo.write("Jump Lists=True")
    arquivo.write("Keyword Searches=True")
    arquivo.write("Limerunner=True")
    arquivo.write("LimewireFrostwire=True")
    arquivo.write("LINE Pictures=True")
    arquivo.write("LinkedIn=True")
    arquivo.write("LNK Files=True")
    arquivo.write("Luckywire=True")
    arquivo.write("Lync / Office Communicator=True")
    arquivo.write("Mail.ru Chat=True")
    arquivo.write("Mailinator=True")
    arquivo.write("Malware/Phishing URLs=True")
    arquivo.write("MBox=True")
    arquivo.write("IRC=True")
    arquivo.write("Messenger Plus=True")
    arquivo.write("MySpace=True")
    arquivo.write("Network Interfaces=True")
    arquivo.write("Network Profiles=True")
    arquivo.write("Network Share Information=True")
    arquivo.write("Notification Center=True")
    arquivo.write("Omegle=True")
    arquivo.write("OneDrive=True")
    arquivo.write("Oovoo=True")
    arquivo.write("Opera=True")
    arquivo.write("Operating System Information=True")
    arquivo.write("Outlook=True")
    arquivo.write("Outlook Web App=True")
    arquivo.write("Outlook Webmail=True")
    arquivo.write("Pal Talk=True")
    arquivo.write("PDF=True")
    arquivo.write("Pictures=True")
    arquivo.write("Pidgin=True")
    arquivo.write("Pornography URLs=True")
    arquivo.write("PowerPoint=True")
    arquivo.write("QQ Chat=True")
    arquivo.write("RebuildWeb=True")
    arquivo.write("RecycleBin=True")
    arquivo.write("RTF Documents=True")
    arquivo.write("Safari=True")
    arquivo.write("Second Life=True")
    arquivo.write("Shareaza=True")
    arquivo.write("SharePoint=True")
    arquivo.write("Shellbags=True")
    arquivo.write("Sina Weibo=True")
    arquivo.write("Skype=True")
    arquivo.write("Startup Items=True")
    arquivo.write("Text Documents=True")
    arquivo.write("Timezone Information=True")
    arquivo.write("TorChat=True")
    arquivo.write("Trillian=True")
    arquivo.write("Twitter=True")
    arquivo.write("USB Devices=True")
    arquivo.write("Usenet=True")
    arquivo.write("User Accounts=True")
    arquivo.write("UserAssist=True")
    arquivo.write("Viber=True")
    arquivo.write("Videos=True")
    arquivo.write("VirtualMachines=True")
    arquivo.write("VK=True")
    arquivo.write("Flash Video Fragments=True")
    arquivo.write("Webpage Recovery=True")
    arquivo.write("WeChat=True")
    arquivo.write("Windows Event Logs=True")
    arquivo.write("Windows Live Messenger=True")
    arquivo.write("Windows Logon Banner=True")
    arquivo.write("Windows Prefetch Files=True")
    arquivo.write("Word=True")
    arquivo.write("WoW=True")
    arquivo.write("XBox Internet Explorer History=True")
    arquivo.write("Yahoo Messenger=True")
    arquivo.write("Yahoo Mail=True")
    arquivo.write("Zoom=True")
    arquivo.write("")
    arquivo.write("[Android Artifact Selection]")
    arquivo.write("AMR=True")
    arquivo.write("Torrent=True")
    arquivo.write("Accounts Information=True")
    arquivo.write("AIM=True")
    arquivo.write("Android Backups=True")
    arquivo.write("Contacts=True")
    arquivo.write("Android User Dictionary=True")
    arquivo.write("BlackBerry Messenger=True")
    arquivo.write("Bluetooth Devices=True")
    arquivo.write("Browser Activity=True")
    arquivo.write("Burner=True")
    arquivo.write("Cache.Cell=True")
    arquivo.write("Cache.Wifi=True")
    arquivo.write("Calendar=True")
    arquivo.write("Call Logs=True")
    arquivo.write("Chrome=True")
    arquivo.write("Device Information=True")
    arquivo.write("Dolphin Browser=True")
    arquivo.write("Downloads=True")
    arquivo.write("Dropbox=True")
    arquivo.write("Dynamic Application Finder=True")
    arquivo.write("Email=True")
    arquivo.write("Excel=True")
    arquivo.write("Facebook=True")
    arquivo.write("Facebook Messenger=True")
    arquivo.write("File System Information=True")
    arquivo.write("Firefox=True")
    arquivo.write("Foursquare=True")
    arquivo.write("Gmail=True")
    arquivo.write("GMX Webmail=True")
    arquivo.write("Google Analytics=True")
    arquivo.write("Google Hangouts=True")
    arquivo.write("Google Maps=True")
    arquivo.write("Google Talk=True")
    arquivo.write("Grindr=True")
    arquivo.write("Growlr=True")
    arquivo.write("Instagram=True")
    arquivo.write("Installed Applications=True")
    arquivo.write("Kik Messenger=True")
    arquivo.write("LINE=True")
    arquivo.write("Malware/Phishing URLs=True")
    arquivo.write("Meet24=True")
    arquivo.write("Oovoo=True")
    arquivo.write("PDF=True")
    arquivo.write("Pictures=True")
    arquivo.write("Pornography URLs=True")
    arquivo.write("PowerPoint=True")
    arquivo.write("Puffin Browser=True")
    arquivo.write("RebuildWeb=True")
    arquivo.write("RTF Documents=True")
    arquivo.write("Sina Weibo=True")
    arquivo.write("Skype=True")
    arquivo.write("SMS / MMS=True")
    arquivo.write("Snapchat=True")
    arquivo.write("Telegram=True")
    arquivo.write("Text Documents=True")
    arquivo.write("Textfree=True")
    arquivo.write("TextMe=True")
    arquivo.write("TextNow=True")
    arquivo.write("TextPlus=True")
    arquivo.write("TigerText=True")
    arquivo.write("Tinder=True")
    arquivo.write("Touch=True")
    arquivo.write("Twitter=True")
    arquivo.write("Uber=True")
    arquivo.write("Viber=True")
    arquivo.write("Videos=True")
    arquivo.write("VK=True")
    arquivo.write("WeChat=True")
    arquivo.write("WhatsApp=True")
    arquivo.write("Whisper=True")
    arquivo.write("Wi-Fi Profiles=True")
    arquivo.write("Word=True")
    arquivo.write("Yahoo Mail=True")
    arquivo.write("Zoom=True")
    arquivo.write("")
    arquivo.write("[iOS Artifact Selection]")
    arquivo.write("AMR=True")
    arquivo.write("Torrent=True")
    arquivo.write("AIM=True")
    arquivo.write("BlackBerry Messenger=True")
    arquivo.write("Bluetooth Devices=True")
    arquivo.write("Browser Activity=True")
    arquivo.write("Burner=True")
    arquivo.write("Calendar=True")
    arquivo.write("Chrome=True")
    arquivo.write("Dolphin Browser=True")
    arquivo.write("Dropbox=True")
    arquivo.write("Dynamic Application Finder=True")
    arquivo.write("Email=True")
    arquivo.write("Excel=True")
    arquivo.write("Facebook=True")
    arquivo.write("Facebook Messenger=True")
    arquivo.write("File System Information=True")
    arquivo.write("Foursquare=True")
    arquivo.write("GMX Webmail=True")
    arquivo.write("Google Analytics=True")
    arquivo.write("Google Hangouts=True")
    arquivo.write("Google Maps=True")
    arquivo.write("Grindr=True")
    arquivo.write("Growlr=True")
    arquivo.write("SMS / MMS=True")
    arquivo.write("Instagram=True")
    arquivo.write("Installed Applications=True")
    arquivo.write("App Cache=True")
    arquivo.write("iOS Backups=True")
    arquivo.write("Call Logs=True")
    arquivo.write("Contacts=True")
    arquivo.write("Notes=True")
    arquivo.write("Snapshots=True")
    arquivo.write("iOS Spotlight=True")
    arquivo.write("iOS User Shortcut Dictionary=True")
    arquivo.write("iOS User Word Dictionary=True")
    arquivo.write("Voice Mail=True")
    arquivo.write("Kik Messenger=True")
    arquivo.write("LINE=True")
    arquivo.write("Malware/Phishing URLs=True")
    arquivo.write("Maps=True")
    arquivo.write("Oovoo=True")
    arquivo.write("Owner Information=True")
    arquivo.write("PDF=True")
    arquivo.write("Pictures=True")
    arquivo.write("Pornography URLs=True")
    arquivo.write("PowerPoint=True")
    arquivo.write("Puffin Browser=True")
    arquivo.write("QQ=True")
    arquivo.write("RebuildWeb=True")
    arquivo.write("RTF Documents=True")
    arquivo.write("Safari=True")
    arquivo.write("Sina Weibo=True")
    arquivo.write("Skype=True")
    arquivo.write("Snapchat=True")
    arquivo.write("Telegram=True")
    arquivo.write("Text Documents=True")
    arquivo.write("Textfree=True")
    arquivo.write("TextMe=True")
    arquivo.write("TextNow=True")
    arquivo.write("TextPlus=True")
    arquivo.write("TigerText=True")
    arquivo.write("Tinder=True")
    arquivo.write("Twitter=True")
    arquivo.write("Uber=True")
    arquivo.write("Viber=True")
    arquivo.write("Videos=True")
    arquivo.write("VK=True")
    arquivo.write("WeChat=True")
    arquivo.write("WhatsApp=True")
    arquivo.write("Whisper=True")
    arquivo.write("Wi-Fi Profiles=True")
    arquivo.write("Word=True")
    arquivo.write("Yahoo Mail=True")
    arquivo.write("Yik Yak=True")
    arquivo.write("Zoom=True")
    arquivo.write("")
    arquivo.write("[Windows Phone Artifact Selection]")
    arquivo.write("SafeBrowser=True")
    arquivo.write("Flash Cookies=True")
    arquivo.write("BeBo=True")
    arquivo.write("Bing Bar=True")
    arquivo.write("Browser Activity=True")
    arquivo.write("Call Logs=True")
    arquivo.write("Chrome=True")
    arquivo.write("Dynamic Application Finder=True")
    arquivo.write("Email=True")
    arquivo.write("Excel=True")
    arquivo.write("Facebook=True")
    arquivo.write("File System Information=True")
    arquivo.write("Firefox=True")
    arquivo.write("Gmail=True")
    arquivo.write("GMX Webmail=True")
    arquivo.write("Google Analytics=True")
    arquivo.write("Google Maps=True")
    arquivo.write("Google Bar=True")
    arquivo.write("Google Plus=True")
    arquivo.write("Hotmail=True")
    arquivo.write("Hushmail=True")
    arquivo.write("Instagram=True")
    arquivo.write("Internet Explorer=True")
    arquivo.write("Jump Lists=True")
    arquivo.write("LinkedIn=True")
    arquivo.write("LNK Files=True")
    arquivo.write("Lync / Office Communicator=True")
    arquivo.write("Mailinator=True")
    arquivo.write("Malware/Phishing URLs=True")
    arquivo.write("MySpace=True")
    arquivo.write("Network Share Information=True")
    arquivo.write("Opera=True")
    arquivo.write("Operating System Information=True")
    arquivo.write("Outlook=True")
    arquivo.write("Outlook Web App=True")
    arquivo.write("Outlook Webmail=True")
    arquivo.write("PDF=True")
    arquivo.write("Pictures=True")
    arquivo.write("Pornography URLs=True")
    arquivo.write("PowerPoint=True")
    arquivo.write("RebuildWeb=True")
    arquivo.write("RTF Documents=True")
    arquivo.write("Safari=True")
    arquivo.write("Shellbags=True")
    arquivo.write("Sina Weibo=True")
    arquivo.write("Skype=True")
    arquivo.write("SMS / MMS=True")
    arquivo.write("Startup Items=True")
    arquivo.write("Text Documents=True")
    arquivo.write("Timezone Information=True")
    arquivo.write("Twitter=True")
    arquivo.write("USB Devices=True")
    arquivo.write("User Accounts=True")
    arquivo.write("Videos=True")
    arquivo.write("Flash Video Fragments=True")
    arquivo.write("Windows Event Logs=True")
    arquivo.write("Windows Phone Contacts=True")
    arquivo.write("Windows Prefetch Files=True")
    arquivo.write("Word=True")
    arquivo.write("Yahoo Mail=True")
    arquivo.write("")
    arquivo.write("[Kindle Artifact Selection]")
    arquivo.write("Accounts Information=True")
    arquivo.write("AIM=True")
    arquivo.write("Downloads=True")
    arquivo.write("Dropbox=True")
    arquivo.write("Dynamic Application Finder=True")
    arquivo.write("Email=True")
    arquivo.write("Excel=True")
    arquivo.write("Facebook=True")
    arquivo.write("File System Information=True")
    arquivo.write("Gmail=True")
    arquivo.write("GMX Webmail=True")
    arquivo.write("Google Analytics=True")
    arquivo.write("Google Maps=True")
    arquivo.write("Instagram=True")
    arquivo.write("Kik Messenger=True")
    arquivo.write("Malware/Phishing URLs=True")
    arquivo.write("PDF=True")
    arquivo.write("Pictures=True")
    arquivo.write("Pornography URLs=True")
    arquivo.write("PowerPoint=True")
    arquivo.write("RTF Documents=True")
    arquivo.write("Silk=True")
    arquivo.write("Sina Weibo=True")
    arquivo.write("Skype=True")
    arquivo.write("Text Documents=True")
    arquivo.write("Twitter=True")
    arquivo.write("Videos=True")
    arquivo.write("Word=True")
    arquivo.write("")

    # elif perfil_execucao == 'ief':

    arquivo.close()
    return


def tableautd3(tableau_id='192.168.0.149'):
    '''
    Se o servidor Windows não está mais sendo conectado, pode ser que o serviço tenha travado. 
    Para reiniciar o serviço, use os comandos:
    sc stop LanmanServer
    sc start LanmanServer
    
    Se não resolver, modifique a seguinte chave para o valor ‘3′:
    HKLM\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters\Size    
    '''
    # ABRE BROWSER
    browser = webdriver.Firefox()
    browser.get('http://' + tableau_id)
    browser.implicitly_wait(10)
    # time.sleep(2)
    browser.maximize_window()
    # LOGIN
    assert 'TD3 Web - Login' in browser.title
    elem = browser.find_element_by_id('usr')
    elem.send_keys('Profile1' + Keys.RETURN)
    elem = browser.find_element_by_id('pwd')
    elem.send_keys('password' + Keys.RETURN)
    time.sleep(5)
    # TELA PRINCIPAL
    assert 'TD3 Web - Main Menu' in browser.title
    # VERIFICA SE TEM ORIGEM
    try:
        elem = browser.find_element_by_xpath('html/body/div[8]/div[2]/div/div/a/img[1]')
    except NoSuchElementException:
        print("não achei origem")
        sys.exit(1)

    # VERIFICA SE TEM DESTINO (STORAGE)
    try:
        browser.find_element_by_xpath('html/body/div[11]/div[2]/div/div/a/img[1]')
    except NoSuchElementException:
        print("não achei destino. Vou configurar...")
        # ENTRA EM SETTINGS
        browser.find_element_by_xpath('html/body/div[10]/div/div[9]/button').click()
        time.sleep(2)
        assert 'TD3 Web - Settings' in browser.title
        browser.find_element_by_xpath('html/body/div[10]/div[2]/button[3]').click()
        # time.sleep(2)
        elem = browser.find_element_by_xpath('html/body/div[2]/div/div/div[2]/div[2]/div[1]/div/input')
        elem.clear()
        elem.send_keys('192.168.0.129')
        elem = browser.find_element_by_xpath('html/body/div[2]/div/div/div[2]/div[2]/div[2]/div/input')
        elem.clear()
        elem.send_keys('storage')
        elem = browser.find_element_by_xpath('html/body/div[2]/div/div/div[2]/div[2]/div[3]/div/input')
        elem.clear()
        elem.send_keys('sapi')
        elem = browser.find_element_by_xpath('html/body/div[2]/div/div/div[2]/div[2]/div[4]/div/input')
        elem.clear()
        elem.send_keys('sapi')
        elem = browser.find_element_by_xpath('html/body/div[2]/div/div/div[2]/div[1]/div/div/label').click()
        # time.sleep(10)
        elem = browser.find_element_by_xpath('html/body/div[2]/div/div/div[3]/button')
        elem.click()
        # time.sleep(1)
        elem = browser.find_element_by_xpath('html/body/div[10]/div[2]/button[7]')
        elem.click()
        # time.sleep(2)

    # VERIFICA SE TEM ORIGEM
    try:
        browser.find_element_by_xpath('html/body/div[8]/div[2]/div/div/a/img[1]')
    except NoSuchElementException:
        print("Não achei origem")

    # CONFIGURA DUPLICAÇÃO
    elem = browser.find_element_by_xpath('html/body/div[10]/div/div[1]/button').click()
    # time.sleep(2)
    elem = browser.find_element_by_xpath('html/body/div[18]/div[3]/button[2]').click()
    # time.sleep(2)
    elem = browser.find_element_by_xpath('html/body/div[7]/div[2]/div/input')  # EXAMINER
    elem.clear()
    elem.send_keys('SETEC/PF/PR')
    elem = browser.find_element_by_xpath('html/body/div[7]/div[3]/div/input')  # CASE ID
    elem.clear()
    elem.send_keys('')
    elem = browser.find_element_by_xpath('html/body/div[7]/div[4]/div/textarea')  # CASE NOTES
    elem.clear()
    elem.send_keys('')
    elem = Select(browser.find_element_by_id('dup-type'))  # DUPLICATION TYPE (Disk-to-File)
    elem.select_by_visible_text('Disk-to-File')
    elem = browser.find_element_by_xpath('html/body/div[7]/div[6]/div/button').click()  # DESTINATION DIR
    # time.sleep(4)
    try:
        browser.find_element_by_xpath('html/body/div[8]/div[3]/button[2]').click()
        time.sleep(2)
    except NoSuchElementException:
        print("Indo para pasta raiz")

    try:
        browser.find_element_by_xpath('html/body/div[8]/div[3]/button[2]').click()
    except NoSuchElementException:
        print("Indo para pasta raiz")
    try:
        browser.find_element_by_xpath('html/body/div[8]/div[3]/button[2]').click()
    except NoSuchElementException:
        print("Indo para pasta raiz")

    elem = browser.find_element_by_xpath('html/body/div[8]/div[3]/button[3]').click()
    # time.sleep(4)
    elem = browser.find_element_by_xpath('html/body/div[2]/div/div/div[2]/div[1]/div/input')
    elem.clear()
    elem.send_keys('Memo1234-16')
    elem = browser.find_element_by_xpath('html/body/div[2]/div/div/div[3]/div[1]/button').click()
    time.sleep(4)
    elem = browser.find_element_by_xpath('html/body/div[8]/div[3]/button[1]').click()
    # time.sleep(4)
    elem = Select(browser.find_element_by_xpath('html/body/div[7]/div[7]/div/select'))  # IMAGE DIR NAMING
    elem.select_by_visible_text('Serial + Model Number')
    elem = Select(
        browser.find_element_by_xpath('html/body/div[7]/div[8]/div/select'))  # IMAGE FILE NAMING (User Defined)
    elem.select_by_visible_text('User Defined')
    time.sleep(2)  # tem que aguardar pois o tipo Custom abre um novo campo abaixo
    elem = browser.find_element_by_xpath('html/body/div[7]/div[9]/div/input')  # IMAGE FILE NAME ()
    elem.clear()
    elem.send_keys('Item01_ItemArrecadacao01')
    elem = Select(
        browser.find_element_by_xpath('html/body/div[7]/div[10]/div/select'))  # FILE FORMAT (E01 - EnCase format)
    elem.select_by_visible_text('E01 - EnCase format')
    elem = Select(browser.find_element_by_xpath('html/body/div[7]/div[11]/div/select'))  # FILE SIZE (2GB)
    elem.select_by_visible_text('2 GB')
    elem = Select(browser.find_element_by_xpath('html/body/div[7]/div[14]/div/select'))  # ERROR GRANULARITY (Exaustive)
    elem.select_by_visible_text('Exhaustive')
    elem = Select(browser.find_element_by_xpath('html/body/div[7]/div[15]/div/select'))  # ERROR RETRY (retry once)
    elem.select_by_visible_text('Retry once')
    elem = Select(browser.find_element_by_xpath('html/body/div[7]/div[16]/div/select'))  # VERIFICATION (off)
    elem.select_by_visible_text('Off')
    # time.sleep(2)
    elem = browser.find_element_by_xpath('html/body/div[7]/div[17]/button').click()
    # time.sleep(10)

    # INICIA DUPLICAÇÃO
    elem = browser.find_element_by_xpath('html/body/div[18]/div[2]/button').click()

    # AGUARDA O FIM DA DUPLICAÇÃO
    # SE ENCONTROU O BOTÃO "OK" QUER DIZER QUE ACABOU
    print("Iniciando a duplicação")
    while browser.find_element_by_xpath('html/body/div[8]/div[1]/table/tbody/tr[1]/td/p/span').text == 'Duplicating...':
        time.sleep(10)
    print("Duplicação finalizada")
    x_status = browser.find_element_by_xpath('html/body/div[8]/div[1]/table/tbody/tr[1]/td/p/span').text
    x_tempo = browser.find_element_by_xpath('html/body/div[8]/div[1]/table/tbody/tr[2]/td/p/span').text
    x_tamanho = browser.find_element_by_xpath('html/body/div[8]/div[1]/table/tbody/tr[3]/td/p/span').text
    x_taxa = browser.find_element_by_xpath('html/body/div[8]/div[1]/table/tbody/tr[5]/td/p/span').text
    x_md5 = browser.find_element_by_xpath('html/body/div[8]/div[1]/table/tbody/tr[6]/td/p/span').text
    x_sha1 = browser.find_element_by_xpath('html/body/div[8]/div[1]/table/tbody/tr[7]/td/p/span').text
    duplicacao = {'Status': x_status, 'Tempo_decorrido': x_tempo, 'Tamanho': x_tamanho, 'Taxa': x_taxa, 'MD5': x_md5,
                  'SHA1': x_sha1}
    print(duplicacao)

    return duplicacao


def configura():
    config = configparser.ConfigParser()
    config.add_section("FERRAMENTAS")
    config.set("FERRAMENTAS", "iped", "True")
    config.set("FERRAMENTAS", "iped_sem_ocr", "True")
    config.set("FERRAMENTAS", "ief", "True")
    config.set("FERRAMENTAS", "ief-mobile", "True")
    config.set("FERRAMENTAS", "belkasoft", "False")
    config.set("FERRAMENTAS", "regripper", "False")
    config.set("FERRAMENTAS", "nirsoft", "False")
    config.set("FERRAMENTAS", "sysinternals", "False")

    config.add_section("NIRSOFT")
    config.set("NIRSOFT", "versao", "")
    config.set("NIRSOFT", "pasta", "")
    config.set("NIRSOFT", "executavel", "")
    config.set("NIRSOFT", "hash_executavel", "")
    config.set("NIRSOFT", "tipo", "Pasta")  # arquivo (só copia pasta); executável (instala)
    config.set("NIRSOFT", "origem", "")
    config.set("NIRSOFT", "profile", "")

    config.add_section("SYSINTERNALS")
    config.set("SYSINTERNALS", "versao", "")
    config.set("SYSINTERNALS", "pasta", "")
    config.set("SYSINTERNALS", "executavel", "")
    config.set("SYSINTERNALS", "hash_executavel", "")
    config.set("SYSINTERNALS", "tipo", "Pasta")  # arquivo (só copia pasta); executável (instala)
    config.set("SYSINTERNALS", "origem", "")
    config.set("SYSINTERNALS", "profile", "")

    config.add_section("REGRIPPER")
    config.set("REGRIPPER", "versao", "")
    config.set("REGRIPPER", "pasta", "")
    config.set("REGRIPPER", "executavel", "")
    config.set("REGRIPPER", "hash_executavel", "")
    config.set("REGRIPPER", "tipo", "Pasta")  # arquivo (só copia pasta); executável (instala)
    config.set("REGRIPPER", "origem", "")
    config.set("REGRIPPER", "profile", "")

    config.add_section("BELKASOFT")
    config.set("REGRIPPER", "versao", "")
    config.set("REGRIPPER", "pasta", "")
    config.set("REGRIPPER", "executavel", "")
    config.set("REGRIPPER", "hash_executavel", "")
    config.set("REGRIPPER", "tipo", "Pasta")  # arquivo (só copia pasta); executável (instala)
    config.set("REGRIPPER", "origem", "")
    config.set("REGRIPPER", "profile", "")

    config.add_section("IEF")
    config.set("IEF", "versao", "6.8.2.3062")
    config.set("IEF", "pasta", "C:/Program Files (x86)/Internet Evidence Finder")
    config.set("IEF", "executavel", "IEF.exe")
    config.set("IEF", "hash_executavel", "21cd66cce2841fadd3349f625c043e04")
    config.set("IEF", "tipo", "Executavel")  # arquivo (só copia pasta); executavel (instala)
    config.set("IEF", "origem", r"C:\Users\PCF-\Downloads\IEFv682.3062setup.exe")
    config.set("IEF", "parametros", "/SILENT /NORESTART /CLOSEAPPLICATIONS")  # campo que só existe no tipo EXECUTAVEL

    config.add_section("IEF-MOBILE")
    config.set("IEF-MOBILE", "versao", "6.8.2.3062")
    config.set("IEF-MOBILE", "pasta", "C:/Program Files (x86)/Internet Evidence Finder")
    config.set("IEF-MOBILE", "executavel", "IEF.exe")
    config.set("IEF-MOBILE", "hash_executavel", "21cd66cce2841fadd3349f625c043e04")
    config.set("IEF-MOBILE", "tipo", "Executavel")  # arquivo (só copia pasta); executavel (instala)
    config.set("IEF-MOBILE", "origem", r"C:\Users\PCF-\Downloads\IEFv682.3062setup.exe")
    config.set("IEF-MOBILE", "parametros",
               "/SILENT /NORESTART /CLOSEAPPLICATIONS")  # campo que só existe no tipo EXECUTAVEL

    config.add_section("IPED_SEM_OCR")
    config.set("IPED_SEM_OCR", "versao", "3.10")
    config.set("IPED_SEM_OCR", "pasta", "C:/IPED-3.10_SEM_OCR")
    config.set("IPED_SEM_OCR", "executavel", "iped.jar")
    config.set("IPED_SEM_OCR", "hash_executavel", "ecb6ee867cf2fe2dc6917a33333607bf")
    config.set("IPED_SEM_OCR", "tipo", "Arquivo")  # arquivo (só copia pasta); executável (instala)
    config.set("IPED_SEM_OCR", "origem", "R:/IPED-3.10_SEM_OCR")
    config.set("IPED_SEM_OCR", "profile", "")

    config.add_section("IPED")
    config.set("IPED", "versao", "3.10")
    config.set("IPED", "pasta", "C:/IPED-3.10")
    config.set("IPED", "executavel", "iped.jar")
    config.set("IPED", "hash_executavel", "ecb6ee867cf2fe2dc6917a33333607bf")
    config.set("IPED", "tipo", "Arquivo")  # arquivo (só copia pasta); executável (instala)
    config.set("IPED", "origem", "R:/IPED-3.10")
    config.set("IPED", "profile", "")

    arquivo = open("CLIENTE.ini", "w")
    config.write(arquivo)
    arquivo.close()
    return


# Função para criar/apagar mapeamento de rede
def mapear(endereco_ip, compartilhamento, usuario, senha):
    print(" IP:", endereco_ip, " compartilhamento:", compartilhamento, " usuario:", usuario, " Senha:", senha)
    mapeamento = ''
    if estaRodandoLinux():
        # mapeamento no Linux
        comando = ''
    else:
        # mapeamento no Windows
        comando = "net use * \\\\" + endereco_ip + "\\" + compartilhamento + " /USER:" + usuario + " " + senha
        resultado = subprocess.check_output(comando)
        mapeamento = resultado.decode("windows-1252")[10] + ":"  # Pega o 10º caractere que é a letra da unidade criada
        # print("Foi criada a unidade " + mapeamento + ":")
    return mapeamento


# Apaga o mapeamento
def apagar_mapeamento(mapeamento):
    if estaRodandoLinux():
        # mapeamento no Linux
        comando = ''
    else:
        # mapeamento no Windows
        mapeamento += ":"
        comando = "net use " + mapeamento + " /del"
        resultado = subprocess.check_output(comando)
        print(resultado)

    return


def generate_file_md5(rootdir, filename, blocksize=2 ** 20):
    m = hashlib.md5()
    with open(os.path.join(rootdir, filename), "rb") as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            m.update(buf)
    return m.hexdigest()


# Retorna a listagem das ferramentas que estão habilitadas
def lista_ferramentas_habilitadas():
    listagem_ferramentas_habilitadas = []
    config = configparser.ConfigParser()
    config.read("CLIENTE.ini")
    for key in config['FERRAMENTAS']:
        if config.getboolean("FERRAMENTAS", key):
            listagem_ferramentas_habilitadas += [key]
    return listagem_ferramentas_habilitadas


# Inicia a execução das tarefas
def executa_tarefas(qual_tarefa):
    # Em desenvolvimento não executa, para ganhar tempo
    if not Gdesenvolvimento:
        assegura_comunicacao_servidor_sapi()

    # CONECTA COM O SERVIDOR E VERIFICA SE EXISTEM TAREFAS PARA CADA FERRAMENTA
    print_log_dual("Solicitando tarefa ao servidor do tipo: " + qual_tarefa)
    (disponivel, tarefa) = sapisrv_obter_iniciar_tarefa(qual_tarefa)

    # Para ver o conjunto completo, descomentar a linha abaixo
    var_dump(tarefa)

    # Se não tem nenhuma tarefa disponível, dorme um pouco
    if not disponivel:
        print_log_dual("Servidor informou que não existe tarefa " + qual_tarefa + " para processamento.")
        return

    # continue

    # Ok, temos trabalho a fazer
    # ------------------------------------------------------------------
    # Montar storage
    # ------------------------------------------------------------------
    # Teria que montar o storage (caso a montagem seja dinâmica)
    # Os dados do storage estão em tarefa["dados_storage"]
    # Cria o mapeamento do storage
    # É montado primeiro para saber o local de montagem/letra da unidade
    letra = mapear(endereco_ip=tarefa["dados_storage"]["maquina_ip"],
                   compartilhamento=tarefa["dados_storage"]["pasta_share"], usuario=tarefa["dados_storage"]["usuario"],
                   senha=tarefa["dados_storage"]["senha"])

    # O sistema retorna um conjunto bastante amplo de dados
    # Os mais relevantes estão aqui
    codigo_tarefa = tarefa["codigo_tarefa"]  # Identificador único da tarefa
    caminho_origem = letra + "/" + tarefa["caminho_origem"]
    caminho_destino = letra + "/" + tarefa["caminho_destino"]

    print_log_dual("Processando tarefa: ", codigo_tarefa)

    # Conferir se pasta/arquivo de origem está ok
    # ------------------------------------------------------------------
    # O caminho de origem pode indicar um arquivo (.E01) ou uma pasta
    # Neste ponto, seria importante verificar se esta origem está ok
    # Ou seja, se existe o arquivo ou pasta de origem
    if os.path.exists(caminho_origem):
        print_log_dual("Caminho de origem (", caminho_origem, "): localizado")
    else:
        print_log_dual("Caminho de origem (", caminho_origem, "): não localizado. Saindo.")
        sys.exit(1)

    # Criar pasta de destino
    # ------------------------------------------------------------------
    # Teria que criar a pasta de destino, caso ainda não exista
    # Se a pasta de destino já existe...opa, pode ter algo errado.
    # Neste cenário, teria que conferir se a pasta não tem nada
    # de útil (indicando alguma concorrência....ou processo abortado)
    if os.path.exists(caminho_destino):
        print_log_dual("Caminho de destino (", caminho_destino, "): Já existe. Verificando se possui arquivos.")
        if not os.listdir(caminho_destino):
            print_log_dual("Caminho de destino (", caminho_destino, "): Já existe, mas está vazia. Pode continuar.")
        else:
            print_log_dual("Caminho de destino (", caminho_destino, "): Já existe, mas não está vazia. Saindo.")
            sys.exit(1)
    else:
        os.makedirs(caminho_destino)
        print_log_dual("Caminho de destino (", caminho_destino, "): Criado")

    # Fork para executar e esperar resposta
    # ------------------------------------------------------------------
    # Em um agente de verdade, aqui teria que fazer um fork
    # O programa secundário iria invocar o programa externo que 
    # executa a tarefa, e o programa principal se
    # encarregaria de controlar a execução
    print_log_dual("Invocando programa ", qual_tarefa, " e aguardando resultado")
    # pid = os.fork()
    # if pid == 0:
    #    print_log_dual("invocado programa: "+comando)
    #    # Executa o programa externo e fica esperando o resultado
    #    os.system(comando) # Se mata o pai, morre também...melhorar isto
    #    print_log_dual("Programa externo encerrou")
    #    sys.exit()

    # Programa principal controla a execução
    # ------------------------------------------------------------------
    codigo_situacao_tarefa = GEmAndamento
    atualizar_status_tarefa(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=codigo_situacao_tarefa,
        status=texto_status
    )

    if qual_tarefa == 'ief-mobile':
        if ief(origem=caminho_origem, destino=caminho_destino + "/ief", tipo_execucao='cli',
               perfil_execucao='ief-mobile'):
            texto_status = "Finalizado com sucesso"
            codigo_situacao_tarefa = GFinalizadoComSucesso
            atualizar_status_tarefa(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=codigo_situacao_tarefa,
                status=texto_status
            )
        return

    elif qual_tarefa == 'ief':
        if ief(origem=caminho_origem, destino=caminho_destino + "/ief", tipo_execucao='cli', perfil_execucao='ief'):
            texto_status = "Finalizado com sucesso"
            codigo_situacao_tarefa = GFinalizadoComSucesso
            atualizar_status_tarefa(
                codigo_tarefa=codigo_tarefa,
                codigo_situacao_tarefa=codigo_situacao_tarefa,
                status=texto_status
            )
        return

    terminou = False
    codigo_situacao_tarefa = GEmAndamento
    atualizar_status_tarefa(
        codigo_tarefa=codigo_tarefa,
        codigo_situacao_tarefa=codigo_situacao_tarefa,
        status=texto_status
    )

    apagar_mapeamento(letra)
    # Finaliza

    resposta_origem = 'R:/Dropbox/DPF/____ PERICIA_JATO ____/TESTE/Item02_ItemArrecadacao03/Item02_ItemArrecadacao03.E01'
    resposta_pasta_destino = 'R:/Dropbox/DPF/____ PERICIA_JATO ____/TESTE/'
    resposta_ferramenta = pedidos.json()
    if resposta_ferramenta['args']['ferramenta'] in ['IPED_SEM_OCR', 'IPED']:
        arquivo_ferramenta = config.get(lista_ferramentas[x], "pasta") + "/" + config.get(lista_ferramentas[x],
                                                                                          "executavel")
        iped(resposta_origem, resposta_pasta_destino, arquivo_ferramenta)
    elif resposta_ferramenta['args']['ferramenta'] == 'IEF':
        resposta_pasta_destino += "ief"
        if not os.path.exists(resposta_pasta_destino):
            ief(resposta_origem, resposta_pasta_destino, arquivo_ferramenta, 'cli')
    elif resposta_ferramenta['args']['ferramenta'] == 'TABLEAU_TD3':
        print("Usando Tableau TD3")
        tableautd3()
    return


# Cria arquivo VHDX
# Memorando = identificação do memorando, com a equipe e o item, se for o caso
# Pasta = local no servidor em que são criados os compartilhamentos (padrão = S:\STORAGE)
# Criptografado = se vai usar o bitlocker ou não
# Ex: vhdx_cria("Memo.1234-15-LJ37", "S:/STORAGE", False)
def vhdx_cria(memorando, pasta, criptografado=False):
    # Inicialmente deve-se identificar se o cliente possui a ferramenta "STORAGE" habilitada
    config = configparser.ConfigParser()
    config.read("CLIENTE.ini")
    if not config.get("FERRAMENTAS", "storage"):
        erro_fatal("A ferramenta STORAGE não está habilitada neste computador.")
    if not os.path.exists(pasta):
        erro_fatal("A pasta de destino [" + pasta + "] não foi encontrada.")
    # Para saber qual a pasta onde estão os arquivos VHDX, deve ser consultado o CLIENTE.INI
    origem_vhdx = config.get("STORAGE", "pasta")
    # Se for criptografado, usa o arquivo SAPI_BITLOCKER.vhdx, se não for, usa o arquivo SAPI.vhdx
    if criptografado:
        arquivo_vhdx = "/SAPI_BITLOCKER.vhdx"
    elif:
        arquivo_vhdx = "/SAPI.vhdx"
    # concatena o nome da pasta, o memorando e a extensão VHDX
    pasta += "/" + memorando + ".vhdx"
    # verifica se já existe o nome do arquivo VHDX na pasta designada
    if os.path.exists(origem_vhdx + arquivo_vhdx):
        # agora pode copiar da origem para o destino
        shutil.copy(origem_vhdx + arquivo_vhdx, pasta)
    return


# Monta arquivo VHDX e compartilha via rede
# Memorando = identificação do memorando, com a equipe e o item, se for o caso
# Pasta = local no servidor em que são criados os compartilhamentos (padrão = S:\STORAGE)
# Criptografado = se vai usar o bitlocker ou não
# Ex: vhdx_monta("Memo.1234-15-LJ37", "S:/STORAGE", True)
# Comando do PowerShell: Mount-VHD -Path "C:\Users\Brink\Desktop\Non-Insider W10.vhdx"
def vhdx_monta(memorando, pasta, criptografado=False):
    # Cria a pasta se ela não existir
    if not os.path.exists(pasta):
        cria_pasta_se_nao_existe(pasta)
    elif:
        # Se a pasta existir, verifica se existem arquivos dentro dela. Para usar ponto de montagem a pasta deve estar vazia
        if os.listdir(pasta) != []:
            erro_fatal("A pasta [" + pasta + "] não está vazia.")


    p = subprocess.Popen(["powershell.exe",
                          ""],
                         stdout=sys.stdout)
    p.communicate()


    return


# Desmonta arquivo VHDX
# Comando do PowerShell: Dismount-VHD -Path "C:\Users\Brink\Desktop\Non-Insider W10.vhdx"
def vhdx_desmonta(pasta):
    return


if __name__ == "__main__":
    hora_inicio = time.time()
    print_log_dual('Início da execução do cliente')
    main()
    hora_fim = time.time()
    duracao = hora_fim - hora_inicio
    print_log_dual('Tempo decorrido:' + str(duracao) + 'seconds')
    print_log_dual('Programa finalizado normalmente.')
