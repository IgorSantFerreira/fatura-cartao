from datetime import date

import numpy as np
import pandas as pd
import pytest

import fatura as ft
import modelo as ml


def montar(texto, vencimento=date(2026, 11, 25)):
    fatura = ft.montar_fatura(ft.ler_csv(('date,title,amount\n' + texto).encode('utf-8')), {})
    return {'vencimento': vencimento, 'rotulo': '', 'completa': True, 'fatura': fatura}


def conjunto_de(linhas):
    # linhas: (descricao, valor em reais, data, rotulo)
    tabela = pd.DataFrame(linhas, columns=['descricao', 'reais', 'data', 'rotulo'])
    return pd.DataFrame({
          'vencimento': [date(2026, 11, 25)] * len(tabela)
        , 'data': pd.to_datetime(tabela['data']).dt.date
        , 'descricao': tabela['descricao']
        , 'centavos': (tabela['reais'] * 100).round().astype(int)
        , 'estabelecimento': [ft.nome_estabelecimento(descricao) for descricao in tabela['descricao']]
        , 'chave': [ft.chave_estabelecimento(descricao) for descricao in tabela['descricao']]
        , 'parcela_atual': [None] * len(tabela)
        , 'parcela_total': [None] * len(tabela)
        , 'rotulo': tabela['rotulo']
    })


def test_historico_frequencia_e_valor_repetido():
    historico = ml.historico_estabelecimentos([
          montar('2026-10-20,Netflix.Com,"44,90"\n2026-10-21,Padaria X,"10,00"\n2026-10-22,Padaria X,"12,00"\n')
        , montar('2026-11-20,Netflix.Com,"44,90"\n2026-11-21,Loja Y,"50,00"\n')
    ])
    assert historico['netflix.com'] == {'frequencia': 1.0, 'valor_repetido': 1.0}
    assert historico['padaria x'] == {'frequencia': 0.5, 'valor_repetido': 0.5}
    # Um lançamento só: sem repetição a medir.
    assert historico['loja y'] == {'frequencia': 0.5, 'valor_repetido': 0.0}


def test_preparar_sem_vencimento_nao_quebra():
    linhas = pd.DataFrame({
          'descricao': ['Padaria X - Parcela 1/3']
        , 'centavos': [1000]
        , 'data': [date(2026, 10, 20)]
        , 'vencimento': [None]
        , 'parcela_total': [3]
    })
    atributos = ml.preparar(linhas, {})
    assert atributos['texto'].iloc[0] == 'padaria x'
    assert atributos['posicao_ciclo'].iloc[0] == 0.0
    assert atributos['parcelado'].iloc[0] == 1
    assert atributos['frequencia'].iloc[0] == 0.0
    assert atributos['log_valor'].iloc[0] == pytest.approx(np.log1p(10.0))


def test_treinar_precisa_de_duas_categorias():
    conjunto = conjunto_de([('Padaria X', 10.0, '2026-10-20', ft.COMIDA), ('Padaria Z', 12.0, '2026-10-21', ft.COMIDA)])
    assert ml.treinar(conjunto, {}) is None
    assert ml.treinar(conjunto.iloc[0:0], {}) is None


