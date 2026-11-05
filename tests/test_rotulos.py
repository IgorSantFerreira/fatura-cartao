from datetime import date
from pathlib import Path

import pytest

import fatura as ft
import historico as hist
import rotulos as rt


# Fatura de exemplo 100% fictícia (tests/exemplo.py): nenhum dado real nos testes.
from exemplo import CONTEUDO_EXEMPLO


@pytest.fixture
def fatura_real():
    return ft.montar_fatura(ft.ler_csv(CONTEUDO_EXEMPLO), {})


def montar(texto, regras=None):
    return ft.montar_fatura(ft.ler_csv(('date,title,amount\n' + texto).encode('utf-8')), regras or {})


def test_para_conferir_deixa_de_fora_pagamento_saldo_estorno_e_encargos(fatura_real):
    itens = rt.para_conferir(fatura_real, {})
    assert len(itens) == 36
    nomes = set(itens['estabelecimento'])
    assert 'Pagamento recebido' not in nomes
    assert 'Valor pendente do mês anterior' not in nomes
    assert not any('Estorno' in nome or 'IOF' in nome or 'Multa' in nome or 'Juros' in nome for nome in nomes)
    # Um item por estabelecimento, somando os lançamentos.
    uber = itens[itens['estabelecimento'] == 'Uber Uber *Trip Help.U'].iloc[0]
    assert uber['lancamentos'] == 3
    assert uber['centavos'] == 4750
    assert int(itens['lancamentos'].sum()) == 53 - 5 - 1 - 2
    assert not itens['conferido'].any()


def test_conferir_grava_rotulo_mesmo_concordando_com_as_regras(fatura_real):
    itens = rt.para_conferir(fatura_real, {})
    escolhas = {
          'auto posto girassol': (ft.TRANSPORTE, True)
        , 'zarpa': (ft.COMPRAS, True)
        , 'conectanet': (ft.CASA, False)
    }
    rotulos, regras, conferidos, removidos = rt.aplicar_conferencia({}, {}, itens, escolhas)
    assert rotulos == {'auto posto girassol': ft.TRANSPORTE, 'zarpa': ft.COMPRAS}
    # Concordar com a regra não cria exceção; corrigir cria. Não conferido não muda nada.
    assert regras == {'zarpa': ft.COMPRAS}
    assert (conferidos, removidos) == (2, 0)


def test_desmarcar_remove_o_rotulo_e_a_classificar_conferido_e_recusado(fatura_real):
    itens = rt.para_conferir(fatura_real, {'zarpa': ft.COMPRAS})
    assert bool(itens.loc[itens['chave'] == 'zarpa', 'conferido'].iloc[0]) is True
    assert itens.loc[itens['chave'] == 'zarpa', 'categoria_sugerida'].iloc[0] == ft.COMPRAS
    rotulos, regras, conferidos, removidos = rt.aplicar_conferencia({'zarpa': ft.COMPRAS}, {}, itens, {'zarpa': (ft.COMPRAS, False)})
    assert rotulos == {}
    assert removidos == 1
    with pytest.raises(ValueError, match='Escolha uma categoria'):
        rt.aplicar_conferencia({}, {}, itens, {'conectanet': (ft.A_CLASSIFICAR, True)})


def test_registrar_escolha_so_para_estabelecimento_rotulavel_e_categoria_de_compra(fatura_real):
    assert rt.registrar_escolha({}, fatura_real, 'zarpa', ft.COMPRAS) == {'zarpa': ft.COMPRAS}
    assert rt.registrar_escolha({}, fatura_real, 'pagamento recebido', ft.COMPRAS) == {}
    assert rt.registrar_escolha({}, fatura_real, 'zarpa', ft.PAGAMENTO) == {}
    assert rt.registrar_escolha({'zarpa': ft.COMPRAS}, fatura_real, 'zarpa', None) == {}


def test_rotulos_salvar_carregar_e_invalidos(tmp_path):
    caminho = str(tmp_path / 'rotulos.json')
    assert rt.carregar_rotulos(caminho) == ({}, None)
    rt.salvar_rotulos(caminho, {'fibra': ft.CASA})
    assert rt.carregar_rotulos(caminho) == ({'fibra': ft.CASA}, None)
    for conteudo in ['{quebrado', '[]', '{"fibra": "Inventada"}', '{"fibra": "A classificar"}', '{"x": "Pagamento da fatura"}']:
        Path(caminho).write_text(conteudo, encoding='utf-8')
        rotulos, erro = rt.carregar_rotulos(caminho)
        assert rotulos == {} and erro, conteudo


