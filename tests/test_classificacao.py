from pathlib import Path

import pytest

import fatura as ft


# Fatura de exemplo 100% fictícia (tests/exemplo.py): nenhum dado real nos testes.
from exemplo import CONTEUDO_EXEMPLO

# Classificação esperada de cada linha da fatura de exemplo (fictícia), conferida à mão.
ESPERADO = [
      ('IOF de compra internacional', ft.ENCARGOS, ft.SUB_IOF_INTERNACIONAL)
    , ('Pag*Nuuvem', ft.JOGOS, 'Jogos')
    , ('Dl*Deezer Premium', ft.ASSINATURAS, 'Apps e streaming')
    , ('Openai *Chatgpt Subscr', ft.ASSINATURAS, 'Apps e streaming')
    , ('Auto Posto Primavera', ft.TRANSPORTE, 'Combustível')
    , ('Vip Estacionamentos L', ft.TRANSPORTE, 'Estacionamento')
    , ('Centralparkingestac', ft.TRANSPORTE, 'Estacionamento')
    , ('Ifd*J. R. Lima Pizza', ft.COMIDA, 'Delivery')
    , ('Auto Posto Girassol', ft.TRANSPORTE, 'Combustível')
    , ('Restaurante Bom Prato', ft.COMIDA, 'Restaurantes e lanches')
    , ('Uber Uber *Trip Help.U', ft.TRANSPORTE, 'Apps de corrida')
    , ('Ifd*M. Antunes', ft.COMIDA, 'Delivery')
    , ('Ifood Club Assinatura', ft.ASSINATURAS, 'Apps e streaming')
    , ('Pagamento recebido', ft.PAGAMENTO, ft.PAGAMENTO)
    , ('Multa por fatura atrasada', ft.ENCARGOS, ft.SUB_ATRASO)
    , ('IOF por fatura atrasada', ft.ENCARGOS, ft.SUB_ATRASO)
    , ('Juros por fatura atrasada', ft.ENCARGOS, ft.SUB_ATRASO)
    , ('Emv Metrô*162238417', ft.TRANSPORTE, 'Transporte público')
    , ('Emv Metrô*162290033', ft.TRANSPORTE, 'Transporte público')
    , ('Ifd*31.554.208 Ana Lu', ft.COMIDA, 'Delivery')
    , ('Icloud *Storage', ft.ASSINATURAS, 'Apps e streaming')
    , ('Topazio Park Estacion', ft.TRANSPORTE, 'Estacionamento')
    , ('Posto Jacaranda', ft.TRANSPORTE, 'Combustível')
    , ('Burger do Bairro', ft.COMIDA, 'Restaurantes e lanches')
    , ('Airbnb * Hmzk31qa77 - Parcela 1/2', ft.VIAGEM, 'Viagem')
    , ('Valor pendente do mês anterior', ft.SALDO_ANTERIOR, ft.SALDO_ANTERIOR)
    , ('Ifd*Carla Mendes de S', ft.COMIDA, 'Delivery')
    , ('Tavola Rest', ft.COMIDA, 'Restaurantes e lanches')
    , ('Hortifruti Sol', ft.COMIDA, 'Mercado e padaria')
    , ('Vidafarma', ft.SAUDE, 'Saúde')
    , ('Cerealista do Bairro', ft.COMIDA, 'Mercado e padaria')
    , ('Academia Corpo Livre', ft.ASSINATURAS, 'Academia')
    , ('Amazon - Parcela 8/10', ft.COMPRAS, 'Compras')
    , ('Playstation Store - Parcela 3/3', ft.JOGOS, 'Jogos')
    , ('Decathlon - Parcela 5/6', ft.COMPRAS, 'Compras')
    , ('Estorno de compra (iFood)', ft.COMIDA, 'Delivery')
]

# O app não deve chutar: estes ficam para o usuário classificar.
SEM_REGRA = [
      'Lucasferreiramota'
    , 'Bom Prato'
    , 'Recanto Verde Parque'
    , 'Bandeirante'
    , 'Conectanet'
    , 'Arena Esportes Empreen'
    , 'Mp *Anapaulasilv'
    , 'Zarpa - Parcela 1/2'
]


def montar_exemplo(regras_usuario=None):
    return ft.montar_fatura(ft.ler_csv(CONTEUDO_EXEMPLO), regras_usuario)


