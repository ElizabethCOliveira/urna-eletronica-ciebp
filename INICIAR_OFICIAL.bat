@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 urna.py 
    goto fim
)
where python >nul 2>nul
if not errorlevel 1 (
    python urna.py 
    goto fim
)
echo Python nao encontrado. Abra LEIA_PRIMEIRO.html para instalar.
:fim
if errorlevel 1 echo Ocorreu um erro. Registre a mensagem acima e consulte o guia.
pause
