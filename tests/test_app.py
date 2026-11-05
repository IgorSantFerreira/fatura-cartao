import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import fatura as ft


PASTA = Path(__file__).parent
ARQUIVO_APP = str(PASTA.parent / 'src' / 'app.py')
# Fatura de exemplo 100% fictícia (tests/exemplo.py): nenhum dado real nos testes.
from exemplo import CONTEUDO_EXEMPLO


@pytest.fixture
def regras(tmp_path, monkeypatch):
    # O app nunca deve tocar no regras_usuario.json, nas metas nem no histórico reais durante os testes.
    caminho = tmp_path / 'regras_usuario.json'
    monkeypatch.setenv('FATURA_REGRAS', str(caminho))
    monkeypatch.setenv('FATURA_METAS', str(tmp_path / 'metas_usuario.json'))
    monkeypatch.setenv('FATURA_HISTORICO', str(tmp_path / 'historico'))
    monkeypatch.setenv('FATURA_ROTULOS', str(tmp_path / 'rotulos.json'))
    monkeypatch.setenv('FATURA_SIMULADAS', str(tmp_path / 'simuladas'))
    monkeypatch.setenv('FATURA_REJEITADAS', str(tmp_path / 'sugestoes_rejeitadas.json'))
    return caminho


def abrir_com_exemplo(nome='Nubank_2026-11-25.csv', conteudo=None):
    if conteudo is None:
        conteudo = CONTEUDO_EXEMPLO
    app = AppTest.from_file(ARQUIVO_APP, default_timeout=60)
    app.run()
    app.file_uploader[0].upload(nome, conteudo, 'text/csv')
    app.run()
    # Com CSV inválido o app para antes da barra lateral.
    if len(app.sidebar.date_input) > 0:
        app.sidebar.date_input(key='hoje').set_value(date(2026, 11, 4))
        app.run()
    return app


def metricas(app):
    valores = {}
    for metrica in app.metric:
        valores[metrica.label] = metrica.value
    return valores


def textos(app):
    partes = []
    for elemento in list(app.markdown) + list(app.caption) + list(app.warning) + list(app.info) + list(app.error) + list(app.success):
        partes.append(elemento.value)
    return '\n'.join(partes)


def test_sem_arquivo_mostra_instrucao(regras):
    app = AppTest.from_file(ARQUIVO_APP, default_timeout=60)
    app.run()
    assert not app.exception
    assert 'Exporte a fatura em CSV' in app.info[0].value


def test_mostra_os_numeros_do_csv_real(regras):
    app = abrir_com_exemplo()
    assert not app.exception
    valores = metricas(app)
    assert valores['Gasto no período'] == 'R$ 2.508,14'
    assert valores['Comida e bebida'] == 'R$ 511,60'
    assert valores['Transporte'] == 'R$ 743,50'
    assert valores['Multa e juros por atraso'] == 'R$ 48,67'
    assert valores['Dias de compra que faltam'] == '13 de 31'
    assert valores['Fatura estimada no fechamento'] == 'R$ 3.685,00'
    texto = textos(app)
    # Textos de markdown levam "R\$" escapado; as métricas acima não passam por markdown.
    assert r'gasto do período R\$ 2.508,14 + saldo da fatura anterior R\$ 1.412,70 + pagamentos (-R\$ 1.412,70)' in texto
    assert r'8 lançamentos (R\$ 378,90) ainda não têm categoria' in texto
    assert 'de **18/10/2026** a **17/11/2026**' in texto
    assert r'Total nas próximas faturas: R\$ 480,20' in texto


def test_fechamento_editavel_muda_o_ciclo(regras):
    app = abrir_com_exemplo()
    app.sidebar.date_input(key='fechamento_2026-11-25').set_value(date(2026, 11, 20))
    app.run()
    assert not app.exception
    assert 'de **20/10/2026** a **19/11/2026**' in textos(app)


def test_arquivo_sem_data_no_nome_pede_vencimento(regras):
    app = abrir_com_exemplo(nome='fatura.csv')
    assert not app.exception
    assert 'Informe o vencimento' in textos(app)
    assert metricas(app)['Gasto no período'] == 'R$ 2.508,14'


def test_csv_invalido_mostra_erro_e_nenhum_numero(regras):
    app = abrir_com_exemplo(conteudo=b'date,title,amount\n2026-10-28,Compra,1.385\n')
    assert not app.exception
    assert 'linha 2' in app.error[0].value
    assert len(app.metric) == 0


def test_classificar_salva_e_atualiza_os_totais(regras):
    app = abrir_com_exemplo()
    app.selectbox(key='classificar_bom prato').set_value('Comida e bebida')
    app.selectbox(key='classificar_zarpa').set_value('Compras')
    for botao in app.button:
        if botao.label == 'Salvar categorias':
            botao.click()
    app.run()
    assert not app.exception
    salvo = json.loads(regras.read_text(encoding='utf-8'))
    assert salvo == {'zarpa': 'Compras', 'bom prato': 'Comida e bebida'}
    valores = metricas(app)
    assert valores['Comida e bebida'] == 'R$ 551,50'
    assert r'6 lançamentos (R\$ 189,10) ainda não têm categoria' in textos(app)


def test_corrigir_e_voltar_para_automatica(regras):
    app = abrir_com_exemplo()
    app.selectbox(key='corrigir_estabelecimento').set_value('auto posto primavera')
    app.selectbox(key='corrigir_categoria').set_value('Viagem')
    for botao in app.button:
        if botao.label == 'Salvar correção':
            botao.click()
    app.run()
    assert json.loads(regras.read_text(encoding='utf-8')) == {'auto posto primavera': 'Viagem'}
    assert metricas(app)['Transporte'] == 'R$ 555,90'

    app.selectbox(key='corrigir_estabelecimento').set_value('auto posto primavera')
    app.selectbox(key='corrigir_categoria').set_value('Voltar para a categoria automática')
    for botao in app.button:
        if botao.label == 'Salvar correção':
            botao.click()
    app.run()
    assert json.loads(regras.read_text(encoding='utf-8')) == {}
    assert metricas(app)['Transporte'] == 'R$ 743,50'


def test_regras_corrompidas_bloqueiam_gravacao(regras):
    regras.write_text('{quebrado', encoding='utf-8')
    app = abrir_com_exemplo()
    assert not app.exception
    assert 'não grava nada' in textos(app)
    assert regras.read_text(encoding='utf-8') == '{quebrado'
    for botao in app.button:
        assert botao.label != 'Salvar correção'


# ---------------------------------------------------------------- casos-limite

def test_fatura_estimada_inclui_saldo_nao_pago(regras):
    conteudo = 'date,title,amount\n2026-10-20,Valor pendente do mês anterior,"1.000,00"\n2026-10-22,Pagamento recebido,"- 600,00"\n2026-10-23,Restaurante Teste,"100,00"\n'.encode('utf-8')
    app = abrir_com_exemplo(conteudo=conteudo)
    app.sidebar.date_input(key='hoje').set_value(date(2026, 11, 17))
    app.run()
    assert not app.exception
    valores = metricas(app)
    if 'Fatura estimada no fechamento' in valores:
        assert valores['Fatura estimada no fechamento'] == 'R$ 500,00'
    else:
        assert not any('fatura' in r.lower() and 'estimad' in r.lower() for r in valores)


def test_valores_em_reais_nao_viram_latex(regras):
    app = abrir_com_exemplo()
    elementos = list(app.markdown) + list(app.caption) + list(app.warning) + list(app.info) + list(app.success) + list(app.error)
    for elemento in elementos:
        assert re.search(r'(?<!\\)\$', elemento.value) is None, elemento.value


