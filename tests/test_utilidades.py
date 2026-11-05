from datetime import date, timedelta
from pathlib import Path

import pytest

import fatura as ft
import metas as mt


# Fatura de exemplo 100% fictícia (tests/exemplo.py): nenhum dado real nos testes.
from exemplo import CONTEUDO_EXEMPLO


@pytest.fixture
def fatura_real():
    return ft.montar_fatura(ft.ler_csv(CONTEUDO_EXEMPLO), {})


def montar(texto):
    return ft.montar_fatura(ft.ler_csv(('date,title,amount\n' + texto).encode('utf-8')), {})


# ---------------------------------------------------------------- datas

@pytest.mark.parametrize('dia, meses, esperado', [
      (date(2026, 11, 25), 1, date(2026, 12, 25))
    , (date(2026, 12, 25), 1, date(2027, 1, 25))
    , (date(2026, 1, 31), 1, date(2026, 2, 28))
    , (date(2028, 1, 31), 1, date(2028, 2, 29))
    , (date(2026, 3, 31), -1, date(2026, 2, 28))
    , (date(2026, 1, 15), -1, date(2025, 12, 15))
    , (date(2026, 11, 25), 14, date(2028, 1, 25))
])
def test_somar_meses(dia, meses, esperado):
    assert ft.somar_meses(dia, meses) == esperado


def test_melhor_dia_de_compra_antes_do_fechamento():
    melhor = ft.melhor_dia_de_compra(date(2026, 11, 25), date(2026, 11, 18), date(2026, 11, 4))
    assert melhor['dia'] == date(2026, 11, 18)
    assert melhor['vencimento'] == date(2026, 12, 25)
    assert melhor['prazo_dias'] == 37
    assert melhor['vespera'] == date(2026, 11, 17)
    assert melhor['vencimento_vespera'] == date(2026, 11, 25)
    assert melhor['prazo_vespera_dias'] == 8


def test_melhor_dia_de_compra_no_proprio_fechamento_e_depois():
    no_dia = ft.melhor_dia_de_compra(date(2026, 11, 25), date(2026, 11, 18), date(2026, 11, 18))
    assert no_dia['dia'] == date(2026, 11, 18)
    depois = ft.melhor_dia_de_compra(date(2026, 11, 25), date(2026, 11, 18), date(2026, 11, 19))
    assert depois['dia'] == date(2026, 12, 18)
    assert depois['vencimento'] == date(2027, 1, 25)
    assert depois['prazo_dias'] == 38
    assert depois['vencimento_vespera'] == date(2026, 12, 25)


# ---------------------------------------------------------------- parcelas por mês

def test_parcelas_por_mes_da_fatura_real(fatura_real):
    por_mes = ft.parcelas_por_mes(fatura_real, date(2026, 11, 25))
    assert list(por_mes['fatura']) == ['dez/2026', 'jan/2027']
    assert list(por_mes['centavos']) == [39200, 8820]
    assert list(por_mes['compras']) == [4, 1]
    assert int(por_mes['centavos'].sum()) == int(ft.parcelas_futuras(fatura_real)['centavos_futuros'].sum()) == 48020


def test_parcelas_por_mes_sem_vencimento_e_sem_parcelas():
    fatura = montar('2026-10-20,Loja - Parcela 1/3,"30,00"\n')
    por_mes = ft.parcelas_por_mes(fatura)
    assert list(por_mes['fatura']) == ['Daqui a 1 fatura(s)', 'Daqui a 2 fatura(s)']
    assert list(por_mes['centavos']) == [3000, 3000]
    vazia = ft.parcelas_por_mes(montar('2026-10-20,Restaurante X,"30,00"\n'), date(2026, 11, 25))
    assert len(vazia) == 0


# ---------------------------------------------------------------- gastinhos

def test_gastinhos_da_fatura_real(fatura_real):
    pequenos = ft.gastinhos(fatura_real)
    assert pequenos['total_compras'] == 34
    assert pequenos['corte'] == 3200
    assert pequenos['quantidade'] == 17
    assert pequenos['centavos'] == 32510
    assert round(pequenos['percentual_do_gasto'], 1) == 13.0
    primeiro = pequenos['lugares'].iloc[0]
    assert primeiro['estabelecimento'] == 'Uber Uber *Trip Help.U'
    assert primeiro['compras'] == 3
    assert primeiro['centavos'] == 4750


