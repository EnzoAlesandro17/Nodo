@echo off
rem Crea el entorno virtual (.venv) de Nodo e instala lo que necesita. Se corre una sola vez por PC.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv || goto error
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto error
echo.
echo Listo. Para abrir Nodo usa iniciar_nodo.bat
pause
exit /b 0
:error
echo.
echo Algo fallo. Revisa que Python este instalado (python.org, con "Add to PATH").
pause
exit /b 1