def test_classificar_nao_oferece_pagamento_nem_saldo(regras):
    app = abrir_com_exemplo()
    opcoes = list(app.selectbox(key='classificar_bom prato').options)
    assert ft.PAGAMENTO not in opcoes and ft.SALDO_ANTERIOR not in opcoes


# ---------------------------------------------------------------- casos-limite

@pytest.mark.parametrize('opcao, valor', [('server.address', '0.0.0.0'), ('browser.gatherUsageStats', True)])
def test_app_recusa_abrir_sem_config_de_privacidade(regras, opcao, valor):
    from streamlit import config
    original = config.get_option(opcao)
    config.set_option(opcao, valor)
    try:
        app = AppTest.from_file(ARQUIVO_APP, default_timeout=60)
        app.run()
        assert not app.exception
        assert len(app.file_uploader) == 0
        assert 'Por privacidade' in app.error[0].value
    finally:
        config.set_option(opcao, original)


def test_rotulos_com_valor_nao_viram_latex(regras):
    app = abrir_com_exemplo()
    rotulos = [caixa.label for caixa in app.selectbox] + [bloco.label for bloco in app.expander]
    assert any('R\\$' in rotulo for rotulo in rotulos)
    for rotulo in rotulos:
        assert re.search(r'(?<!\\)\$', rotulo) is None, rotulo


# ---------------------------------------------------------------- histórico, metas, fixos, parcelas, melhor dia, gastinhos

import historico as hist


OUTUBRO = (
      'date,title,amount\n'
    + '2026-09-20,Restaurante Bom Prato,"38,00"\n'
    + '2026-09-25,Dl*Deezer Premium,"22,90"\n'
    + '2026-09-26,Conectanet,"39,90"\n'
    + '2026-10-01,Auto Posto Primavera,"200,00"\n'
).encode('utf-8')

# Uma fatura "simulada" para os testes de bases: os mesmos estabelecimentos da de exemplo, com todas as datas
# um dia depois. Nenhum lançamento coincide, então não é a mesma fatura nem outra exportação dela (nenhuma contém
# a outra) e pode ser guardada na outra base.
def datas_um_dia_depois(conteudo):
    linhas = conteudo.decode('utf-8').splitlines()
    novas = [linhas[0]]
    for linha in linhas[1:]:
        data, resto = linha.split(',', 1)
        novas.append((date.fromisoformat(data) + timedelta(days=1)).isoformat() + ',' + resto)
    return ('\n'.join(novas) + '\n').encode('utf-8')


SIMULADA_DE_EXEMPLO = datas_um_dia_depois(CONTEUDO_EXEMPLO)


@pytest.fixture
def pasta_historico(regras, monkeypatch):
    # A data real em que a fatura é guardada decide se ela está completa: fixa em 04/11/2026.
    monkeypatch.setattr(hist, 'data_de_hoje', lambda: date(2026, 11, 4))
    return regras.parent / 'historico'


def clicar(app, rotulo):
    for botao in app.button:
        if botao.label == rotulo:
            botao.click()
            app.run()
            return
    raise AssertionError(f'botão {rotulo} não encontrado')


def guardar_outubro(pasta_historico):
    hist.guardar(str(pasta_historico), OUTUBRO, 'Nubank_2026-10-25.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))


def test_abrir_fatura_guarda_no_historico_uma_vez(pasta_historico):
    app = abrir_com_exemplo()
    assert not app.exception
    arquivos = list(pasta_historico.glob('*.json'))
    assert [arquivo.name for arquivo in arquivos] == ['2026-11-25.json']
    salvo = json.loads(arquivos[0].read_text(encoding='utf-8'))
    assert salvo['salvo_em'] == '2026-11-04'
    assert salvo['csv'] == CONTEUDO_EXEMPLO.decode('utf-8-sig')
    assert 'Fatura 25/11/2026 guardada no histórico.' in textos(app)
    app.run()
    assert 'Fatura 25/11/2026 guardada no histórico.' in textos(app)
    assert len(list(pasta_historico.glob('*.json'))) == 1


def test_sem_vencimento_nao_guarda(pasta_historico):
    app = abrir_com_exemplo(nome='fatura.csv')
    assert not app.exception
    assert not pasta_historico.exists() or list(pasta_historico.glob('*.json')) == []
    assert 'Sem a data de vencimento a fatura não é guardada no histórico.' in textos(app)


def test_comparacao_com_a_media_e_fixos(pasta_historico):
    guardar_outubro(pasta_historico)
    app = abrir_com_exemplo()
    assert not app.exception
    texto = textos(app)
    assert 'Média de 1 fatura(s) completa(s) anterior(es): out/2026' in texto
    assert 'Esta fatura: estimada no fechamento, no ritmo atual.' in texto
    assert 'por mês** em cobranças fixas' in texto
    tabelas = [tabela.value for tabela in app.dataframe]
    fixos = [tabela for tabela in tabelas if 'Como foi achada' in tabela.columns][0]
    conectanet = fixos[fixos['Cobrança'] == 'Conectanet'].iloc[0]
    assert conectanet['Por mês'] == 'R$ 39,90'
    assert conectanet['Por ano'] == 'R$ 478,80'
    assert conectanet['Como foi achada'] == 'repete todo mês'
    meses = [tabela for tabela in tabelas if 'out/2026' in tabela.columns][0]
    assert 'nov/2026 (parcial)' in meses.columns
    total = meses[meses['Categoria'] == 'Total'].iloc[0]
    assert total['out/2026'] == 'R$ 300,80'
    assert total['nov/2026 (parcial)'] == 'R$ 2.508,14'


def test_metricas_da_comparacao_batem_com_a_projecao(pasta_historico):
    guardar_outubro(pasta_historico)
    app = abrir_com_exemplo()
    resultado = ft.projecao(
          ft.montar_fatura(ft.ler_csv(CONTEUDO_EXEMPLO), {})
        , date(2026, 10, 18), date(2026, 11, 17), date(2026, 11, 4)
    )
    tabela = resultado['por_categoria']
    projetado = dict(zip(tabela['categoria'], tabela['centavos_projetado']))
    comida_transporte = int(projetado[ft.COMIDA] + projetado[ft.TRANSPORTE])
    valores = metricas(app)
    assert valores['Comida + transporte nesta fatura'] == ft.reais(comida_transporte)
    assert valores['Gasto do período nesta fatura'] == ft.reais(resultado['projetado'])
    deltas = {metrica.label: metrica.delta for metrica in app.metric}
    assert deltas['Comida + transporte nesta fatura'] == f'{ft.reais_md(comida_transporte - 23800)} vs. média de R\\$ 238,00'
    assert deltas['Gasto do período nesta fatura'] == f'{ft.reais_md(resultado["projetado"] - 30080)} vs. média de R\\$ 300,80'


def test_criar_meta_mostra_quanto_pode_gastar_por_dia(pasta_historico, regras):
    app = abrir_com_exemplo()
    app.multiselect(key='meta_categorias').set_value([ft.TRANSPORTE, ft.COMIDA])
    app.number_input(key='meta_valor').set_value(1400.0)
    clicar(app, 'Salvar meta')
    assert not app.exception
    salvo = json.loads((regras.parent / 'metas_usuario.json').read_text(encoding='utf-8'))
    assert salvo == {'metas': [{'categorias': [ft.COMIDA, ft.TRANSPORTE], 'centavos': 140000}]}
    texto = textos(app)
    assert r'**Comida e bebida \+ Transporte**: R\$ 1.255,10 de R\$ 1.400,00 até agora, mas no ritmo atual fecha em' in texto
    assert r'até R\$ 11,14 por dia nos 13 dia(s) de compra que faltam depois de 04/11/2026 (R\$ 144,90 no total)' in texto
    # O aviso também aparece no topo.
    assert any(aviso.value.startswith('Meta: ') for aviso in app.warning)


def test_mudar_e_remover_meta(pasta_historico, regras):
    app = abrir_com_exemplo()
    app.multiselect(key='meta_categorias').set_value([ft.COMIDA, ft.TRANSPORTE])
    app.number_input(key='meta_valor').set_value(1400.0)
    clicar(app, 'Salvar meta')
    app.multiselect(key='meta_categorias').set_value([ft.TRANSPORTE, ft.COMIDA])
    app.number_input(key='meta_valor').set_value(3000.0)
    clicar(app, 'Salvar meta')
    caminho = regras.parent / 'metas_usuario.json'
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'metas': [{'categorias': [ft.COMIDA, ft.TRANSPORTE], 'centavos': 300000}]}
    assert not any(aviso.value.startswith('Meta: ') for aviso in app.warning)
    clicar(app, 'Remover meta')
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'metas': []}


