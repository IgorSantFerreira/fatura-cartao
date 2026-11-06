# Fase 4: ferramentas/preparar_demonstracao.py prepara a base simulada só com faturas fictícias.

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

import fatura as ft
import historico as hist
import rotulos as rt


ARQUIVO = Path(__file__).parent.parent / 'ferramentas' / 'preparar_demonstracao.py'
HOJE = date(2026, 11, 6)


@pytest.fixture(scope='module')
def demonstracao():
    especificacao = importlib.util.spec_from_file_location('preparar_demonstracao', ARQUIVO)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


def test_guarda_as_12_primeiras_completas_e_a_ultima_parcial(demonstracao, tmp_path):
    simuladas = tmp_path / 'simuladas'
    minhas = tmp_path / 'minhas' / 'historico'
    resultado = demonstracao.preparar(simuladas, minhas, False, HOJE)
    assert [situacao for vencimento, situacao in resultado] == [hist.NOVA] * 13
    entradas, erros = hist.carregar_historico(str(simuladas / 'historico'))
    assert erros == []
    assert [entrada['vencimento'] for entrada in entradas] == [vencimento for vencimento, situacao in resultado]
    assert all(entrada['completa'] for entrada in entradas[:12])
    # A última (a que se abre ao vivo) fica parcial: o app a completa quando ela é aberta.
    assert entradas[-1]['vencimento'] == date(2026, 10, 25) and not entradas[-1]['completa']
    # A base "Minhas faturas" não é tocada.
    assert not minhas.exists()
    assert not (simuladas / 'rotulos.json').exists()


def test_rodar_de_novo_nao_duplica(demonstracao, tmp_path):
    simuladas = tmp_path / 'simuladas'
    minhas = tmp_path / 'minhas'
    demonstracao.preparar(simuladas, minhas, False, HOJE)
    resultado = demonstracao.preparar(simuladas, minhas, False, HOJE)
    assert [situacao for vencimento, situacao in resultado] == [hist.IGUAL] * 13
    assert len(list((simuladas / 'historico').glob('*.json'))) == 13


def test_com_rotulos_confere_as_categorias_pelo_gabarito(demonstracao, tmp_path):
    simuladas = tmp_path / 'simuladas'
    demonstracao.preparar(simuladas, tmp_path / 'minhas', True, HOJE)
    rotulos, erro = rt.carregar_rotulos(str(simuladas / 'rotulos.json'))
    assert erro is None and len(rotulos) >= 20
    assert set(rotulos.values()) <= set(rt.CATEGORIAS_ROTULO)
    origens, erro = rt.carregar_origens(rt.caminho_origens(str(simuladas / 'rotulos.json')))
    assert erro is None
    assert {origem['origem'] for origem in origens.values()} == {demonstracao.ORIGEM_DEMONSTRACAO}
    assert json.loads((simuladas / 'regras_usuario.json').read_text(encoding='utf-8'))


def test_fatura_que_esta_na_base_minhas_faturas_e_recusada(demonstracao, tmp_path):
    simuladas = tmp_path / 'simuladas'
    minhas = tmp_path / 'minhas'
    gerador = demonstracao.carregar_gerador()
    vencimento, linhas = gerador.gerar(13, 2026, date(2025, 10, 25))[0]
    hist.guardar(str(minhas), demonstracao.texto_csv(gerador, linhas).encode('utf-8'), 'x.csv', vencimento, date(2025, 10, 18), HOJE)
    resultado = demonstracao.preparar(simuladas, minhas, False, HOJE)
    assert resultado[0] == (vencimento, 'recusada: já está na base "Minhas faturas"')
    assert not (simuladas / 'historico' / f'{vencimento.isoformat()}.json').exists()
    assert len(list((simuladas / 'historico').glob('*.json'))) == 12