def test_conjunto_rotulado_usa_todas_as_faturas_e_traz_o_baseline_das_regras(tmp_path):
    pasta = str(tmp_path / 'historico')
    outubro = 'date,title,amount\n2026-09-20,Fibra,"36,90"\n2026-09-21,Auto Posto X,"100,00"\n2026-09-22,Pagamento recebido,"- 50,00"\n'.encode('utf-8')
    novembro = 'date,title,amount\n2026-10-20,Fibra,"36,90"\n2026-10-21,Loja Nova,"10,00"\n2026-10-22,IOF de compra internacional,"1,00"\n'.encode('utf-8')
    hist.guardar(pasta, outubro, 'a.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    hist.guardar(pasta, novembro, 'b.csv', date(2026, 11, 25), date(2026, 11, 18), date(2026, 11, 20))
    rotulos = {'fibra': ft.CASA, 'auto posto x': ft.TRANSPORTE}
    regras = {'fibra': ft.CASA}
    montadas = hist.montar(hist.carregar_historico(pasta)[0], regras)
    conjunto = rt.conjunto_rotulado(montadas, rotulos)
    assert len(conjunto) == 3
    assert list(conjunto['rotulo']) == [ft.CASA, ft.TRANSPORTE, ft.CASA]
    # Baseline: o que as regras dariam sem as escolhas do usuário.
    assert list(conjunto['categoria_regras']) == [ft.A_CLASSIFICAR, ft.TRANSPORTE, ft.A_CLASSIFICAR]
    assert set(conjunto['vencimento']) == {date(2026, 10, 25), date(2026, 11, 25)}
    assert 'loja nova' not in set(conjunto['chave'])


# ---------------------------------------------------------------- fase 1: regressões

def test_linha_que_o_usuario_nao_mexeu_nao_desfaz_nada(fatura_real):
    # A tela mostrou Zarpa conferido como Compras; se a escolha volta igual, nada muda,
    # mesmo que o rótulo gravado no disco seja outro (gravado por outro caminho depois da tela).
    itens = rt.para_conferir(fatura_real, {'zarpa': ft.COMPRAS})
    rotulos, regras, conferidos, removidos = rt.aplicar_conferencia(
          {'zarpa': ft.LAZER}, {'zarpa': ft.LAZER}, itens, {'zarpa': (ft.COMPRAS, True), 'conectanet': (ft.A_CLASSIFICAR, False)}
    )
    assert rotulos == {'zarpa': ft.LAZER}
    assert regras == {'zarpa': ft.LAZER}
    assert (conferidos, removidos) == (0, 0)


def test_encargos_e_estornos_nao_sao_categoria_de_rotulo(tmp_path):
    assert ft.ENCARGOS not in rt.CATEGORIAS_ROTULO
    assert ft.ESTORNOS not in rt.CATEGORIAS_ROTULO
    caminho = tmp_path / 'rotulos.json'
    caminho.write_text('{"fibra": "Juros, multas e IOF"}', encoding='utf-8')
    assert rt.carregar_rotulos(str(caminho))[0] == {}


def test_origens_novo_trocado_igual_e_removido():
    antes = {'a': ft.COMIDA, 'b': ft.LAZER, 'c': ft.CASA}
    depois = {'a': ft.COMIDA, 'b': ft.COMPRAS, 'd': ft.SAUDE}
    origens = {'a': {'origem': rt.ORIGEM_CORRIGIR, 'data': '2026-11-01'}, 'c': {'origem': rt.ORIGEM_CORRIGIR, 'data': '2026-11-01'}}
    novas = rt.atualizar_origens(origens, antes, depois, {'b': rt.ORIGEM_TROCOU, 'd': rt.ORIGEM_CONFIRMOU}, date(2026, 11, 5))
    assert novas == {
          'a': {'origem': rt.ORIGEM_CORRIGIR, 'data': '2026-11-01'}
        , 'b': {'origem': rt.ORIGEM_TROCOU, 'data': '2026-11-05'}
        , 'd': {'origem': rt.ORIGEM_CONFIRMOU, 'data': '2026-11-05'}
    }
    assert rt.caminho_origens('x/rotulos.json') == 'x/rotulos_origem.json'


def test_conjunto_rotulado_traz_origem_e_base(tmp_path):
    pasta = str(tmp_path / 'historico')
    hist.guardar(pasta, 'date,title,amount\n2026-09-20,Fibra,"36,90"\n'.encode('utf-8'), 'a.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    montadas = hist.montar(hist.carregar_historico(pasta)[0], {})
    conjunto = rt.conjunto_rotulado(montadas, {'fibra': ft.CASA}, {'fibra': {'origem': rt.ORIGEM_TROCOU, 'data': '2026-11-05'}}, 'simuladas')
    linha = conjunto.iloc[0]
    assert (linha['origem'], linha['data_rotulo'], linha['base']) == (rt.ORIGEM_TROCOU, '2026-11-05', 'simuladas')
    sem_origem = rt.conjunto_rotulado(montadas, {'fibra': ft.CASA})
    assert sem_origem.iloc[0]['origem'] == rt.ORIGEM_DESCONHECIDA