def test_meta_sem_categoria_nao_salva(pasta_historico, regras):
    app = abrir_com_exemplo()
    app.number_input(key='meta_valor').set_value(100.0)
    clicar(app, 'Salvar meta')
    assert not app.exception
    assert 'Escolha pelo menos uma categoria.' in textos(app)
    assert not (regras.parent / 'metas_usuario.json').exists()


def test_metas_corrompidas_bloqueiam_gravacao(pasta_historico, regras):
    caminho = regras.parent / 'metas_usuario.json'
    caminho.write_text('{quebrado', encoding='utf-8')
    app = abrir_com_exemplo()
    assert not app.exception
    assert 'As metas não estão sendo usadas' in textos(app)
    assert all(botao.label != 'Salvar meta' for botao in app.button)
    assert caminho.read_text(encoding='utf-8') == '{quebrado'


def test_remover_do_historico_nao_volta_sozinha(pasta_historico):
    app = abrir_com_exemplo()
    assert (pasta_historico / '2026-11-25.json').exists()
    app.selectbox(key='historico_remover').set_value('2026-11-25')
    clicar(app, 'Remover do histórico')
    assert not app.exception
    assert not (pasta_historico / '2026-11-25.json').exists()
    app.run()
    assert not (pasta_historico / '2026-11-25.json').exists()


def test_adicionar_faturas_antigas(pasta_historico):
    app = abrir_com_exemplo()
    app.file_uploader(key='importar_antigas_Minhas faturas').upload('Nubank_2026-10-25.csv', OUTUBRO, 'text/csv')
    app.run()
    clicar(app, 'Guardar no histórico')
    assert not app.exception
    entradas, erros = hist.carregar_historico(str(pasta_historico))
    assert [entrada['vencimento'] for entrada in entradas] == [date(2026, 10, 25), date(2026, 11, 25)]
    assert entradas[0]['fechamento'] == date(2026, 10, 18)
    assert entradas[0]['completa'] is True
    assert 'Média de 1 fatura(s) completa(s) anterior(es): out/2026' in textos(app)


def test_melhor_dia_parcelas_e_gastinhos_na_tela(pasta_historico):
    app = abrir_com_exemplo()
    texto = textos(app)
    assert '**Dia 18, o dia do fechamento.** Uma compra em **18/11/2026** já vai para a fatura que vence em 25/12/2026: **37 dias** até pagar.' in texto
    assert 'Na véspera (17/11/2026) ela entraria na fatura que vence em 25/11/2026, com 8 dias.' in texto
    assert r'**17 de 34 compras do dia a dia** foram de até R\$ 32,00. Juntas, somam **R\$ 325,10**, 13% do gasto do período.' in texto
    tabelas = [tabela.value for tabela in app.dataframe]
    por_mes = [tabela for tabela in tabelas if 'Já comprometido' in tabela.columns][0]
    assert list(por_mes['Fatura']) == ['dez/2026', 'jan/2027']
    assert list(por_mes['Já comprometido']) == ['R$ 392,00', 'R$ 88,20']


def test_textos_novos_nao_viram_latex(pasta_historico, regras):
    guardar_outubro(pasta_historico)
    (regras.parent / 'metas_usuario.json').write_text(json.dumps({'metas': [{'categorias': [ft.COMIDA, ft.TRANSPORTE], 'centavos': 140000}]}), encoding='utf-8')
    app = abrir_com_exemplo()
    assert not app.exception
    elementos = list(app.markdown) + list(app.caption) + list(app.warning) + list(app.info) + list(app.success) + list(app.error)
    assert any('Meta: ' in elemento.value for elemento in elementos)
    for elemento in elementos:
        assert re.search(r'(?<!\\)\$', elemento.value) is None, elemento.value
    # Rótulos e deltas das métricas também passam por markdown (o valor não).
    deltas = [metrica.delta for metrica in app.metric if metrica.delta]
    assert len(deltas) == 2
    for texto in deltas + [metrica.label for metrica in app.metric]:
        assert re.search(r'(?<!\\)\$', texto) is None, texto


# ---------------------------------------------------------------- casos-limite

