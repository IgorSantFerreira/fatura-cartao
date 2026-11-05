from datetime import date
from pathlib import Path

import pytest

import fatura as ft


# Fatura de exemplo 100% fictícia (tests/exemplo.py): nenhum dado real nos testes.
from exemplo import CONTEUDO_EXEMPLO


def montar_exemplo(regras_usuario=None):
    return ft.montar_fatura(ft.ler_csv(CONTEUDO_EXEMPLO), regras_usuario)


def total_categoria(fatura, categoria):
    resumo = ft.resumo_categorias(fatura)
    return int(resumo.loc[resumo['categoria'] == categoria, 'centavos'].iloc[0])


def test_totais_e_conciliacao_da_fatura_de_exemplo():
    valores = ft.totais(montar_exemplo())
    assert valores == {'gasto': 250814, 'saldo_anterior': 141270, 'pagamentos': -141270, 'total_csv': 250814}
    assert valores['gasto'] + valores['saldo_anterior'] + valores['pagamentos'] == valores['total_csv']


def test_totais_por_categoria_batem_com_a_conta_manual():
    fatura = montar_exemplo()
    esperado = {
          ft.COMIDA: 51160
        , ft.TRANSPORTE: 74350
        , ft.ASSINATURAS: 27580
        , ft.JOGOS: 27120
        , ft.COMPRAS: 15810
        , ft.VIAGEM: 8400
        , ft.SAUDE: 2940
        , ft.ENCARGOS: 5564
        , ft.A_CLASSIFICAR: 37890
    }
    resumo = ft.resumo_categorias(fatura)
    obtido = {}
    for linha in resumo.itertuples(index=False):
        obtido[linha.categoria] = linha.centavos
    assert obtido == esperado
    assert sum(esperado.values()) == 250814


def test_subcategorias_de_comida_e_transporte():
    fatura = montar_exemplo()
    comida = ft.resumo_subcategorias(fatura, ft.COMIDA)
    assert dict(zip(comida['subcategoria'], comida['centavos'])) == {'Delivery': 37010, 'Restaurantes e lanches': 10550, 'Mercado e padaria': 3600}
    transporte = ft.resumo_subcategorias(fatura, ft.TRANSPORTE)
    assert dict(zip(transporte['subcategoria'], transporte['centavos'])) == {
          'Combustível': 54470
        , 'Estacionamento': 14050
        , 'Apps de corrida': 4750
        , 'Transporte público': 1080
    }


def test_compras_e_media_ignoram_estorno():
    fatura = montar_exemplo()
    comida = ft.resumo_subcategorias(fatura, ft.COMIDA)
    delivery = comida[comida['subcategoria'] == 'Delivery'].iloc[0]
    assert delivery['compras'] == 7
    assert delivery['media_centavos'] == 5924  # 414,70 / 7 = 59,242...


def test_parcelas_futuras():
    futuras = ft.parcelas_futuras(montar_exemplo())
    assert int(futuras['centavos_futuros'].sum()) == 48020
    assert sorted(futuras['estabelecimento']) == ['Airbnb * Hmzk31qa77', 'Amazon', 'Decathlon', 'Zarpa']


def test_ciclo_do_nubank_fecha_7_dias_antes():
    datas = ft.ciclo(date(2026, 11, 25))
    assert datas['fechamento'] == date(2026, 11, 18)
    assert datas['inicio'] == date(2026, 10, 18)
    assert datas['ultimo_dia'] == date(2026, 11, 17)
    datas = ft.ciclo(date(2026, 3, 7))
    assert datas['fechamento'] == date(2026, 2, 28)
    # Início = fechamento anterior = 07/02 - 7 dias.
    assert datas['inicio'] == date(2026, 1, 31)
    datas = ft.ciclo(date(2026, 4, 7), date(2026, 3, 31))
    assert datas['inicio'] == date(2026, 2, 28)


def test_projecao_da_fatura_de_exemplo_em_4_de_novembro():
    datas = ft.ciclo(date(2026, 11, 25))
    resultado = ft.projecao(montar_exemplo(), datas['inicio'], datas['ultimo_dia'], date(2026, 11, 4))
    assert resultado['dias_total'] == 31
    assert resultado['dias_decorridos'] == 18
    assert resultado['dias_restantes'] == 13
    # Dia a dia de 18/10 a 04/11, sem parcelas, assinaturas, encargos e estornos: 1.629,50 (/18 = 90,53; x13/18 = 1.176,86).
    assert resultado['ritmo_diario'] == 9053
    assert resultado['a_mais'] == 117686
    assert resultado['projetado'] == 368500
    por_categoria = resultado['por_categoria']
    comida = por_categoria[por_categoria['categoria'] == ft.COMIDA].iloc[0]
    assert (comida['centavos_atual'], comida['centavos_a_mais']) == (51160, 40170)
    transporte = por_categoria[por_categoria['categoria'] == ft.TRANSPORTE].iloc[0]
    assert (transporte['centavos_atual'], transporte['centavos_a_mais']) == (74350, 53697)
    compras = por_categoria[por_categoria['categoria'] == ft.COMPRAS].iloc[0]
    assert compras['centavos_a_mais'] == 0


def test_projecao_com_ciclo_encerrado_nao_soma_nada():
    datas = ft.ciclo(date(2026, 11, 25))
    resultado = ft.projecao(montar_exemplo(), datas['inicio'], datas['ultimo_dia'], date(2026, 12, 20))
    assert resultado['dias_restantes'] == 0
    assert resultado['projetado'] == resultado['atual'] == 250814


