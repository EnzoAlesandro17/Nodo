@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Falta el entorno virtual. Corre primero crear_entorno.bat
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" main.pyw