def test_sugere_pelo_nome_parecido_e_explica():
    conjunto = conjunto_de([
          ('Padaria Sol', 12.0, '2026-10-20', ft.COMIDA)
        , ('Padaria Lua', 9.0, '2026-10-21', ft.COMIDA)
        , ('Padaria Estrela', 15.0, '2026-10-22', ft.COMIDA)
        , ('Auto Posto Norte', 150.0, '2026-10-23', ft.TRANSPORTE)
        , ('Auto Posto Sul', 180.0, '2026-10-24', ft.TRANSPORTE)
        , ('Auto Posto Leste', 160.0, '2026-10-25', ft.TRANSPORTE)
    ])
    treinado = ml.treinar(conjunto, {})
    novas = pd.DataFrame({
          'descricao': ['Padaria Mar', 'Auto Posto Oeste']
        , 'centavos': [1100, 17000]
        , 'data': [date(2026, 11, 1), date(2026, 11, 2)]
        , 'vencimento': [date(2026, 11, 25), date(2026, 11, 25)]
        , 'parcela_total': [None, None]
        , 'chave': ['padaria mar', 'auto posto oeste']
    })
    sugestoes = ml.sugerir(treinado, novas).set_index('chave')
    assert sugestoes.loc['padaria mar', 'categoria'] == ft.COMIDA
    assert sugestoes.loc['auto posto oeste', 'categoria'] == ft.TRANSPORTE
    for chave in sugestoes.index:
        assert 0.5 < sugestoes.loc[chave, 'confianca'] <= 1.0
    parecidos = sugestoes.loc['padaria mar', 'parecidos']
    assert 1 <= len(parecidos) <= 3
    assert all(categoria == ft.COMIDA for nome, categoria in parecidos[:1])
    assert parecidos[0][0].startswith('Padaria')


def test_uma_sugestao_por_estabelecimento():
    conjunto = conjunto_de([
          ('Padaria Sol', 12.0, '2026-10-20', ft.COMIDA)
        , ('Auto Posto Norte', 150.0, '2026-10-23', ft.TRANSPORTE)
    ])
    treinado = ml.treinar(conjunto, {})
    novas = pd.DataFrame({
          'descricao': ['Loja Q', 'Loja Q', 'Loja Q']
        , 'centavos': [1000, 2000, 3000]
        , 'data': [date(2026, 11, 1)] * 3
        , 'vencimento': [date(2026, 11, 25)] * 3
        , 'parcela_total': [None] * 3
        , 'chave': ['loja q'] * 3
    })
    sugestoes = ml.sugerir(treinado, novas)
    assert len(sugestoes) == 1


def test_pontuacoes_com_duas_categorias_e_categoria_desconhecida():
    conjunto = conjunto_de([
          ('Padaria Sol', 12.0, '2026-10-20', ft.COMIDA)
        , ('Auto Posto Norte', 150.0, '2026-10-23', ft.TRANSPORTE)
    ])
    atributos = ml.preparar(ml.linhas_do_conjunto(conjunto), {})
    pipeline = ml.montar_pipeline(ml.LOGISTICA, usar_tempo=False)
    pipeline.fit(atributos, conjunto['rotulo'])
    classes = [ft.COMIDA, ft.LAZER, ft.TRANSPORTE]
    logits = ml.pontuacoes(pipeline, atributos, classes)
    assert logits.shape == (2, 3)
    # Lazer não existia no treino: pontuação mínima, probabilidade ~0.
    assert (logits[:, 1] < -1e5).all()
    # Com temperatura 1, o softmax das pontuações é a probabilidade do próprio modelo.
    from scipy.special import softmax
    probabilidades = softmax(logits, axis=1)
    assert np.allclose(probabilidades[:, [0, 2]], pipeline.predict_proba(atributos))
    temperatura = ml.ajustar_temperatura(logits, list(conjunto['rotulo']), classes)
    assert 0.05 <= temperatura <= 20.0


# ---------------------------------------------------------------- casos-limite

import importlib.util
from pathlib import Path
from sklearn.model_selection import GroupKFold
import rotulos as rt

