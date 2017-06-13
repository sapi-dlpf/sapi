@echo off
REM ====================================================================================================================
REM Este bat é utilizado para executar o sapi_iped
REM Foi projetado para ser acionado pelo task scheduler, sendo invocado sempre que a máquina for ligada
REM e em intervalos regulares de tempo, para garantir uma alta tolerância a falhas
REM ====================================================================================================================

echo %time%
pause

:repete

@echo off
echo === sapi_iped_executar versão 1.3 ===
@echo Iniciando em: %date% %time%

REM ===== Monta nome do arquivo de log ====
::for 30.10.2016 dd.MM.yyyy
if %date:~2,1%==. set d=%date:~-4%%date:~3,2%%date:~,2%
::for 10/30/2016 MM/dd/yyyy
if %date:~2,1%==/ set d=%date:~-4%%date:~,2%%date:~3,2%
::for 2016-10-30 yyyy-MM-dd
if %date:~4,1%==- set d=%date:~,4%%date:~5,2%%date:~-2%
::variable %d% have now value: 2016103 (yyyyMMdd)
set t=%time::=%
set t=%t:,=%
set nome_arquivo_log=sapi_log_%d%_%t%.txt

REM Substitui espaços por zeros
set nome_arquivo_log=%nome_arquivo_log: =0%

echo Arquivo de log associado: %nome_arquivo_log%

REM ====== Atualização ================
REM Inicialmente é feito uma atualização, copiando arquivos do servidor de deployment
@echo on
python e:\sistema\sapi_iped\sapi_atualiza_iped.py --background --log e:/sistema/log/%nome_arquivo_log%
@echo off
@echo Concluido atualizaçao em: %date% %time%

REM ====== Execução ================
REM Agora que já está atualizado, executa o sapi_iped
REM Se durante a execução do sapi_iped, o servidor informar que existe uma nova versão
REM o sapi_iped encerrará, fazendo com que no próximo ciclo do loop seja feita a atualização
@echo on
python e:\sistema\sapi_iped\sapi_iped.py --background --log e:/sistema/log/%nome_arquivo_log%
@echo off
@echo Concluido execução em: %date% %time%

REM echo Simula uma finalizacao do bat, o que na pratica nunca acontece
REM exit

@echo Repete loop de atualização-execução
@echo .
@echo .
GOTO repete