@REM MODO PRODUÇÃO
REM @Echo off
REM powershell -noprofile -command "&{ start-process powershell -ArgumentList '-noprofile -NonInteractive -WindowStyle Hidden -file r:\storage\monta_sapi.ps1 %1 %2' -verb RunAs}"

REM Modo desenvolvimento:
start /wait powershell -noprofile -command "&{ start-process powershell -ArgumentList '-noexit -noprofile -file r:\storage\monta_sapi.ps1 %1 %2' -verb RunAs}"
REM Precisa do comando no powershell:
REM  Set-ExecutionPolicy -ExecutionPolicy unrestricted