def test_fixo_ainda_nao_cobrado_na_fatura_aberta_entra_no_total(pasta_historico):
    pasta = str(pasta_historico)
    hist.guardar(pasta, OUTUBRO, 'Nubank_2026-10-25.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    novembro = ('date,title,amount\n2026-10-26,Conectanet,"39,90"\n2026-10-27,Restaurante Z,"55,00"\n').encode('utf-8')
    hist.guardar(pasta, novembro, 'Nubank_2026-11-25.csv', date(2026, 11, 25), date(2026, 11, 18), date(2026, 11, 20))
    dezembro = ('date,title,amount\n2026-11-19,Restaurante Y,"30,00"\n').encode('utf-8')
    app = abrir_com_exemplo(nome='Nubank_2026-12-25.csv', conteudo=dezembro)
    assert not app.exception
    assert hist.carregar_historico(pasta)[0][-1]['completa'] is False  # dezembro aberta/parcial
    assert r'**R\$ 39,90 por mês** em cobranças fixas' in textos(app)


def test_vencimento_corrigido_e_errado_removido_guarda_no_certo(pasta_historico):
    app = abrir_com_exemplo()
    assert (pasta_historico / '2026-11-25.json').exists()
    app.sidebar.date_input(key='vencimento_Nubank_2026-11-25.csv').set_value(date(2026, 11, 26))
    app.run()
    assert any(aviso.value.startswith('Histórico: Não guardei') for aviso in app.warning)
    app.selectbox(key='historico_remover').set_value('2026-11-25')
    clicar(app, 'Remover do histórico')
    app.run()
    assert not app.exception
    assert (pasta_historico / '2026-11-26.json').exists()
    assert not (pasta_historico / '2026-11-25.json').exists()  # a removida não volta
    assert not any(aviso.value.startswith('Histórico: Não guardei') for aviso in app.warning)


def test_remover_a_fatura_atual_nao_diz_que_ela_esta_guardada(pasta_historico):
    app = abrir_com_exemplo()
    app.selectbox(key='historico_remover').set_value('2026-11-25')
    clicar(app, 'Remover do histórico')
    assert not app.exception
    assert 'Fatura 25/11/2026 guardada no histórico.' not in textos(app)


# ---------------------------------------------------------------- casos-limite

def test_remover_fatura_com_arquivo_aberto_mais_velho_nao_regrava(pasta_historico):
    pasta = str(pasta_historico)
    completa = CONTEUDO_EXEMPLO
    linhas = completa.decode('utf-8-sig').splitlines()
    velha = ('\n'.join(linhas[:-1]) + '\n').encode('utf-8')
    hist.guardar(pasta, completa, 'Nubank_2026-11-25.csv', date(2026, 11, 25), date(2026, 11, 18), date(2026, 11, 4))
    app = abrir_com_exemplo(conteudo=velha)
    assert not app.exception
    assert 'Mantive a guardada' in textos(app)
    app.selectbox(key='historico_remover').set_value('2026-11-25')
    clicar(app, 'Remover do histórico')
    app.run()
    assert not app.exception
    assert not (pasta_historico / '2026-11-25.json').exists()


def test_remover_a_guardada_em_conflito_guarda_o_arquivo_aberto(pasta_historico):
    # A mensagem de conflito manda remover a guardada se o arquivo aberto é o certo: aí ele é guardado.
    pasta = str(pasta_historico)
    nova = ('date,title,amount\n2026-10-20,Restaurante A,"10,00"\n2026-11-10,Restaurante B,"20,00"\n').encode('utf-8')
    hist.guardar(pasta, nova, 'Nubank_2026-11-25.csv', date(2026, 11, 25), date(2026, 11, 18), date(2026, 11, 20))
    velha_alterada = ('date,title,amount\n2026-10-20,Restaurante A,"12,00"\n').encode('utf-8')
    app = abrir_com_exemplo(conteudo=velha_alterada)
    assert any(aviso.value.startswith('Histórico: Não troquei') for aviso in app.warning)
    app.selectbox(key='historico_remover').set_value('2026-11-25')
    clicar(app, 'Remover do histórico')
    app.run()
    assert not app.exception
    entradas = hist.carregar_historico(pasta)[0]
    assert len(entradas) == 1
    assert list(entradas[0]['df']['centavos']) == [1200]


# ---------------------------------------------------------------- regressões

def test_historico_e_metas_por_padrao_fora_da_pasta_do_app(regras, monkeypatch, tmp_path):
    # Sem FATURA_HISTORICO/FATURA_METAS, vão para %LOCALAPPDATA%\fatura_cartao, não para a pasta do app (OneDrive).
    monkeypatch.delenv('FATURA_HISTORICO')
    monkeypatch.delenv('FATURA_METAS')
    local = tmp_path / 'local_app_data'
    monkeypatch.setenv('LOCALAPPDATA', str(local))
    monkeypatch.setattr(hist, 'data_de_hoje', lambda: date(2026, 11, 4))
    pasta_app = PASTA.parent
    antes = (pasta_app / 'historico').exists()
    app = abrir_com_exemplo()
    assert not app.exception
    assert (local / 'fatura_cartao' / 'historico' / '2026-11-25.json').exists()
    assert (pasta_app / 'historico').exists() == antes


def test_fechamento_depois_do_vencimento_explica_por_que_nao_guarda(pasta_historico):
    app = abrir_com_exemplo()
    app.sidebar.date_input(key='fechamento_2026-11-25').set_value(date(2026, 11, 26))
    app.run()
    assert not app.exception
    assert 'Com o fechamento igual ou depois do vencimento a fatura não é guardada no histórico.' in textos(app)


def test_meta_com_data_antes_do_ciclo_nao_pede_vencimento(pasta_historico, regras):
    (regras.parent / 'metas_usuario.json').write_text(json.dumps({'metas': [{'categorias': [ft.COMIDA], 'centavos': 100000}]}), encoding='utf-8')
    app = abrir_com_exemplo()
    app.sidebar.date_input(key='hoje').set_value(date(2026, 10, 1))
    app.run()
    assert not app.exception
    texto = textos(app)
    assert 'Informe o vencimento' not in texto
    assert 'anterior ao início do ciclo, então não dá para calcular quanto dá por dia' in texto


def test_upload_com_aspa_sem_fechar_mostra_erro(regras):
    app = abrir_com_exemplo(conteudo=('date,title,amount\n2026-10-20,"' + 'x' * 200000 + '\n').encode('utf-8'))
    assert not app.exception
    assert 'não é um CSV válido' in app.error[0].value


# ---------------------------------------------------------------- fase 1: bases, rotulagem, tipo de gasto, evolução, fora do padrão

def usar_base(app, nome):
    app.sidebar.radio(key='base').set_value(nome)
    app.run()


def grafico(app, chave_grafico):
    for elemento in app.get('plotly_chart'):
        if elemento.proto.id and chave_grafico in elemento.proto.id:
            return json.loads(elemento.proto.spec)['data'][0]
    raise AssertionError(f'gráfico {chave_grafico} não encontrado')


def test_bases_separadas_nao_misturam_historico_regras_nem_rotulos(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    app = abrir_com_exemplo()
    assert 'Base de dados: Minhas faturas.' in textos(app)
    assert (pasta_historico / '2026-11-25.json').exists()
    assert not simuladas.exists()

    usar_base(app, 'Faturas simuladas')
    # na outra base a fatura precisa ser aberta de novo.
    # Fase 2: a mesma fatura não pode ficar nas duas bases, então aqui vai uma outra
    # fatura (a de exemplo com um lançamento a mais).
    app.file_uploader[0].upload('Nubank_2026-11-25.csv', SIMULADA_DE_EXEMPLO, 'text/csv')
    app.run()
    app.sidebar.date_input(key='hoje').set_value(date(2026, 11, 4))
    app.run()
    assert not app.exception
    assert 'Base de dados: Faturas simuladas.' in textos(app)
    assert (simuladas / 'historico' / '2026-11-25.json').exists()
    # Classificar na base simulada grava só nela.
    app.selectbox(key='classificar_zarpa').set_value(ft.COMPRAS)
    clicar(app, 'Salvar categorias')
    assert json.loads((simuladas / 'regras_usuario.json').read_text(encoding='utf-8')) == {'zarpa': ft.COMPRAS}
    assert json.loads((simuladas / 'rotulos.json').read_text(encoding='utf-8')) == {'zarpa': ft.COMPRAS}
    assert not regras.exists()
    assert not (regras.parent / 'rotulos.json').exists()

    usar_base(app, 'Minhas faturas')
    assert not app.exception
    # Correção de B1: cada base tem seu campo de arquivo; ao voltar, a fatura é aberta de novo.
    assert len(app.metric) == 0
    app.file_uploader[0].upload('Nubank_2026-11-25.csv', CONTEUDO_EXEMPLO, 'text/csv')
    app.run()
    # Em "Minhas faturas" o Zarpa continua a classificar.
    assert r'8 lançamentos (R\$ 378,90) ainda não têm categoria' in textos(app)


def test_remover_numa_base_nao_mexe_na_outra(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    app = abrir_com_exemplo()
    usar_base(app, 'Faturas simuladas')
    # Correção de B1: na base simulada a fatura é aberta de novo (e só então guardada nela).
    # Fase 2: outra fatura, porque a mesma não pode ficar nas duas bases.
    app.file_uploader[0].upload('Nubank_2026-11-25.csv', SIMULADA_DE_EXEMPLO, 'text/csv')
    app.run()
    assert (simuladas / 'historico' / '2026-11-25.json').exists()
    app.selectbox(key='historico_remover').set_value('2026-11-25')
    clicar(app, 'Remover do histórico')
    app.run()
    assert not (simuladas / 'historico' / '2026-11-25.json').exists()
    assert (pasta_historico / '2026-11-25.json').exists()


def test_conferir_grava_rotulos_e_categoria(pasta_historico, regras):
    app = abrir_com_exemplo()
    assert '0 de 36 estabelecimentos desta fatura conferidos.' in textos(app)
    app.checkbox(key='conferir_ok_auto posto girassol').check()
    app.selectbox(key='conferir_categoria_conectanet').set_value(ft.CASA)
    app.checkbox(key='conferir_ok_conectanet').check()
    clicar(app, 'Salvar conferência')
    assert not app.exception
    assert json.loads((regras.parent / 'rotulos.json').read_text(encoding='utf-8')) == {'auto posto girassol': ft.TRANSPORTE, 'conectanet': ft.CASA}
    assert json.loads(regras.read_text(encoding='utf-8')) == {'conectanet': ft.CASA}
    texto = textos(app)
    assert '2 de 36 estabelecimentos desta fatura conferidos.' in texto
    assert 'Na base "Minhas faturas": 2 lançamento(s) rotulado(s), de 2 estabelecimento(s), em 1 fatura(s) do histórico.' in texto
    assert len(app.get('download_button')) == 1


def test_conferir_a_classificar_mostra_erro_e_nao_grava(pasta_historico, regras):
    app = abrir_com_exemplo()
    app.checkbox(key='conferir_ok_zarpa').check()
    clicar(app, 'Salvar conferência')
    assert not app.exception
    assert 'Escolha uma categoria para Zarpa' in textos(app)
    assert not (regras.parent / 'rotulos.json').exists()


def test_corrigir_e_voltar_mexem_no_rotulo(pasta_historico, regras):
    app = abrir_com_exemplo()
    app.selectbox(key='corrigir_estabelecimento').set_value('auto posto primavera')
    app.selectbox(key='corrigir_categoria').set_value('Viagem')
    clicar(app, 'Salvar correção')
    caminho = regras.parent / 'rotulos.json'
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'auto posto primavera': 'Viagem'}
    app.selectbox(key='corrigir_estabelecimento').set_value('auto posto primavera')
    app.selectbox(key='corrigir_categoria').set_value('Voltar para a categoria automática')
    clicar(app, 'Salvar correção')
    assert json.loads(caminho.read_text(encoding='utf-8')) == {}


def test_rotulos_corrompidos_nao_sao_sobrescritos(pasta_historico, regras):
    caminho = regras.parent / 'rotulos.json'
    caminho.write_text('{quebrado', encoding='utf-8')
    app = abrir_com_exemplo()
    assert not app.exception
    assert 'Os rótulos não estão sendo usados' in textos(app)
    assert all(botao.label != 'Salvar conferência' for botao in app.button)
    app.selectbox(key='classificar_zarpa').set_value(ft.COMPRAS)
    clicar(app, 'Salvar categorias')
    assert caminho.read_text(encoding='utf-8') == '{quebrado'


def test_tipo_de_gasto_na_tela(pasta_historico):
    app = abrir_com_exemplo()
    tabelas = [tabela.value for tabela in app.dataframe]
    tipos = [tabela for tabela in tabelas if 'Tipo' in tabela.columns and '% do gasto' in tabela.columns][0]
    assert dict(zip(tipos['Tipo'], tipos['Total'])) == {
          'Recorrente': 'R$ 275,80', 'Parcelado': 'R$ 591,80', 'Ocasional': 'R$ 1.629,50', 'Encargo': 'R$ 55,64', 'Estorno': '-R$ 44,60'
    }
    lancamentos = [tabela for tabela in tabelas if 'Quem classificou' in tabela.columns][0]
    assert 'Tipo' in lancamentos.columns
    app.multiselect(key='filtro_tipos').set_value(['Parcelado'])
    app.run()
    lancamentos = [tabela.value for tabela in app.dataframe if 'Quem classificou' in tabela.value.columns][0]
    assert len(lancamentos) == 5
    assert set(lancamentos['Tipo']) == {'Parcelado'}


def test_evolucao_por_categoria(pasta_historico):
    guardar_outubro(pasta_historico)
    app = abrir_com_exemplo()
    total = grafico(app, 'grafico_meses')
    assert total['x'] == ['out/2026', 'nov/2026 (parcial)']
    assert total['text'] == ['R$ 300,80', 'R$ 2.508,14']
    app.selectbox(key='evolucao_categoria').set_value('Comida e bebida + Transporte')
    app.run()
    assert grafico(app, 'grafico_meses')['text'] == ['R$ 238,00', 'R$ 1.255,10']
    app.selectbox(key='evolucao_categoria').set_value(ft.COMIDA)
    app.run()
    assert grafico(app, 'grafico_meses')['text'] == ['R$ 38,00', 'R$ 511,60']


def test_fora_do_padrao_sem_e_com_historico(pasta_historico):
    app = abrir_com_exemplo()
    assert 'Ainda não há histórico suficiente: são precisas 2 faturas completas anteriores a esta, e há 0.' in textos(app)
    guardar_outubro(pasta_historico)
    setembro = ('date,title,amount\n2026-08-20,Restaurante Bom Prato,"950,00"\n2026-08-21,Auto Posto Primavera,"100,00"\n').encode('utf-8')
    hist.guardar(str(pasta_historico), setembro, 'Nubank_2026-09-25.csv', date(2026, 9, 25), date(2026, 9, 18), date(2026, 11, 4))
    app = abrir_com_exemplo()
    texto = textos(app)
    # Novembro aberto entra pela estimativa: comida 913,30 fica entre 38,00 e 950,00; transporte 1.280,47 passa de 200,00.
    assert r'- **Transporte**: R\$ 1.280,47 nesta fatura, acima do maior valor das 2 faturas anteriores (R\$ 200,00).' in texto
    assert r'- **Comida e bebida**: ' not in texto
    assert r'- **Total**: R\$ 3.685,00 nesta fatura, acima do maior valor das 2 faturas anteriores (R\$ 1.050,00).' in texto
    # Categoria que não existia antes (máximo 0): frase própria, sem "acima de R$ 0,00".
    assert r'- **Jogos**: R\$ 322,77 nesta fatura; não apareceu nas 2 faturas anteriores.' in texto
    assert r'(R\$ 0,00)' not in texto
    assert 'cada categoria ficaria fora desse intervalo por acaso 2 vezes em 3' in texto
    assert 'Com 9 categorias comparadas, espere uns 6,0 avisos só por acaso' in texto
    assert r'- **A classificar**: ' not in texto


# ---------------------------------------------------------------- casos-limite

def test_trocar_de_base_nao_guarda_a_fatura_aberta_na_outra_base(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    app = abrir_com_exemplo()
    assert (pasta_historico / '2026-11-25.json').exists()
    usar_base(app, 'Faturas simuladas')
    assert not app.exception
    assert list((simuladas / 'historico').glob('*.json')) == []


def test_fatura_simulada_nao_vai_para_minhas_faturas_ao_trocar_de_base(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    app = AppTest.from_file(ARQUIVO_APP, default_timeout=60)
    app.run()
    usar_base(app, 'Faturas simuladas')
    app.file_uploader[0].upload('Nubank_2026-11-25.csv', CONTEUDO_EXEMPLO, 'text/csv')
    app.run()
    assert (simuladas / 'historico' / '2026-11-25.json').exists()
    usar_base(app, 'Minhas faturas')
    assert not app.exception
    assert list(pasta_historico.glob('*.json')) == []


def test_rotulo_do_formulario_a_classificar_sobrevive_a_proxima_conferencia(pasta_historico, regras):
    caminho = regras.parent / 'rotulos.json'
    app = abrir_com_exemplo()
    app.selectbox(key='classificar_zarpa').set_value(ft.COMPRAS)
    clicar(app, 'Salvar categorias')
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'zarpa': ft.COMPRAS}
    assert '1 de 36 estabelecimentos desta fatura conferidos.' in textos(app)
    assert app.checkbox(key='conferir_ok_zarpa').value is True
    assert app.selectbox(key='conferir_categoria_zarpa').value == ft.COMPRAS
    app.checkbox(key='conferir_ok_auto posto girassol').check()
    clicar(app, 'Salvar conferência')
    assert not app.exception
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'auto posto girassol': ft.TRANSPORTE, 'zarpa': ft.COMPRAS}
    assert json.loads(regras.read_text(encoding='utf-8')) == {'zarpa': ft.COMPRAS}


def test_voltar_para_automatica_nao_e_desfeito_pela_proxima_conferencia(pasta_historico, regras):
    caminho = regras.parent / 'rotulos.json'
    app = abrir_com_exemplo()
    app.selectbox(key='conferir_categoria_auto posto primavera').set_value(ft.VIAGEM)
    app.checkbox(key='conferir_ok_auto posto primavera').check()
    clicar(app, 'Salvar conferência')
    assert json.loads(regras.read_text(encoding='utf-8')) == {'auto posto primavera': ft.VIAGEM}
    app.selectbox(key='corrigir_estabelecimento').set_value('auto posto primavera')
    app.selectbox(key='corrigir_categoria').set_value('Voltar para a categoria automática')
    clicar(app, 'Salvar correção')
    assert json.loads(caminho.read_text(encoding='utf-8')) == {}
    assert app.checkbox(key='conferir_ok_auto posto primavera').value is False
    assert app.selectbox(key='conferir_categoria_auto posto primavera').value == ft.TRANSPORTE
    app.checkbox(key='conferir_ok_auto posto girassol').check()
    clicar(app, 'Salvar conferência')
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'auto posto girassol': ft.TRANSPORTE}
    assert json.loads(regras.read_text(encoding='utf-8')) == {}
    assert metricas(app)['Transporte'] == 'R$ 743,50'


def test_corrigir_depois_de_conferir_nao_e_desfeito_pela_proxima_conferencia(pasta_historico, regras):
    caminho = regras.parent / 'rotulos.json'
    app = abrir_com_exemplo()
    app.selectbox(key='conferir_categoria_auto posto primavera').set_value(ft.VIAGEM)
    app.checkbox(key='conferir_ok_auto posto primavera').check()
    clicar(app, 'Salvar conferência')
    app.selectbox(key='corrigir_estabelecimento').set_value('auto posto primavera')
    app.selectbox(key='corrigir_categoria').set_value(ft.COMPRAS)
    clicar(app, 'Salvar correção')
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'auto posto primavera': ft.COMPRAS}
    assert app.selectbox(key='conferir_categoria_auto posto primavera').value == ft.COMPRAS
    app.checkbox(key='conferir_ok_auto posto girassol').check()
    clicar(app, 'Salvar conferência')
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'auto posto primavera': ft.COMPRAS, 'auto posto girassol': ft.TRANSPORTE}
    assert json.loads(regras.read_text(encoding='utf-8')) == {'auto posto primavera': ft.COMPRAS}