def test_mesma_pasta_da_base_minhas_faturas_e_recusada(demonstracao, tmp_path):
    simuladas = tmp_path / 'base'
    with pytest.raises(SystemExit):
        demonstracao.preparar(simuladas, simuladas / 'historico', False, HOJE)
    assert not (simuladas / 'historico').exists()


def test_a_ultima_fatura_do_gerador_e_a_que_fica_para_abrir_no_app(demonstracao):
    gerador = demonstracao.carregar_gerador()
    assert gerador.gerar(13, 2026, date(2025, 10, 25))[-1][0] == demonstracao.gerador_ultimo_vencimento() == date(2026, 10, 25)


# ---------------------------------------------------------------- casos-limite

def test_red_team_f4_atC_rotulo_conferido_pela_pessoa_na_base_simulada_nao_e_trocado(demonstracao, tmp_path):
    simuladas = tmp_path / 'simuladas'
    gerador = demonstracao.carregar_gerador()
    faturas = gerador.gerar(13, 2026, date(2025, 10, 25))
    for dia, titulo, centavos, categoria, comportamento in faturas[0][1]:
        if categoria in rt.CATEGORIAS_ROTULO and centavos > 0 and not ft.e_estorno(titulo, centavos):
            break
    chave = ft.chave_estabelecimento(titulo)
    outra = [c for c in rt.CATEGORIAS_ROTULO if c != categoria][0]
    caminho = str(simuladas / 'rotulos.json')
    rt.salvar_rotulos(caminho, {chave: outra})
    rt.salvar_origens(rt.caminho_origens(caminho), rt.atualizar_origens({}, {}, {chave: outra}, {chave: rt.ORIGEM_TROCOU}, HOJE))
    try:
        demonstracao.preparar(simuladas, tmp_path / 'minhas', True, HOJE)
    except SystemExit:
        pass  # recusar sem gravar também é aceitável
    rotulos, erro = rt.carregar_rotulos(caminho)
    assert erro is None and rotulos[chave] == outra
    origens, erro = rt.carregar_origens(rt.caminho_origens(caminho))
    assert origens[chave]['origem'] == rt.ORIGEM_TROCOU


def test_red_team_f4_atD_fatura_simulada_guardada_pela_pessoa_nao_e_substituida(demonstracao, tmp_path):
    historico = tmp_path / 'simuladas' / 'historico'
    propria = b'date,title,amount\n2026-02-20,Padaria da Pessoa,"12,34"\n'
    hist.guardar(str(historico), propria, 'Nubank_2026-03-25.csv', date(2026, 3, 25), date(2026, 3, 18), HOJE)
    antes = (historico / '2026-03-25.json').read_bytes()
    try:
        demonstracao.preparar(tmp_path / 'simuladas', tmp_path / 'minhas', False, HOJE)
    except SystemExit:
        pass
    assert (historico / '2026-03-25.json').read_bytes() == antes


def test_red_team_f4_atB_pasta_simulada_com_arquivos_da_base_minhas_faturas_e_recusada(demonstracao, tmp_path, monkeypatch):
    base = tmp_path / 'base'
    base.mkdir()
    regras_reais = base / 'regras_usuario.json'
    regras_reais.write_text(json.dumps({'padaria da pessoa': ft.COMIDA}, ensure_ascii=False), encoding='utf-8')
    antes = regras_reais.read_bytes()
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('FATURA_HISTORICO', str(tmp_path / 'minhas' / 'historico'))
    monkeypatch.setenv('FATURA_ROTULOS', str(tmp_path / 'minhas' / 'rotulos.json'))
    monkeypatch.setenv('FATURA_REGRAS', str(regras_reais))
    monkeypatch.delenv('FATURA_SIMULADAS', raising=False)
    monkeypatch.setattr('sys.argv', ['preparar_demonstracao.py', '--com-rotulos', '--pasta', str(base)])
    with pytest.raises(SystemExit) as erro:
        demonstracao.main()
    assert 'Minhas faturas' in str(erro.value.code)
    assert regras_reais.read_bytes() == antes
    assert not (base / 'historico').exists()
