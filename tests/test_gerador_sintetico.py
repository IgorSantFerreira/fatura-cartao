# Propriedades das faturas sintéticas geradas por ferramentas/gerar_faturas_sinteticas.py.

import csv
import importlib.util
from datetime import date
from pathlib import Path

import pytest

import fatura as ft
import historico as hist


PASTA = Path(__file__).parent
ARQUIVO_GERADOR = PASTA.parent / 'ferramentas' / 'gerar_faturas_sinteticas.py'
ARQUIVO_REAL = PASTA / 'dados' / 'Nubank_2026-11-25.csv'
# Textos que o próprio Nubank (ou Uber/metrô) gera iguais para todo mundo: não são dado pessoal.
TEXTOS_DO_NUBANK = {
      'pagamento recebido', 'valor pendente do mes anterior', 'iof de compra internacional'
    , 'multa por fatura atrasada', 'juros por fatura atrasada', 'iof por fatura atrasada'
    , 'estorno de compra (ifood)', 'uber uber *trip help.u', 'emv metro'
}


def carregar_gerador():
    especificacao = importlib.util.spec_from_file_location('gerador', ARQUIVO_GERADOR)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope='module')
def geradas(tmp_path_factory):
    gerador = carregar_gerador()
    pasta = tmp_path_factory.mktemp('sinteticas')
    gerador.gravar(gerador.gerar(13, 2026, date(2025, 10, 25)), pasta)
    faturas = {}
    for arquivo in sorted((pasta / 'faturas').glob('*.csv')):
        faturas[arquivo.name] = ft.montar_fatura(ft.ler_csv(arquivo.read_bytes()), {})
    with open(pasta / 'gabarito.csv', encoding='utf-8') as arquivo:
        gabarito = list(csv.DictReader(arquivo))
    return pasta, faturas, gabarito


def test_treze_faturas_que_o_app_le_com_datas_dentro_do_ciclo(geradas):
    pasta, faturas, gabarito = geradas
    assert list(faturas) == [f'Nubank_{ft.somar_meses(date(2025, 10, 25), mes).isoformat()}.csv' for mes in range(13)]
    for nome, fatura in faturas.items():
        vencimento = ft.vencimento_do_nome(nome)
        ciclo = ft.ciclo(vencimento)
        datas = fatura['data'].dt.date
        assert datas.min() >= ciclo['inicio'] and datas.max() <= ciclo['ultimo_dia'], nome
        assert 35 <= len(fatura) <= 70, nome


def test_gabarito_bate_com_os_csvs(geradas):
    pasta, faturas, gabarito = geradas
    assert len(gabarito) == sum(len(fatura) for fatura in faturas.values())
    assert {linha['categoria_certa'] for linha in gabarito} <= set(ft.CATEGORIAS)
    assert ft.A_CLASSIFICAR not in {linha['categoria_certa'] for linha in gabarito}
    for linha in gabarito:
        fatura = faturas[linha['fatura']]
        centavos = ft.valor_em_centavos(ft.limpar_valor(linha['amount']), True)
        iguais = fatura[(fatura['descricao'] == linha['title']) & (fatura['centavos'] == centavos)]
        assert len(iguais) >= 1, linha


def test_mesma_semente_gera_os_mesmos_arquivos(geradas, tmp_path):
    pasta, faturas, gabarito = geradas
    gerador = carregar_gerador()
    gerador.gravar(gerador.gerar(13, 2026, date(2025, 10, 25)), tmp_path)
    for arquivo in (pasta / 'faturas').glob('*.csv'):
        assert (tmp_path / 'faturas' / arquivo.name).read_bytes() == arquivo.read_bytes()
    assert (tmp_path / 'gabarito.csv').read_bytes() == (pasta / 'gabarito.csv').read_bytes()


def test_assinaturas_fixas_sao_achadas_pelo_app(geradas):
    pasta, faturas, gabarito = geradas
    montadas = [
        {'vencimento': ft.vencimento_do_nome(nome), 'rotulo': nome, 'completa': True, 'fatura': fatura}
        for nome, fatura in faturas.items()
    ]
    fixos = hist.recorrentes(montadas)
    por_par = {(linha.estabelecimento, int(linha.centavos)): linha for linha in fixos.itertuples(index=False)}
    assert por_par[('Netflix.Com', 4490)].faturas == 13
    assert por_par[('Vivo Fibra', 10990)].faturas == 13
    # Reajuste no meio do período: o valor antigo deixa de ser cobrado, o novo continua.
    assert bool(por_par[('Dl*Deezer Premium', 2290)].ativa) is False
    assert bool(por_par[('Dl*Deezer Premium', 2490)].ativa) is True
    # Assinatura cancelada no período.
    assert bool(por_par[('Globoplay', 2790)].ativa) is False


def test_regras_do_app_nunca_contradizem_o_gabarito_e_deixam_parte_a_classificar(geradas):
    # Propriedade do gerador: os nomes que as regras reconhecem estão na categoria certa; o resto fica
    # "A classificar". É ali que o modelo de ML pode ganhar das regras.
    pasta, faturas, gabarito = geradas
    compras = [linha for linha in gabarito if linha['categoria_certa'] not in [ft.PAGAMENTO, ft.SALDO_ANTERIOR, ft.ENCARGOS]]
    erradas = 0
    a_classificar = 0
    for linha in compras:
        centavos = ft.valor_em_centavos(ft.limpar_valor(linha['amount']), True)
        categoria = ft.classificar(linha['title'], centavos)[0]
        if categoria == ft.A_CLASSIFICAR:
            a_classificar = a_classificar + 1
        elif categoria != linha['categoria_certa']:
            erradas = erradas + 1
    assert erradas == 0
    assert 0.15 <= a_classificar / len(compras) <= 0.40


def test_nenhum_estabelecimento_da_fatura_real(geradas):
    pasta, faturas, gabarito = geradas
    if not ARQUIVO_REAL.exists():
        pytest.skip('fatura real (tests/dados) não está nesta cópia')
    reais = {ft.chave_estabelecimento(descricao) for descricao in ft.ler_csv(ARQUIVO_REAL.read_bytes())['descricao']}
    sinteticos = {ft.chave_estabelecimento(linha['title']) for linha in gabarito}
    assert (reais & sinteticos) <= TEXTOS_DO_NUBANK


def test_parcelas_seguem_mes_a_mes(geradas):
    pasta, faturas, gabarito = geradas
    vistas = {}
    for nome, fatura in faturas.items():
        for item in fatura[fatura['parcela_total'].notna()].itertuples(index=False):
            vistas.setdefault((item.chave, int(item.parcela_total), int(item.centavos)), []).append((nome, int(item.parcela_atual)))
    assert len(vistas) >= 5
    for serie, ocorrencias in vistas.items():
        numeros = [numero for nome, numero in ocorrencias]
        assert numeros == list(range(numeros[0], numeros[0] + len(numeros))), serie


# ---------------------------------------------------------------- casos-limite

def test_dia_da_semana_tem_relacao_com_a_categoria_nas_compras_ocasionais(geradas):
    from scipy.stats import chi2_contingency
    import pandas as pd
    pasta, faturas, gabarito = geradas
    tabela = pd.DataFrame(gabarito)
    ocasionais = tabela[tabela['comportamento'] == 'ocasional']
    contagem = pd.crosstab(ocasionais['categoria_certa'], pd.to_datetime(ocasionais['date']).dt.dayofweek)
    p_valor = chi2_contingency(contagem)[1]
    assert p_valor < 0.05, p_valor
