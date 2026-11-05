# Nenhum estabelecimento da fatura real do usuário pode aparecer
# nos arquivos que vão para o git. A fatura real (tests/dados/, ignorada pelo git) só existe no computador
# do usuário; numa cópia sem ela o teste é pulado.

import subprocess
from pathlib import Path

import pytest

import fatura as ft

PASTA = Path(__file__).parent
RAIZ = PASTA.parent
ARQUIVO_REAL = PASTA / 'dados' / 'Nubank_2026-11-25.csv'
# Textos genéricos do Nubank/Uber/metrô e marcas presentes nas regras; cada inclusão aqui precisa de justificativa.
PERMITIDOS = {'pagamento recebido', 'emv metro', 'uber uber *trip help.u', 'iof de compra internacional',
              'estorno de compra (ifood)', 'iof por fatura atrasada', 'juros por fatura atrasada',
              'multa por fatura atrasada', 'valor pendente do mes anterior', 'amazon', 'fibra'}


def test_nenhum_estabelecimento_da_fatura_real_nos_arquivos_que_vao_para_o_git():
    if not ARQUIVO_REAL.exists():
        pytest.skip('fatura real não está nesta cópia')
    chaves = {ft.chave_estabelecimento(d) for d in ft.ler_csv(ARQUIVO_REAL.read_bytes())['descricao']}
    chaves = {c for c in chaves - PERMITIDOS if len(c) >= 5}
    saida = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=RAIZ, capture_output=True, text=True, check=True).stdout
    achados = []
    for nome in filter(None, saida.splitlines()):
        texto = ft.normalizar((RAIZ / nome).read_text(encoding='utf-8', errors='replace'))
        achados += [(nome, c) for c in chaves if c in texto]
    assert achados == [], len(achados)