def test_cada_linha_da_fatura_de_exemplo_tem_a_categoria_esperada():
    fatura = montar_exemplo()
    for descricao, categoria, subcategoria in ESPERADO:
        linhas = fatura[fatura['descricao'] == descricao]
        assert len(linhas) > 0, descricao
        for linha in linhas.itertuples(index=False):
            assert (linha.categoria, linha.subcategoria) == (categoria, subcategoria), descricao


def test_estabelecimentos_desconhecidos_ficam_a_classificar():
    fatura = montar_exemplo()
    a_classificar = sorted(fatura.loc[fatura['categoria'] == ft.A_CLASSIFICAR, 'descricao'])
    assert a_classificar == sorted(SEM_REGRA)


def test_todas_as_linhas_foram_conferidas():
    fatura = montar_exemplo()
    conferidas = set()
    for descricao, categoria, subcategoria in ESPERADO:
        conferidas.add(descricao)
    for descricao in SEM_REGRA:
        conferidas.add(descricao)
    assert set(fatura['descricao']) == conferidas


@pytest.mark.parametrize('descricao, centavos, categoria', [
      ('Uber *Eats Pedido', 3000, ft.COMIDA)
    , ('Restaurante Forrest', 3000, ft.COMIDA)
    , ('Mercado Pago *Joao', 3000, ft.A_CLASSIFICAR)
    , ('Supermercado Dia', 3000, ft.COMIDA)
    , ('Barbearia do Ze', 3000, ft.A_CLASSIFICAR)
    , ('Pagamento recebido', 3000, ft.A_CLASSIFICAR)
    , ('Credito Real Imoveis', 3000, ft.A_CLASSIFICAR)
    , ('Estorno de compra', -1000, ft.ESTORNOS)
    , ('Estorno de compra (Loja Desconhecida)', -1000, ft.ESTORNOS)
    , ('Estorno de compra (Uber)', -1000, ft.TRANSPORTE)
    , ('Crédito de IOF', -312, ft.ENCARGOS)  # volta para a cobrança original
])
def test_regras_em_casos_de_borda(descricao, centavos, categoria):
    assert ft.classificar(descricao, centavos)[0] == categoria


def test_escolha_do_usuario_vence_a_regra_e_vale_para_o_estabelecimento():
    regras = {ft.chave_estabelecimento('Zarpa - Parcela 1/2'): ft.COMPRAS, ft.chave_estabelecimento('Auto Posto Primavera'): ft.VIAGEM}
    fatura = montar_exemplo(regras)
    assert fatura.loc[fatura['descricao'] == 'Zarpa - Parcela 1/2', 'categoria'].iloc[0] == ft.COMPRAS
    assert fatura.loc[fatura['descricao'] == 'Auto Posto Primavera', 'categoria'].iloc[0] == ft.VIAGEM
    assert fatura.loc[fatura['descricao'] == 'Auto Posto Primavera', 'origem'].iloc[0] == 'você'


def test_chave_ignora_parcela_e_numero_do_metro():
    assert ft.chave_estabelecimento('Zarpa - Parcela 1/2') == ft.chave_estabelecimento('ZARPA - Parcela 2/2')
    assert ft.chave_estabelecimento('Emv Metrô*162238417') == ft.chave_estabelecimento('Emv Metrô*162290033')


def test_aplicar_escolha_igual_a_automatica_remove_a_excecao():
    regras = ft.aplicar_escolha({}, 'Auto Posto Primavera', 18760, ft.VIAGEM)
    assert regras == {'auto posto primavera': ft.VIAGEM}
    regras = ft.aplicar_escolha(regras, 'Auto Posto Primavera', 18760, ft.TRANSPORTE)
    assert regras == {}


def test_regras_do_usuario_salvam_e_carregam(tmp_path):
    caminho = str(tmp_path / 'regras.json')
    assert ft.carregar_regras_usuario(caminho) == ({}, None)
    ft.salvar_regras_usuario(caminho, {'bom prato': ft.COMIDA})
    assert ft.carregar_regras_usuario(caminho) == ({'bom prato': ft.COMIDA}, None)