def test_gastinhos_ignora_parcelas_assinaturas_encargos_e_estornos():
    fatura = montar(
          '2026-10-20,Restaurante A,"10,00"\n'
        + '2026-10-21,Restaurante B,"50,00"\n'
        + '2026-10-21,Loja - Parcela 1/3,"1,00"\n'
        + '2026-10-22,Spotify,"2,00"\n'
        + '2026-10-22,IOF de compra internacional,"0,50"\n'
        + '2026-10-23,Estorno de compra (Restaurante B),"- 5,00"\n'
    )
    pequenos = ft.gastinhos(fatura)
    assert pequenos['total_compras'] == 2
    assert pequenos['corte'] == 1000
    assert pequenos['quantidade'] == 1
    assert pequenos['centavos'] == 1000


def test_gastinhos_com_uma_compra_so():
    assert ft.gastinhos(montar('2026-10-20,Restaurante A,"10,00"\n')) is None


# ---------------------------------------------------------------- metas

def test_situacao_da_meta_comida_e_transporte_na_fatura_real(fatura_real):
    resultado = ft.projecao(fatura_real, date(2026, 10, 18), date(2026, 11, 17), date(2026, 11, 4))
    tabela = resultado['por_categoria']
    metas = mt.definir_meta([], [ft.TRANSPORTE, ft.COMIDA], 140000)
    linha = mt.situacao(
          metas
        , dict(zip(tabela['categoria'], tabela['centavos_atual']))
        , dict(zip(tabela['categoria'], tabela['centavos_projetado']))
        , resultado['dias_restantes']
    )[0]
    assert linha['nome'] == 'Comida e bebida + Transporte'
    assert linha['atual'] == 51160 + 74350
    assert linha['restante'] == 140000 - 125510
    assert linha['dias_restantes'] == 13
    assert linha['por_dia'] == (140000 - 125510) // 13
    assert linha['projetado'] > 140000
    assert linha['estado'] == 'vai estourar'


def test_situacao_estourou_e_sem_projecao():
    metas = mt.definir_meta([], [ft.COMIDA], 10000)
    estourou = mt.situacao(metas, {ft.COMIDA: 12000}, {ft.COMIDA: 15000}, 5)[0]
    assert estourou['estado'] == 'estourou'
    assert estourou['por_dia'] is None
    sem_projecao = mt.situacao(metas, {ft.COMIDA: 4000})[0]
    assert sem_projecao['estado'] == 'dentro'
    assert sem_projecao['projetado'] is None
    assert sem_projecao['por_dia'] is None
    assert sem_projecao['restante'] == 6000


def test_definir_meta_troca_a_de_mesmas_categorias_e_remove():
    metas = mt.definir_meta([], [ft.COMIDA, ft.TRANSPORTE], 130000)
    metas = mt.definir_meta(metas, [ft.TRANSPORTE, ft.COMIDA, ft.COMIDA], 120000)
    metas = mt.definir_meta(metas, [ft.COMIDA], 50000)
    assert metas == [
          {'categorias': [ft.COMIDA, ft.TRANSPORTE], 'centavos': 120000}
        , {'categorias': [ft.COMIDA], 'centavos': 50000}
    ]
    assert mt.remover_meta(metas, [ft.TRANSPORTE, ft.COMIDA]) == [{'categorias': [ft.COMIDA], 'centavos': 50000}]
    with pytest.raises(ValueError):
        mt.definir_meta(metas, [], 1000)
    with pytest.raises(ValueError):
        mt.definir_meta(metas, [ft.COMIDA], 0)
    with pytest.raises(ValueError):
        mt.definir_meta(metas, [ft.PAGAMENTO], 1000)


def test_metas_salvar_e_carregar(tmp_path):
    caminho = str(tmp_path / 'metas.json')
    assert mt.carregar_metas(caminho) == ([], None)
    metas = mt.definir_meta([], [ft.COMIDA, ft.TRANSPORTE], 140000)
    mt.salvar_metas(caminho, metas)
    assert mt.carregar_metas(caminho) == (metas, None)


