@echo off
rem Abre o Raio-X da fatura no navegador. Feche esta janela para parar o app.
cd /d "%~dp0"
py -m streamlit run src\app.py --server.address localhost --browser.gatherUsageStats false