def test_arquivo_de_regras_corrompido_nao_e_usado(tmp_path):
    caminho = tmp_path / 'regras.json'
    caminho.write_text('{"bom prato": ', encoding='utf-8')
    regras, erro = ft.carregar_regras_usuario(str(caminho))
    assert regras == {}
    assert erro is not None
    caminho.write_text('{"bom prato": "Comidinha"}', encoding='utf-8')
    regras, erro = ft.carregar_regras_usuario(str(caminho))
    assert regras == {}
    assert 'Comidinha' not in erro and 'bom prato' in erro


# ---------------------------------------------------------------- casos-limite

@pytest.mark.parametrize('descricao, centavos, proibida', [
      ('Universidade Estacio de Sa', 50000, ft.TRANSPORTE)
    , ('Posto Carrefour', 20000, ft.COMIDA)
    , ('Auto Posto Pao de Acucar', 20000, ft.COMIDA)
    , ('Drogaria Ipiranga', 3000, ft.TRANSPORTE)
    , ('Drogarias Unidas', 3000, ft.TRANSPORTE)
])
def test_regras_amplas_nao_classificam_errado(descricao, centavos, proibida):
    assert ft.classificar(descricao, centavos)[0] != proibida


def test_regra_do_usuario_sobrevive_a_salvar_e_carregar(tmp_path):
    caminho = str(tmp_path / 'regras.json')
    descricao = 'Pagseguro *Loja 12345 678901'
    ft.salvar_regras_usuario(caminho, ft.aplicar_escolha({}, descricao, 5000, ft.COMIDA))
    carregadas, erro = ft.carregar_regras_usuario(caminho)
    assert erro is None
    assert ft.classificar(descricao, 5000, carregadas)[0] == ft.COMIDA
    assert ft.classificar('Pagseguro *Loja', 5000, carregadas)[0] == ft.A_CLASSIFICAR


@pytest.mark.parametrize('descricao, centavos, regras, esperado', [
      ('Estorno de juros por fatura atrasada', -1480, {}, (ft.ENCARGOS, ft.SUB_ATRASO))
    , ('Estorno de IOF de compra internacional', -312, {}, (ft.ENCARGOS, ft.SUB_IOF_INTERNACIONAL))
    , ('Estorno de compra (Bom Prato)', -3990, {'bom prato': ft.COMIDA}, (ft.COMIDA, None))
])
def test_estorno_volta_para_a_categoria_original(descricao, centavos, regras, esperado):
    categoria, subcategoria, _ = ft.classificar(descricao, centavos, regras)
    assert categoria == esperado[0]
    if esperado[1] is not None:
        assert subcategoria == esperado[1]


def test_saldo_anterior_credor_fica_fora_do_gasto():
    assert ft.classificar('Saldo restante da fatura anterior', -5000)[0] == ft.SALDO_ANTERIOR


# ---------------------------------------------------------------- casos-limite

@pytest.mark.parametrize('descricao, centavos, proibida', [
      ('Supermercado Ipiranga', 15000, ft.TRANSPORTE)
    , ('Padaria Ipiranga', 2000, ft.TRANSPORTE)
    , ('Restaurante Ipiranga', 6000, ft.TRANSPORTE)
    , ('Lanchonete do Posto', 3000, ft.TRANSPORTE)
    , ('Posto Ipiranga Ltda', 20000, ft.COMIDA)
])
def test_reordenacao_das_regras_nao_cria_novo_chute(descricao, centavos, proibida):
    assert ft.classificar(descricao, centavos)[0] != proibida


def test_escolha_explicita_no_estorno_vence_regra_da_compra_original():
    regras = {'bom prato': ft.COMIDA}
    descricao = 'Estorno de compra (Bom Prato)'
    novas = ft.aplicar_escolha(regras, descricao, -3990, ft.ESTORNOS)
    assert ft.classificar(descricao, -3990, novas)[0] == ft.ESTORNOS
    assert ft.classificar('Bom Prato', 3990, novas)[0] == ft.COMIDA


@pytest.mark.parametrize('descricao, centavos, esperado', [
      ('Juros da fatura anterior', 1480, ft.ENCARGOS)
    , ('Multa da fatura anterior', 2770, ft.ENCARGOS)
    , ('Estorno de juros da fatura anterior', -1480, ft.ENCARGOS)
])
def test_encargo_e_estorno_que_citam_fatura_anterior_nao_viram_saldo(descricao, centavos, esperado):
    assert ft.classificar(descricao, centavos)[0] == esperado