def dados_sinteticos(pasta):
    caminho = Path(__file__).parent.parent / 'ferramentas' / 'gerar_faturas_sinteticas.py'
    especificacao = importlib.util.spec_from_file_location('gerador', caminho)
    gerador = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(gerador)
    gerador.gravar(gerador.gerar(13, 2026, date(2025, 10, 25)), pasta)
    gabarito = pd.read_csv(pasta / 'gabarito.csv', dtype=str)
    partes = []
    for arquivo in sorted((pasta / 'faturas').glob('*.csv')):
        df_csv = ft.ler_csv(arquivo.read_bytes())
        do_arquivo = gabarito[gabarito['fatura'] == arquivo.name].reset_index(drop=True)
        assert list(df_csv['descricao']) == list(do_arquivo['title'].str.strip())
        df_csv['categoria_certa'] = do_arquivo['categoria_certa'].to_numpy()
        df_fatura = ft.montar_fatura(df_csv.drop(columns='categoria_certa'), {})
        df_fatura = df_fatura.merge(df_csv[['linha', 'categoria_certa']], on='linha', how='left', validate='one_to_one')
        df_fatura = df_fatura[rt.rotulavel(df_fatura)].copy()
        df_fatura['vencimento'] = ft.vencimento_do_nome(arquivo.name)
        df_fatura['fatura'] = arquivo.name
        partes.append(df_fatura)
    return pd.concat(partes, ignore_index=True)

def test_confianca_citada_no_app_vale_para_os_lancamentos_que_recebem_sugestao(tmp_path):
    dados = dados_sinteticos(tmp_path)
    historico = ml.historico_estabelecimentos([{'fatura': grupo} for _, grupo in dados.groupby('fatura')])
    y = dados['categoria_certa'].to_numpy()
    grupos = dados['chave'].to_numpy()
    confianca = np.zeros(len(dados))
    acerto = np.zeros(len(dados), dtype=bool)
    for treino, teste in GroupKFold(n_splits=5).split(dados, y, grupos):
        pipeline = ml.montar_pipeline(ml.TIPO_APP, usar_tempo=ml.TEMPO_APP, C=ml.C_APP)
        pipeline.fit(ml.preparar(dados.iloc[treino], historico), y[treino])
        probabilidades = pipeline.predict_proba(ml.preparar(dados.iloc[teste], historico))
        classes = pipeline.named_steps['modelo'].classes_
        confianca[teste] = probabilidades.max(axis=1)
        acerto[teste] = classes[probabilidades.argmax(axis=1)] == y[teste]
    sugeridos = (dados['categoria'] == ft.A_CLASSIFICAR).to_numpy()
    # Texto do app (ml.texto_da_confianca, montado com ml.CALIBRACAO_SUGESTOES): confiança e acerto por lançamento, e "otimista".
    citado = ml.CALIBRACAO_SUGESTOES['por_lancamento']
    media, taxa = confianca[sugeridos].mean(), acerto[sugeridos].mean()
    assert abs(media - citado['confianca']) <= 0.05 and abs(taxa - citado['acerto']) <= 0.05 and media > taxa, (media, taxa)


# ---------------------------------------------------------------- fase 2: regressões

def test_texto_da_confianca_cita_os_numeros_medidos_e_a_direcao():
    texto = ml.texto_da_confianca()
    por_estabelecimento = ml.CALIBRACAO_SUGESTOES['por_estabelecimento']
    por_lancamento = ml.CALIBRACAO_SUGESTOES['por_lancamento']
    for medida in [por_estabelecimento, por_lancamento]:
        assert f"{round(medida['confianca'] * 100)}%" in texto
        assert f"{round(medida['acerto'] * 100)}%" in texto
        assert str(medida['quantidade']) in texto
    assert por_estabelecimento['confianca'] > por_estabelecimento['acerto']
    assert 'otimista' in texto


def test_texto_da_confianca_muda_de_direcao_com_os_numeros(monkeypatch):
    monkeypatch.setattr(ml, 'CALIBRACAO_SUGESTOES', {
          'por_lancamento': {'confianca': 0.40, 'acerto': 0.70, 'quantidade': 10}
        , 'por_estabelecimento': {'confianca': 0.35, 'acerto': 0.60, 'quantidade': 4}
    })
    texto = ml.texto_da_confianca()
    assert 'pessimista' in texto and 'otimista' not in texto
    assert '35%' in texto and '60%' in texto and '40%' in texto and '70%' in texto
