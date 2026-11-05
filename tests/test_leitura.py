from datetime import date
from pathlib import Path

import pytest

import fatura as ft


# Fatura de exemplo 100% fictícia (tests/exemplo.py): nenhum dado real nos testes.
from exemplo import CONTEUDO_EXEMPLO


def test_le_a_fatura_de_exemplo_com_53_linhas_e_soma_exata():
    df = ft.ler_csv(CONTEUDO_EXEMPLO)
    assert len(df) == 53
    # Soma conferida à mão sobre tests/exemplo.py.
    assert int(df['centavos'].sum()) == 250814
    assert df['centavos'].dtype == 'int64'


def test_formato_brasileiro_com_milhar_e_sinal_separado():
    texto = 'date,title,amount\n2026-10-28,Pagamento recebido,"- 1.412,70"\n2026-10-26,Valor pendente do mês anterior,"1.412,70"\n2026-11-03,IOF,"3,12"\n'
    df = ft.ler_csv(texto.encode('utf-8'))
    assert list(df['centavos']) == [-141270, 141270, 312]


def test_formato_com_ponto_decimal():
    texto = 'date,title,amount\n2026-10-28,Pagamento recebido,-1412.70\n2026-10-26,Compra,1412.5\n2026-11-03,Outra,40\n'
    df = ft.ler_csv(texto.encode('utf-8'))
    assert list(df['centavos']) == [-141270, 141250, 4000]


def test_formato_antigo_com_coluna_categoria_e_bom():
    texto = '﻿date,category,title,amount\n2026-10-28,restaurante,Restaurante X,23.00\n'
    df = ft.ler_csv(texto.encode('utf-8'))
    assert list(df['descricao']) == ['Restaurante X']
    assert list(df['centavos']) == [2300]


def test_valor_ambiguo_gera_erro_em_vez_de_numero_errado():
    # Sem vírgula no arquivo, "1.385" teria três casas decimais: não dá para saber o que é.
    texto = 'date,title,amount\n2026-10-28,Compra,1.385\n'
    with pytest.raises(ValueError, match='linha 2'):
        ft.ler_csv(texto.encode('utf-8'))


def test_valor_no_formato_americano_gera_erro():
    texto = 'date,title,amount\n2026-10-28,Compra,"1,385.02"\n'
    with pytest.raises(ValueError, match='valor'):
        ft.ler_csv(texto.encode('utf-8'))


def test_data_invalida_gera_erro_com_a_linha():
    texto = 'date,title,amount\n2026-10-28,Compra,"10,00"\n28-10-2026,Outra,"5,00"\n'
    with pytest.raises(ValueError, match='linha 3'):
        ft.ler_csv(texto.encode('utf-8'))


def test_colunas_faltando_gera_erro_claro():
    texto = 'Data,Valor,Identificador,Descrição\n01/10/2026,-10.00,abc,Transferência\n'
    with pytest.raises(ValueError, match='date, title e amount'):
        ft.ler_csv(texto.encode('utf-8'))


def test_arquivo_vazio_ou_so_cabecalho():
    with pytest.raises(ValueError):
        ft.ler_csv(b'')
    with pytest.raises(ValueError, match='não tem lançamentos'):
        ft.ler_csv(b'date,title,amount\n')


def test_linhas_em_branco_sao_ignoradas_mas_campos_faltando_nao():
    df = ft.ler_csv(b'date,title,amount\n\n2026-10-28,Compra,"10,00"\n\n')
    assert len(df) == 1
    with pytest.raises(ValueError, match='linha 2'):
        ft.ler_csv(b'date,title,amount\n2026-10-28,Compra\n')


def test_vencimento_vem_do_nome_do_arquivo():
    assert ft.vencimento_do_nome('Nubank_2026-11-25.csv') == date(2026, 11, 25)
    assert ft.vencimento_do_nome('fatura.csv') is None
    assert ft.vencimento_do_nome('Nubank_2026-02-30.csv') is None


def test_formatacao_em_reais():
    assert ft.reais(141270) == 'R$ 1.412,70'
    assert ft.reais(-4835) == '-R$ 48,35'
    assert ft.reais(5) == 'R$ 0,05'
    assert ft.reais(123456789) == 'R$ 1.234.567,89'


# ---------------------------------------------------------------- casos-limite

def test_codificacao_invalida_da_mensagem_clara():
    with pytest.raises(ValueError) as erro:
        ft.ler_csv(b'date,title,amount\n2026-10-28,Caf\x81,"10,00"\n')
    assert 'charmap' not in str(erro.value) and 'codec' not in str(erro.value)
