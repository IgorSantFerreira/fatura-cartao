@echo off
rem Abre o Raio-X da fatura para uma DEMONSTRACAO, so com faturas ficticias.
rem Todos os dados (inclusive a base "Minhas faturas" e as categorias escolhidas) ficam numa pasta so da demonstracao:
rem as suas faturas reais, metas, rotulos e categorias nao sao usados nem alterados.
rem Feche esta janela para parar o app. Roteiro: docs\DEMONSTRACAO.md
cd /d "%~dp0"
set "DEMO=%LOCALAPPDATA%\fatura_cartao\demonstracao"
set "FATURA_REGRAS=%DEMO%\minhas\regras_usuario.json"
set "FATURA_METAS=%DEMO%\minhas\metas_usuario.json"
set "FATURA_HISTORICO=%DEMO%\minhas\historico"
set "FATURA_ROTULOS=%DEMO%\minhas\rotulos.json"
set "FATURA_REJEITADAS=%DEMO%\minhas\sugestoes_rejeitadas.json"
set "FATURA_SIMULADAS=%DEMO%\simuladas"
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
if not exist "faturas_sinteticas\faturas\Nubank_2026-10-25.csv" %PY% ferramentas\gerar_faturas_sinteticas.py
%PY% ferramentas\preparar_demonstracao.py --com-rotulos
if errorlevel 1 (
    echo Nao consegui preparar a base da demonstracao. Veja a mensagem acima.
    pause
    exit /b 1
)
%PY% -m streamlit run src\app.py --server.address localhost --browser.gatherUsageStats false