@pytest.mark.parametrize('conteudo', [
      '{quebrado'
    , '[]'
    , '{"metas": {}}'
    , '{"metas": [{"categorias": ["Comida e bebida"], "centavos": true}]}'
    , '{"metas": [{"categorias": ["Comida e bebida"], "centavos": -5}]}'
    , '{"metas": [{"categorias": ["Comida e bebida"], "centavos": 10.5}]}'
    , '{"metas": [{"categorias": ["Inventada"], "centavos": 100}]}'
    , '{"metas": [{"categorias": ["Pagamento da fatura"], "centavos": 100}]}'
    , '{"metas": [{"categorias": [], "centavos": 100}]}'
])
def test_metas_invalidas_nao_sao_usadas(tmp_path, conteudo):
    caminho = tmp_path / 'metas.json'
    caminho.write_text(conteudo, encoding='utf-8')
    metas, erro = mt.carregar_metas(str(caminho))
    assert metas == []
    assert erro


# ---------------------------------------------------------------- casos-limite

@pytest.mark.parametrize('dia_vencimento', [1, 5, 7, 10, 25, 28])
@pytest.mark.parametrize('deslocamento', ['antes', 'no_dia', 'depois', 'fev', 'mar', 'dez'])
def test_melhor_dia_bate_com_o_ciclo(dia_vencimento, deslocamento):
    vencimento = date(2027, 1, dia_vencimento)
    fechamento = vencimento - timedelta(days=7)
    hoje = {
          'antes': fechamento - timedelta(days=3), 'no_dia': fechamento, 'depois': fechamento + timedelta(days=1)
        , 'fev': date(2027, 2, 27), 'mar': date(2027, 3, 30), 'dez': date(2027, 12, 31)
    }[deslocamento]
    melhor = ft.melhor_dia_de_compra(vencimento, fechamento, hoje)
    assert ft.ciclo(melhor['vencimento'])['inicio'] == melhor['dia']
    assert ft.ciclo(melhor['vencimento_vespera'])['ultimo_dia'] == melhor['vespera']
    assert ft.ciclo(melhor['vencimento_vespera'])['inicio'] < hoje <= melhor['dia']
    assert melhor['prazo_dias'] == (melhor['vencimento'] - melhor['dia']).days


# ---------------------------------------------------------------- fase 1: tipo de comportamento

def test_comportamentos_da_fatura_real(fatura_real):
    import historico as hist
    fixos = hist.recorrentes([{'vencimento': None, 'rotulo': '', 'completa': False, 'fatura': fatura_real}])
    tipos = ft.comportamentos(fatura_real, set(zip(fixos['chave'], fixos['centavos'])))
    resumo = ft.resumo_comportamentos(fatura_real, tipos)
    valores = dict(zip(resumo['comportamento'], resumo['centavos']))
    assert valores == {ft.RECORRENTE: 27580, ft.PARCELADO: 59180, ft.OCASIONAL: 162950, ft.ENCARGO: 5564, ft.ESTORNO: -4460}
    # Somados, os tipos dão o gasto do período; pagamento e saldo anterior são movimento da fatura.
    assert sum(valores.values()) == ft.totais(fatura_real)['gasto'] == 250814
    assert int((tipos == ft.MOVIMENTO).sum()) == 2
    assert dict(zip(resumo['comportamento'], resumo['lancamentos'])) == {
          ft.RECORRENTE: 6, ft.PARCELADO: 5, ft.OCASIONAL: 34, ft.ENCARGO: 5, ft.ESTORNO: 1
    }


def test_comportamento_prioridade_e_recorrente_por_valor():
    fatura = montar(
          '2026-10-20,Fibra,"36,90"\n'
        + '2026-10-21,Fibra,"50,00"\n'
        + '2026-10-22,Spotify - Parcela 1/2,"21,90"\n'
        + '2026-10-23,Pagamento recebido,"- 10,00"\n'
    )
    tipos = ft.comportamentos(fatura, {('fibra', 3690), ('spotify', 2190)})
    assert list(tipos) == [ft.RECORRENTE, ft.OCASIONAL, ft.PARCELADO, ft.MOVIMENTO]
