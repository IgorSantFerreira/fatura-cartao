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
if not exist "faturas_sinteticas\faturas\Nubank_2026-10-25.csv" py ferramentas\gerar_faturas_sinteticas.py
py ferramentas\preparar_demonstracao.py --com-rotulos
if errorlevel 1 (
    echo Nao consegui preparar a base da demonstracao. Veja a mensagem acima.
    pause
    exit /b 1
)
py -m streamlit run src\app.py --server.address localhost --browser.gatherUsageStats false