def test_conferencia_de_uma_base_nao_vaza_para_a_outra(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    app = abrir_com_exemplo()
    app.checkbox(key='conferir_ok_auto posto girassol').check()
    app.selectbox(key='conferir_categoria_auto posto primavera').set_value(ft.VIAGEM)
    app.checkbox(key='conferir_ok_auto posto primavera').check()
    clicar(app, 'Salvar conferência')
    usar_base(app, 'Faturas simuladas')
    if len(app.metric) == 0:
        app.file_uploader[0].upload('Nubank_2026-11-25.csv', SIMULADA_DE_EXEMPLO, 'text/csv')
        app.run()
        app.sidebar.date_input(key='hoje').set_value(date(2026, 11, 4))
        app.run()
    assert not app.exception
    assert '0 de 36 estabelecimentos desta fatura conferidos.' in textos(app)
    assert app.checkbox(key='conferir_ok_auto posto girassol').value is False
    assert app.checkbox(key='conferir_ok_auto posto primavera').value is False
    assert app.selectbox(key='conferir_categoria_auto posto primavera').value == ft.TRANSPORTE
    app.selectbox(key='conferir_categoria_conectanet').set_value(ft.CASA)
    app.checkbox(key='conferir_ok_conectanet').check()
    clicar(app, 'Salvar conferência')
    assert json.loads((simuladas / 'rotulos.json').read_text(encoding='utf-8')) == {'conectanet': ft.CASA}
    assert json.loads((simuladas / 'regras_usuario.json').read_text(encoding='utf-8')) == {'conectanet': ft.CASA}


# ---------------------------------------------------------------- fase 1: regressões

def test_origem_de_cada_rotulo_fica_registrada(pasta_historico, regras):
    origens = regras.parent / 'rotulos_origem.json'
    app = abrir_com_exemplo()
    app.checkbox(key='conferir_ok_auto posto girassol').check()
    app.selectbox(key='conferir_categoria_conectanet').set_value(ft.CASA)
    app.checkbox(key='conferir_ok_conectanet').check()
    clicar(app, 'Salvar conferência')
    app.selectbox(key='classificar_zarpa').set_value(ft.COMPRAS)
    clicar(app, 'Salvar categorias')
    app.selectbox(key='corrigir_estabelecimento').set_value('auto posto primavera')
    app.selectbox(key='corrigir_categoria').set_value(ft.VIAGEM)
    clicar(app, 'Salvar correção')
    assert not app.exception
    salvo = json.loads(origens.read_text(encoding='utf-8'))
    assert {chave: valor['origem'] for chave, valor in salvo.items()} == {
          'auto posto girassol': 'conferência: confirmou a categoria do app'
        , 'conectanet': 'conferência: trocou a categoria'
        , 'zarpa': 'formulário A classificar'
        , 'auto posto primavera': 'corrigir'
    }
    assert json.loads((regras.parent / 'rotulos.json').read_text(encoding='utf-8')) == {
          'auto posto girassol': ft.TRANSPORTE, 'conectanet': ft.CASA, 'zarpa': ft.COMPRAS, 'auto posto primavera': ft.VIAGEM
    }


# ---------------------------------------------------------------- fase 2: a mesma fatura não fica nas duas bases

def test_fatura_real_aberta_na_base_simulada_nao_e_guardada(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    app = abrir_com_exemplo()
    assert (pasta_historico / '2026-11-25.json').exists()
    usar_base(app, 'Faturas simuladas')
    app.file_uploader[0].upload('Nubank_2026-11-25.csv', CONTEUDO_EXEMPLO, 'text/csv')
    app.run()
    assert not app.exception
    assert not (simuladas / 'historico').exists() or list((simuladas / 'historico').glob('*.json')) == []
    assert any(aviso.value.startswith(r'Histórico: Não guardei: esta fatura já está guardada na base "Minhas faturas" \(vencimento 25/11/2026\)') for aviso in app.warning)
    # O resto do app funciona normalmente com a fatura aberta.
    assert metricas(app)['Gasto no período'] == 'R$ 2.508,14'


def test_fatura_simulada_nao_vai_para_minhas_faturas_nem_reaberta(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    app = AppTest.from_file(ARQUIVO_APP, default_timeout=60)
    app.run()
    usar_base(app, 'Faturas simuladas')
    app.file_uploader[0].upload('Nubank_2026-11-25.csv', SIMULADA_DE_EXEMPLO, 'text/csv')
    app.run()
    assert (simuladas / 'historico' / '2026-11-25.json').exists()
    usar_base(app, 'Minhas faturas')
    app.file_uploader[0].upload('Nubank_2026-11-25.csv', SIMULADA_DE_EXEMPLO, 'text/csv')
    app.run()
    assert not app.exception
    assert list(pasta_historico.glob('*.json')) == []
    assert any('já está guardada na base "Faturas simuladas"' in aviso.value for aviso in app.warning)


def test_adicionar_faturas_antigas_recusa_as_da_outra_base(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    hist.guardar(str(simuladas / 'historico'), OUTUBRO, 'Nubank_2026-10-25.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    app = abrir_com_exemplo()
    app.file_uploader(key='importar_antigas_Minhas faturas').upload('Nubank_2026-10-25.csv', OUTUBRO, 'text/csv')
    app.run()
    clicar(app, 'Guardar no histórico')
    assert not app.exception
    assert not (pasta_historico / '2026-10-25.json').exists()
    assert 'já está guardada na base' in textos(app)
    # Outra exportação da mesma fatura (um lançamento a mais, ou um a menos) também é recusada.
    pasta_simuladas = str(simuladas / 'historico')
    assert hist.guardada_em(pasta_simuladas, OUTUBRO + '2026-10-02,Padaria,"5,00"\n'.encode('utf-8')) == date(2026, 10, 25)
    assert hist.guardada_em(pasta_simuladas, OUTUBRO.replace('2026-10-01,Auto Posto Primavera,"200,00"\n'.encode('utf-8'), b'')) == date(2026, 10, 25)
    # Uma fatura parecida mas diferente (um lançamento com outro valor: nenhuma contém a outra) é aceita.
    diferente = OUTUBRO.replace('"200,00"'.encode('utf-8'), '"201,00"'.encode('utf-8'))
    assert hist.guardada_em(pasta_simuladas, diferente) is None


# ---------------------------------------------------------------- fase 2: sugestões do modelo

ROTULOS_PARA_SUGERIR = {
      'auto posto girassol': ft.TRANSPORTE
    , 'auto posto primavera': ft.TRANSPORTE
    , 'posto jacaranda': ft.TRANSPORTE
    , 'ifd*carla mendes de s': ft.COMIDA
    , 'cerealista do bairro': ft.COMIDA
    , 'tavola rest': ft.COMIDA
    , 'amazon': ft.COMPRAS
}


def sugestao_de(app, nome):
    for elemento in app.markdown:
        achado = re.match(r'\*\*' + re.escape(nome) + r'\*\* \(.*\): o modelo sugere \*\*(.+)\*\*, com confiança de (\d+)%\.', elemento.value)
        if achado:
            return achado.group(1).replace('\\', ''), int(achado.group(2))
    return None


def abrir_com_rotulos(regras):
    (regras.parent / 'rotulos.json').write_text(json.dumps(ROTULOS_PARA_SUGERIR, ensure_ascii=False), encoding='utf-8')
    return abrir_com_exemplo()


def test_sem_duas_categorias_rotuladas_nao_sugere(pasta_historico, regras):
    (regras.parent / 'rotulos.json').write_text(json.dumps({'auto posto primavera': ft.TRANSPORTE}), encoding='utf-8')
    app = abrir_com_exemplo()
    assert not app.exception
    assert 'precisa de pelo menos 2 categorias diferentes. Hoje há 1.' in textos(app)
    assert all(botao.label != 'Salvar decisões' for botao in app.button)


def test_sugestoes_aparecem_com_confianca_e_explicacao(pasta_historico, regras):
    app = abrir_com_rotulos(regras)
    assert not app.exception
    texto = textos(app)
    assert 'Modelo: Regressão Logística, treinado com 8 lançamento(s) de 7 estabelecimento(s) que você conferiu nesta base, em 3 categorias.' in texto
    nomes = ['Zarpa', 'Conectanet', 'Bandeirante', 'Lucasferreiramota', 'Bom Prato', 'Recanto Verde Parque', r'Mp \*Anapaulasilv', 'Arena Esportes Empreen']
    for nome in nomes:
        sugestao = sugestao_de(app, nome)
        assert sugestao is not None, nome
        assert sugestao[0] in [ft.TRANSPORTE, ft.COMIDA, ft.COMPRAS]
        assert 0 < sugestao[1] <= 100
    assert 'Nomes parecidos que você já conferiu: ' in texto or 'Nenhum estabelecimento conferido tem nome parecido' in texto
    assert 'Por quê' not in texto
    # Nada foi gravado só por mostrar sugestões.
    assert not regras.exists()
    assert json.loads((regras.parent / 'rotulos.json').read_text(encoding='utf-8')) == ROTULOS_PARA_SUGERIR
    elementos = list(app.markdown) + list(app.caption)
    for elemento in elementos:
        assert re.search(r'(?<!\\)\$', elemento.value) is None, elemento.value


def test_aceitar_rejeitar_e_corrigir_sugestoes(pasta_historico, regras):
    app = abrir_com_rotulos(regras)
    zarpa = sugestao_de(app, 'Zarpa')[0]
    conectanet = sugestao_de(app, 'Conectanet')[0]
    bandeirante = sugestao_de(app, 'Bandeirante')[0]
    correcao = ft.LAZER if bandeirante != ft.LAZER else ft.SAUDE
    app.radio(key='sugestao_acao_zarpa_0').set_value('Aceitar')
    app.radio(key='sugestao_acao_conectanet_0').set_value('Rejeitar')
    app.radio(key='sugestao_acao_bandeirante_0').set_value('Corrigir')
    app.selectbox(key='sugestao_categoria_bandeirante_0').set_value(correcao)
    clicar(app, 'Salvar decisões')
    assert not app.exception
    assert '1 sugestão(ões) aceita(s), 1 corrigida(s), 1 rejeitada(s).' in textos(app)
    salvas = json.loads(regras.read_text(encoding='utf-8'))
    assert salvas['zarpa'] == zarpa
    assert salvas['bandeirante'] == correcao
    assert 'conectanet' not in salvas
    rotulos_salvos = json.loads((regras.parent / 'rotulos.json').read_text(encoding='utf-8'))
    assert rotulos_salvos['zarpa'] == zarpa
    assert rotulos_salvos['bandeirante'] == correcao
    assert 'conectanet' not in rotulos_salvos
    origens = json.loads((regras.parent / 'rotulos_origem.json').read_text(encoding='utf-8'))
    assert origens['zarpa']['origem'] == 'aceitou sugestão do modelo'
    assert origens['bandeirante']['origem'] == 'corrigiu sugestão do modelo'
    assert json.loads((regras.parent / 'sugestoes_rejeitadas.json').read_text(encoding='utf-8')) == {'conectanet': [conectanet]}
    # Zarpa e Bandeirante saíram de "A classificar"; Conectanet continua a classificar.
    assert sugestao_de(app, 'Zarpa') is None
    assert sugestao_de(app, 'Bandeirante') is None
    # 378,90 - 149,90 (Zarpa) - 36,00 (Bandeirante)
    assert r'6 lançamentos (R\$ 193,00) ainda não têm categoria' in textos(app)
    nova_conectanet = sugestao_de(app, 'Conectanet')
    # A sugestão rejeitada não volta; se o modelo retreinado sugerir outra categoria, ela aparece.
    if nova_conectanet is None:
        assert '1 sugestão(ões) que você rejeitou não aparecem mais.' in textos(app)
    else:
        assert nova_conectanet[0] != conectanet
    # Os campos voltam ao padrão depois de salvar (rodada nova).
    assert app.radio(key='sugestao_acao_lucasferreiramota_1').value == 'Decidir depois'


def test_decidir_depois_nao_grava_nada(pasta_historico, regras):
    app = abrir_com_rotulos(regras)
    clicar(app, 'Salvar decisões')
    assert not app.exception
    assert 'Nenhuma decisão escolhida.' in textos(app)
    assert not regras.exists()
    assert not (regras.parent / 'sugestoes_rejeitadas.json').exists()


def test_rejeitadas_corrompidas_desligam_sugestoes(pasta_historico, regras):
    (regras.parent / 'sugestoes_rejeitadas.json').write_text('{quebrado', encoding='utf-8')
    app = abrir_com_rotulos(regras)
    assert not app.exception
    assert any('As sugestões do modelo estão desligadas' in aviso.value for aviso in app.warning)
    assert all(botao.label != 'Salvar decisões' for botao in app.button)
    assert (regras.parent / 'sugestoes_rejeitadas.json').read_text(encoding='utf-8') == '{quebrado'


# ---------------------------------------------------------------- casos-limite

def sugestoes_por_chave(app, rodada=0):
    categorias = []
    for elemento in app.markdown:
        achado = re.match(r'\*\*.+\*\* \(.*\): o modelo sugere \*\*(.+)\*\*, com confiança de \d+%\.', elemento.value)
        if achado:
            categorias.append(achado.group(1).replace('\\', ''))
    radios = [r for r in app.radio if r.key and r.key.startswith('sugestao_acao_') and r.key.endswith(f'_{rodada}')]
    assert len(radios) == len(categorias)
    return {r.key[len('sugestao_acao_'):-len(f'_{rodada}')]: (r, c) for r, c in zip(radios, categorias)}


def test_fatura_recusada_nao_deixa_gravar_dados_dela_na_base_errada(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    chaves_reais = {ft.chave_estabelecimento(d) for d in ft.ler_csv(CONTEUDO_EXEMPLO)['descricao']}
    app = abrir_com_exemplo()
    usar_base(app, 'Faturas simuladas')
    app.file_uploader[0].upload('Nubank_2026-11-25.csv', CONTEUDO_EXEMPLO, 'text/csv')
    app.run()
    assert any('já está guardada na base "Minhas faturas"' in aviso.value for aviso in app.warning)
    seletores = [s for s in app.selectbox if s.key and s.key.startswith('classificar_')]
    if seletores:
        seletores[0].set_value(ft.COMPRAS)
        clicar(app, 'Salvar categorias')
        assert not app.exception
    corrigir = [s for s in app.selectbox if s.key == 'corrigir_categoria']
    if corrigir:
        corrigir[0].set_value(ft.LAZER)
        clicar(app, 'Salvar correção')
        assert not app.exception
    for nome in ['regras_usuario.json', 'rotulos.json', 'rotulos_origem.json', 'sugestoes_rejeitadas.json']:
        caminho = simuladas / nome
        if caminho.exists():
            assert set(json.loads(caminho.read_text(encoding='utf-8'))).isdisjoint(chaves_reais), nome


def test_corrigir_sem_escolher_a_categoria_nao_grava_a_primeira_da_lista(pasta_historico, regras):
    app = abrir_com_rotulos(regras)
    sugestoes = sugestoes_por_chave(app)
    alvos = [chave for chave, (radio, categoria) in sugestoes.items() if categoria != ft.COMIDA]
    assert alvos, 'o teste precisa de uma sugestão diferente de Comida e bebida'
    chave = alvos[0]
    sugestoes[chave][0].set_value('Corrigir')
    clicar(app, 'Salvar decisões')
    assert not app.exception
    if regras.exists():
        assert json.loads(regras.read_text(encoding='utf-8')).get(chave) != ft.COMIDA
    assert json.loads((regras.parent / 'rotulos.json').read_text(encoding='utf-8')).get(chave) != ft.COMIDA


def test_rejeicao_vale_numa_nova_sessao_e_so_na_base_dela(pasta_historico, regras):
    app = abrir_com_rotulos(regras)
    sugestoes = sugestoes_por_chave(app)
    chave, (radio, categoria) = next(iter(sugestoes.items()))
    radio.set_value('Rejeitar')
    clicar(app, 'Salvar decisões')
    assert not app.exception
    assert json.loads((regras.parent / 'sugestoes_rejeitadas.json').read_text(encoding='utf-8')) == {chave: [categoria]}
    nova = abrir_com_exemplo()
    assert not nova.exception
    depois = sugestoes_por_chave(nova)
    assert chave not in depois or depois[chave][1] != categoria
    usar_base(nova, 'Faturas simuladas')
    assert not (regras.parent / 'simuladas' / 'sugestoes_rejeitadas.json').exists()


def test_exportacao_parcial_da_fatura_real_tambem_e_recusada_na_outra_base(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    app = abrir_com_exemplo()
    parcial = b''.join(CONTEUDO_EXEMPLO.splitlines(keepends=True)[:-1])
    usar_base(app, 'Faturas simuladas')
    app.file_uploader[0].upload('Nubank_2026-11-25.csv', parcial, 'text/csv')
    app.run()
    assert not app.exception
    assert not (simuladas / 'historico' / '2026-11-25.json').exists()


# ---------------------------------------------------------------- fase 2: regressões

def test_sugestao_rejeitada_some_na_mesma_sessao_quando_nada_mais_muda(pasta_historico, regras):
    # Sem aceitar nem corrigir nada, o modelo não muda: a sugestão rejeitada precisa sumir (caminho "escondida").
    app = abrir_com_rotulos(regras)
    sugestoes = sugestoes_por_chave(app)
    chave, (radio, categoria) = next(iter(sugestoes.items()))
    radio.set_value('Rejeitar')
    clicar(app, 'Salvar decisões')
    assert not app.exception
    depois = sugestoes_por_chave(app, rodada=1)
    assert chave not in depois
    assert '1 sugestão(ões) que você rejeitou não aparecem mais.' in textos(app)
    assert len(depois) == len(sugestoes) - 1


def test_fatura_recusada_mostra_so_o_aviso_na_aba_classificar(pasta_historico, regras):
    app = abrir_com_exemplo()
    usar_base(app, 'Faturas simuladas')
    app.file_uploader[0].upload('Nubank_2026-11-25.csv', CONTEUDO_EXEMPLO, 'text/csv')
    app.run()
    assert not app.exception
    assert any('Esta fatura é da base "Minhas faturas"' in aviso.value for aviso in app.warning)
    for rotulo in ['Salvar categorias', 'Salvar conferência', 'Salvar correção', 'Salvar decisões']:
        assert all(botao.label != rotulo for botao in app.button), rotulo


def test_aviso_de_pendentes_na_base_errada_nao_manda_para_a_aba_classificar(pasta_historico, regras):
    simuladas = regras.parent / 'simuladas'
    hist.guardar(str(simuladas / 'historico'), CONTEUDO_EXEMPLO, 'Nubank_2026-11-25.csv', date(2026, 11, 25), date(2026, 11, 18), date(2026, 11, 4))
    app = abrir_com_exemplo()
    assert not app.exception
    pendentes = [texto for texto in [aviso.value for aviso in app.warning] if 'ainda não têm categoria' in texto]
    assert len(pendentes) == 1
    assert 'troque para a base onde esta fatura está guardada' in pendentes[0]
    assert 'aba **Classificar**' not in pendentes[0]
    # Na base certa o aviso continua apontando para a aba Classificar.
    app_certa = abrir_com_exemplo()
    usar_base(app_certa, 'Faturas simuladas')
    if len(app_certa.metric) == 0:
        app_certa.file_uploader[0].upload('Nubank_2026-11-25.csv', CONTEUDO_EXEMPLO, 'text/csv')
        app_certa.run()
    assert not app_certa.exception
    pendentes_certa = [aviso.value for aviso in app_certa.warning if 'ainda não têm categoria' in aviso.value]
    assert len(pendentes_certa) == 1 and 'aba **Classificar**' in pendentes_certa[0]


# ---------------------------------------------------------------- casos-limite

def test_fatura_da_outra_base_com_datas_invalidas_tambem_nao_grava_na_base_errada(pasta_historico, regras):
    salvar = ['Salvar categorias', 'Salvar conferência', 'Salvar correção', 'Salvar decisões']
    app = abrir_com_exemplo()
    usar_base(app, 'Faturas simuladas')
    app.file_uploader[0].upload('fatura.csv', CONTEUDO_EXEMPLO, 'text/csv')
    app.run()
    assert not app.exception
    for rotulo in salvar:
        assert all(botao.label != rotulo for botao in app.button), ('sem data no nome', rotulo)
    app2 = abrir_com_exemplo()
    usar_base(app2, 'Faturas simuladas')
    app2.file_uploader[0].upload('Nubank_2026-11-25.csv', CONTEUDO_EXEMPLO, 'text/csv')
    app2.run()
    app2.sidebar.date_input(key='fechamento_2026-11-25').set_value(date(2026, 11, 26))
    app2.run()
    assert not app2.exception
    for rotulo in salvar:
        assert all(botao.label != rotulo for botao in app2.button), ('fechamento inválido', rotulo)
