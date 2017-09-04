@echo off
REM ====================================================================================================================
REM Este bat é utilizado para executar o sapi_iped
REM Foi projetado para ser acionado pelo task scheduler, sendo invocado sempre que a máquina for ligada
REM e em intervalos regulares de tempo, para garantir uma alta tolerância a falhas
REM ====================================================================================================================

:repete

@echo off
echo === sapi_iped_executar versão 1.5 ===

REM ====== Atualização ================
REM Inicialmente é feito uma atualização, copiando arquivos do servidor de deployment
@echo on
python e:\sistema\sapi_iped\sapi_atualiza_iped.py --background --logdir e:/sistema/log
@echo off
@echo sapi_atualiza_iped finalizou em em: %date% %time%

REM ====== Execução ================
REM Agora que já está atualizado, executa o sapi_iped
REM Se durante a execução do sapi_iped, o servidor informar que existe uma nova versão
REM o sapi_iped encerrará, fazendo com que no próximo ciclo do loop seja feita a atualização
@echo on
python e:\sistema\sapi_iped\sapi_iped.py --background --logdir e:/sistema/log
@echo off
@echo sapi_iped finalizou em: %date% %time%

REM echo Simula uma finalizacao do bat, o que na pratica nunca acontece
REM exit

@echo Repete loop de atualização-execução
@echo .
@echo .
GOTO repete