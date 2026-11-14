@echo off
rem Abre o Raio-X da fatura no navegador. Feche esta janela para parar o app.
cd /d "%~dp0"
rem Usa o primeiro comando de Python (py, python ou python3) que tiver as bibliotecas do app instaladas.
set "PY="
for %%P in (py python python3) do if not defined PY %%P -c "import streamlit, sklearn, plotly, pandas" >nul 2>nul && set "PY=%%P"
if not defined PY (
    echo Nao encontrei um Python com as bibliotecas do app instaladas.
    echo Instale o Python em https://www.python.org/downloads/ marcando "Add python.exe to PATH"
    echo e depois rode nesta pasta:  py -m pip install -r requirements.txt
    echo Se o comando py nao existir, use:  python -m pip install -r requirements.txt
    pause
    exit /b 1
)
%PY% -m streamlit run src\app.py --server.address localhost --browser.gatherUsageStats false