def test_projecao_antes_do_inicio_do_ciclo():
    datas = ft.ciclo(date(2026, 11, 25))
    assert ft.projecao(montar_exemplo(), datas['inicio'], datas['ultimo_dia'], date(2026, 10, 1)) is None


def test_destaques_da_fatura_de_exemplo():
    frases = ft.destaques(montar_exemplo())
    texto = '\n'.join(frases)
    # Os destaques vão para st.markdown, então o "$" sai escapado ("R\$") para não virar fórmula.
    assert r'**Transporte** é onde mais vai dinheiro: R\$ 743,50 (30% do gasto do período).' in frases
    assert r'**7 pedidos de delivery** somam R\$ 414,70' in texto
    assert r'R\$ 48,67 de multa, juros e IOF por atraso' in texto
    assert r'R\$ 6,97 de IOF em compras internacionais.' in frases
    assert r'Assinaturas somam R\$ 275,80 em 6 cobranças.' in frases
    assert r'**R\$ 480,20 já estão comprometidos**' in texto
    assert r'R\$ 378,90 em 8 lançamentos ainda estão' in texto
    assert 'combustível' in texto


def test_top_estabelecimentos_agrupa_mesmo_lugar():
    top = ft.top_estabelecimentos(montar_exemplo(), 50)
    pizza = top[top['estabelecimento'] == 'Ifd*J. R. Lima Pizza'].iloc[0]
    assert (pizza['centavos'], pizza['compras']) == (15870, 3)
    metro = top[top['estabelecimento'] == 'Emv Metrô'].iloc[0]
    assert (metro['centavos'], metro['compras']) == (1080, 2)
    assert top['estabelecimento'].iloc[0] == 'Auto Posto Girassol'


def test_pagamento_e_saldo_anterior_nao_aparecem_no_resumo():
    resumo = ft.resumo_categorias(montar_exemplo())
    assert ft.PAGAMENTO not in list(resumo['categoria'])
    assert ft.SALDO_ANTERIOR not in list(resumo['categoria'])


# ---------------------------------------------------------------- casos-limite

def test_estorno_dentro_do_ciclo_fica_fora_do_ritmo():
    texto = 'date,title,amount\n2026-10-20,Ifd*Loja Teste,"100,00"\n2026-10-21,Estorno de compra (iFood),"- 100,00"\n2026-10-22,Restaurante Teste,"50,00"\n'
    fatura = ft.montar_fatura(ft.ler_csv(texto.encode('utf-8')))
    datas = ft.ciclo(date(2026, 11, 25))
    resultado = ft.projecao(fatura, datas['inicio'], datas['ultimo_dia'], date(2026, 10, 27))
    assert resultado['dias_decorridos'] == 10
    assert resultado['ritmo_diario'] == 1500  # A7: estornos fora do ritmo


@pytest.mark.parametrize('vencimento', [date(2026,3,5), date(2026,3,7), date(2026,3,1), date(2026,5,3), date(2026,11,25), date(2027,1,25)])
def test_inicio_do_ciclo_e_o_fechamento_anterior(vencimento):
    anterior = ft.subtrair_um_mes(vencimento)
    assert ft.ciclo(vencimento)['inicio'] == ft.ciclo(anterior)['fechamento']


def test_considerar_compras_ate_nao_conta_duas_vezes():
    fatura = montar_exemplo()
    datas = ft.ciclo(date(2026, 11, 25))
    corte = date(2026, 10, 25)
    try:
        resultado = ft.projecao(fatura, datas['inicio'], datas['ultimo_dia'], corte)
    except ValueError:
        return  # recusar a data com mensagem também é aceitável
    ate_corte = fatura['conta_no_gasto'] & (fatura['data'].dt.date <= corte)
    esperado = int(fatura.loc[ate_corte, 'centavos'].sum())
    assert resultado['atual'] == esperado
    assert resultado['projetado'] == esperado + resultado['a_mais']


def test_projecao_por_categoria_soma_o_total():
    texto = 'date,title,amount\n2026-10-18,Restaurante A,"0,09"\n2026-10-18,Auto Posto B,"0,09"\n'
    fatura = ft.montar_fatura(ft.ler_csv(texto.encode('utf-8')))
    datas = ft.ciclo(date(2026, 11, 25))
    r = ft.projecao(fatura, datas['inicio'], datas['ultimo_dia'], date(2026, 11, 4))
    assert int(r['por_categoria']['centavos_a_mais'].sum()) == r['a_mais']
    assert int(r['por_categoria']['centavos_projetado'].sum()) == r['projetado']


# ---------------------------------------------------------------- casos-limite

def test_regra_pagamento_do_usuario_nao_tira_compra_do_gasto():
    regras = ft.aplicar_escolha({}, 'Loja Xyz', -5000, ft.PAGAMENTO)
    texto = 'date,title,amount\n2026-10-20,Loja Xyz,"- 50,00"\n2026-10-25,Loja Xyz,"80,00"\n'
    fatura = ft.montar_fatura(ft.ler_csv(texto.encode('utf-8')), regras)
    compra = fatura[fatura['centavos'] > 0].iloc[0]
    assert bool(compra['conta_no_gasto'])
    assert ft.totais(fatura)['gasto'] == 8000
