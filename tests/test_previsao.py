# Fase 3: gerador de população e previsão do gasto no fechamento (src/previsao.py). Só dados fictícios.

import hashlib
from datetime import date, timedelta

import pytest

import fatura as ft
import metas as mt
import previsao as pv
from exemplo import CONTEUDO_EXEMPLO


INICIO = date(2026, 10, 18)
ULTIMO_DIA = date(2026, 11, 17)


def fatura_exemplo():
    return ft.montar_fatura(ft.ler_csv(CONTEUDO_EXEMPLO), {})


def curva_anterior_parecida():
    # A fatura de exemplo com as datas um mês antes, no ciclo de 18/09 a 17/10: uma anterior de tamanho parecido.
    linhas = CONTEUDO_EXEMPLO.decode('utf-8').splitlines()
    novas = [linhas[0]]
    for linha in linhas[1:]:
        data, resto = linha.split(',', 1)
        novas.append(ft.somar_meses(date.fromisoformat(data), -1).isoformat() + ',' + resto)
    fatura = ft.montar_fatura(ft.ler_csv('\n'.join(novas) + '\n'), {})
    return pv.curva(fatura, date(2026, 9, 18), date(2026, 10, 17))


@pytest.fixture(scope='module')
def gerador():
    return pv.carregar_gerador()


@pytest.fixture(scope='module')
def treinado():
    # População pequena: o que se testa aqui é o comportamento, não a qualidade da previsão.
    return pv.treinar_para_app(semente=11, pessoas_treino=8, pessoas_calibracao=6)


# ---------------------------------------------------------------- gerador

def impressao_digital(pasta):
    resumo = hashlib.sha256()
    for arquivo in sorted(pasta.rglob('*')):
        if arquivo.is_file():
            resumo.update(arquivo.relative_to(pasta).as_posix().encode('utf-8'))
            resumo.update(arquivo.read_bytes())
    return resumo.hexdigest()


def test_gerador_sem_opcoes_novas_gera_os_mesmos_arquivos_da_fase_2(gerador, tmp_path):
    # Impressão digital da saída do gerador no commit e3369c0 (13 meses, semente 2026): as faturas e o notebook
    # da fase 2 não podem mudar por causa da população da fase 3.
    gerador.gravar(gerador.gerar(13, 2026, date(2025, 10, 25)), tmp_path)
    assert impressao_digital(tmp_path) == 'bfe6510b6d2a957b74a86cfc0ecaf5b7a0114be002d811c905d9ae6bd4fbb1e5'


def test_populacao_e_reprodutivel_e_tem_datas_dentro_do_ciclo(gerador):
    primeira = gerador.gerar_populacao(6, 13, 5, date(2025, 10, 25))
    segunda = gerador.gerar_populacao(6, 13, 5, date(2025, 10, 25))
    assert [pessoa['faturas'] for pessoa in primeira] == [pessoa['faturas'] for pessoa in segunda]
    vencimentos = set()
    for pessoa in primeira:
        assert len(pessoa['faturas']) == 13
        for vencimento, linhas in pessoa['faturas']:
            vencimentos.add(vencimento.day)
            datas = ft.ciclo(vencimento)
            for dia, titulo, centavos, categoria, comportamento in linhas:
                assert datas['inicio'] <= dia <= datas['ultimo_dia'], (pessoa['pessoa'], vencimento, titulo, dia)
    assert vencimentos <= set(gerador.DIAS_VENCIMENTO)


def test_com_e_sem_salario_sao_as_mesmas_pessoas_com_os_mesmos_gastos_em_outros_dias(gerador):
    com = gerador.gerar_populacao(4, 6, 5, date(2025, 10, 25), True)
    sem = gerador.gerar_populacao(4, 6, 5, date(2025, 10, 25), False)
    mudou_dia = False
    for pessoa_com, pessoa_sem in zip(com, sem):
        assert pessoa_com['perfil'] == pessoa_sem['perfil']
        for (vencimento_com, linhas_com), (vencimento_sem, linhas_sem) in zip(pessoa_com['faturas'], pessoa_sem['faturas']):
            assert vencimento_com == vencimento_sem
            assert sorted((titulo, centavos) for dia, titulo, centavos, categoria, comportamento in linhas_com) == sorted(
                (titulo, centavos) for dia, titulo, centavos, categoria, comportamento in linhas_sem
            )
            if sorted(linha[0] for linha in linhas_com) != sorted(linha[0] for linha in linhas_sem):
                mudou_dia = True
    assert mudou_dia


def test_efeito_do_salario_concentra_o_gasto_do_dia_a_dia_depois_do_salario(gerador):
    def fracao(populacao):
        depois = 0
        total = 0
        for pessoa in populacao:
            janela = dict(pessoa['perfil'], duracao=7, intensidade=1.0)
            for vencimento, linhas in pessoa['faturas']:
                for dia, titulo, centavos, categoria, comportamento in linhas:
                    if comportamento != 'ocasional':
                        continue
                    total = total + centavos
                    if gerador.peso_do_salario(janela, dia) > 1:
                        depois = depois + centavos
        return depois / total

    com = fracao(gerador.gerar_populacao(20, 13, 9, date(2025, 10, 25), True))
    sem = fracao(gerador.gerar_populacao(20, 13, 9, date(2025, 10, 25), False))
    assert com > sem + 0.05, (com, sem)


def test_quinto_dia_util(gerador):
    # Novembro de 2026 começa num domingo: dias úteis 2, 3, 4, 5, 6.
    assert gerador.dias_de_salario(gerador.SALARIO_QUINTO_DIA_UTIL, 2026, 11) == [date(2026, 11, 6)]
    assert gerador.dias_de_salario(gerador.SALARIO_QUINZENA, 2026, 11) == [date(2026, 11, 5), date(2026, 11, 20)]


# ---------------------------------------------------------------- curva, atributos e projeção linear

def test_projecao_linear_da_curva_e_a_mesma_do_app_em_todos_os_dias():
    fatura = fatura_exemplo()
    curva = pv.curva(fatura, INICIO, ULTIMO_DIA)
    for j in range(1, curva['dias_total'] + 1):
        dia = INICIO + timedelta(days=j - 1)
        resultado = ft.projecao(fatura, INICIO, ULTIMO_DIA, dia)
        assert int(curva['gasto_ate'][j - 1]) == resultado['atual'], j
        assert int(curva['gasto_ate'][j - 1]) + pv.linear_a_mais(curva, j) == resultado['projetado'], j
    assert curva['total'] == ft.totais(fatura)['gasto']


def test_atributos_nao_usam_lancamentos_depois_do_dia_da_previsao():
    fatura = fatura_exemplo()
    anterior = pv.curva(fatura, INICIO, ULTIMO_DIA)
    curva = pv.curva(fatura, INICIO, ULTIMO_DIA)
    for j in [1, 5, 15, 30]:
        dia = INICIO + timedelta(days=j - 1)
        truncada = fatura[fatura['data'].dt.date <= dia].reset_index(drop=True)
        assert pv.atributos(curva, j, [anterior]) == pv.atributos(pv.curva(truncada, INICIO, ULTIMO_DIA), j, [anterior]), j


def test_atributos_usam_no_maximo_as_anteriores_mais_recentes():
    fatura = fatura_exemplo()
    curva = pv.curva(fatura, INICIO, ULTIMO_DIA)
    vazia = pv.curva(fatura.iloc[0:0], INICIO, ULTIMO_DIA)
    muitas = [vazia] * 5 + [curva] * pv.ANTERIORES_MAXIMO
    assert pv.atributos(curva, 10, muitas) == pv.atributos(curva, 10, [curva] * pv.ANTERIORES_MAXIMO)


def test_dia_fora_do_ciclo_e_recusado():
    curva = pv.curva(fatura_exemplo(), INICIO, ULTIMO_DIA)
    with pytest.raises(ValueError):
        pv.atributos(curva, 0, [])
    with pytest.raises(ValueError):
        pv.atributos(curva, curva['dias_total'] + 1, [])


# ---------------------------------------------------------------- previsão do app

def test_sem_historico_nao_ha_previsao_por_ml(treinado):
    resultado = pv.prever(treinado, fatura_exemplo(), INICIO, ULTIMO_DIA, date(2026, 11, 4), [])
    assert resultado['historico_suficiente'] is (pv.HISTORICO_MINIMO == 0)
    assert resultado['anteriores'] == 0
    if not resultado['historico_suficiente']:
        assert 'previsto' not in resultado
    projecao = ft.projecao(fatura_exemplo(), INICIO, ULTIMO_DIA, date(2026, 11, 4))
    assert resultado['linear'] == projecao['projetado']


def test_com_historico_preve_com_faixa_que_nao_desce_abaixo_do_gasto_atual(treinado):
    fatura = fatura_exemplo()
    anterior = curva_anterior_parecida()
    resultado = pv.prever(treinado, fatura, INICIO, ULTIMO_DIA, date(2026, 11, 4), [anterior] * max(pv.HISTORICO_MINIMO, 1))
    assert resultado['historico_suficiente']
    assert resultado['fora_do_treino'] == []
    assert isinstance(resultado['previsto'], int)
    assert resultado['atual'] == ft.projecao(fatura, INICIO, ULTIMO_DIA, date(2026, 11, 4))['atual']
    assert 'baixo' in resultado
    assert resultado['atual'] <= resultado['baixo'] <= resultado['alto']
    assert resultado['erro_tipico'] >= 0


def test_historico_muito_diferente_do_treino_nao_gera_numero_do_modelo(treinado):
    # Fatura anterior de R$ 10 e a atual de mais de R$ 2.000: a escala vira o piso e o gasto atual fica muito acima
    # de tudo que o modelo viu. Sem número do modelo, em vez de uma extrapolação.
    fatura = fatura_exemplo()
    pequena = ft.montar_fatura(ft.ler_csv('date,title,amount\n2026-09-20,Padaria X,"10,00"\n'), {})
    anterior = pv.curva(pequena, date(2026, 9, 18), date(2026, 10, 17))
    resultado = pv.prever(treinado, fatura, INICIO, ULTIMO_DIA, date(2026, 11, 4), [anterior])
    assert 'atual_n' in resultado['fora_do_treino']
    assert 'previsto' not in resultado


def test_a_mais_previsto_nunca_e_negativo(treinado):
    tabela = pv.tabela_de_retratos(pv.curvas_da_populacao(2, 3, meses=4))
    tabela['atual_n'] = tabela['atual_n'] * 50
    previstos = pv.prever_totais(treinado['modelo'], tabela)
    assert (previstos >= tabela['atual'].to_numpy()).all()


def test_previsao_ignora_lancamentos_depois_de_hoje(treinado):
    fatura = fatura_exemplo()
    anterior = curva_anterior_parecida()
    hoje = date(2026, 10, 30)
    so_ate_hoje = fatura[fatura['data'].dt.date <= hoje].reset_index(drop=True)
    completa = pv.prever(treinado, fatura, INICIO, ULTIMO_DIA, hoje, [anterior])
    assert 'previsto' in completa
    assert completa == pv.prever(treinado, so_ate_hoje, INICIO, ULTIMO_DIA, hoje, [anterior])


def test_sem_previsao_antes_do_inicio_e_com_as_compras_encerradas(treinado):
    fatura = fatura_exemplo()
    assert pv.prever(treinado, fatura, INICIO, ULTIMO_DIA, INICIO - timedelta(days=1), []) is None
    assert pv.prever(treinado, fatura, INICIO, ULTIMO_DIA, ULTIMO_DIA, []) is None
    assert pv.prever(treinado, fatura, INICIO, ULTIMO_DIA, ULTIMO_DIA + timedelta(days=10), []) is None


def test_modelo_do_app_e_treinado_so_com_retratos_com_o_historico_minimo(treinado):
    tabela = pv.tabela_de_retratos(pv.curvas_da_populacao(2, 3, meses=4))
    usados = pv.retratos_de_treino(tabela)
    assert (usados['anteriores'] >= pv.HISTORICO_MINIMO).all()
    assert (usados['j'] % pv.PASSO_DIAS_APP == 0).all()
    assert treinado['tipo'] == pv.TIPO_APP


# ---------------------------------------------------------------- orçamento da fatura inteira

def test_orcamento_da_fatura_inteira_usa_a_previsao_do_modelo_e_as_outras_metas_o_ritmo():
    metas = mt.definir_meta([], mt.CATEGORIAS_META, 300000)
    metas = mt.definir_meta(metas, [ft.COMIDA], 50000)
    atual = {ft.COMIDA: 40000, ft.TRANSPORTE: 100000}
    projetado = {ft.COMIDA: 45000, ft.TRANSPORTE: 150000}
    linhas = mt.situacao(metas, atual, projetado, 10, previsto_total=320000)
    inteira = [linha for linha in linhas if linha['nome'] == mt.FATURA_INTEIRA][0]
    comida = [linha for linha in linhas if linha['nome'] == ft.COMIDA][0]
    assert inteira['projetado'] == 320000 and inteira['fonte'] == mt.MODELO and inteira['estado'] == 'vai estourar'
    assert 'pela previsão do modelo deve fechar em' in mt.frase_situacao(inteira)
    assert comida['projetado'] == 45000 and comida['fonte'] == mt.RITMO and comida['estado'] == 'dentro'
    # Sem previsão do modelo, o orçamento da fatura inteira usa o ritmo (soma das categorias).
    sem_modelo = mt.situacao(metas, atual, projetado, 10)
    assert [linha for linha in sem_modelo if linha['nome'] == mt.FATURA_INTEIRA][0]['projetado'] == 195000


# ---------------------------------------------------------------- casos-limite

@pytest.mark.parametrize('j', [1, 2, 3, 30])
def test_red_team_at1_dias_do_comeco_e_do_fim_nao_ficam_fora_do_treino_so_pela_fracao(treinado, j):
    fatura = fatura_exemplo()
    anterior = curva_anterior_parecida()
    hoje = INICIO + timedelta(days=j - 1)
    resultado = pv.prever(treinado, fatura, INICIO, ULTIMO_DIA, hoje, [anterior])
    assert resultado is not None
    assert 'fracao_decorrida' not in resultado['fora_do_treino'], (j, resultado['fora_do_treino'])


def test_red_team_at8_cli_da_populacao_e_deterministico_e_grava_o_perfil(tmp_path):
    import csv as modulo_csv
    import subprocess
    import sys
    for pasta in ['a', 'b']:
        subprocess.run([sys.executable, str(pv.ARQUIVO_GERADOR), '--pessoas', '3', '--meses', '4', '--saida', str(tmp_path / pasta)], check=True)
    assert impressao_digital(tmp_path / 'a') == impressao_digital(tmp_path / 'b')
    assert len(list((tmp_path / 'a' / 'faturas').iterdir())) == 3
    with open(tmp_path / 'a' / 'perfis.csv', encoding='utf-8') as arquivo:
        cabecalho = next(modulo_csv.reader(arquivo))
    for coluna in ['salario', 'intensidade', 'duracao_dias', 'efeito_salario_ligado', 'meses_viagem', 'meses_atraso', 'meses_estorno']:
        assert coluna in cabecalho, coluna
    resultado = subprocess.run([sys.executable, str(pv.ARQUIVO_GERADOR), '--sem-salario', '--saida', str(tmp_path / 'c')], capture_output=True)
    assert resultado.returncode != 0
    assert not (tmp_path / 'c').exists()


def test_historico_curto_simula_pessoa_com_poucas_faturas_sem_repetir_casos():
    curvas = pv.curvas_da_populacao(1, 3, meses=5)['pessoa_000']
    curtos = pv.retratos_com_historico_curto(curvas, 'pessoa_000')
    quantidades = {linha['anteriores'] for linha in curtos}
    assert quantidades == {1, 2}
    # Ciclo 0 não tem anteriores; ciclo 1 já tem exatamente 1 e ciclo 2 exatamente 2 (não se repetem).
    ciclos = {linha['ciclo'] for linha in curtos}
    assert ciclos == {'2 com 1 anterior(es)', '3 com 1 anterior(es)', '4 com 1 anterior(es)', '3 com 2 anterior(es)', '4 com 2 anterior(es)'}
    # Com 1 anterior, o histórico é só a fatura imediatamente antes.
    linha = [linha for linha in curtos if linha['ciclo'] == '4 com 1 anterior(es)' and linha['j'] == 10][0]
    assert linha == dict(pv.atributos(curvas[4], 10, [curvas[3]]), pessoa='pessoa_000', ciclo='4 com 1 anterior(es)', total=curvas[4]['total'], alvo_n=linha['alvo_n'])


# ---------------------------------------------------------------- modelo guardado no computador (fase 4)

def test_modelo_e_guardado_e_lido_do_arquivo_sem_treinar_de_novo(tmp_path, monkeypatch):
    pasta = tmp_path / 'modelo'
    primeiro, origem, aviso = pv.carregar_ou_treinar(pasta, 6, 4)
    assert origem == 'treino' and aviso is None
    arquivos = list(pasta.glob('modelo_previsao_*.pkl'))
    assert len(arquivos) == 1

    def nao_treinar(*args, **kwargs):
        raise AssertionError('não devia treinar de novo')
    monkeypatch.setattr(pv, 'treinar_para_app', nao_treinar)
    segundo, origem, aviso = pv.carregar_ou_treinar(pasta, 6, 4)
    assert origem == 'arquivo' and aviso is None
    # O modelo lido dá exatamente a mesma previsão do recém-treinado.
    fatura = fatura_exemplo()
    anterior = curva_anterior_parecida()
    hoje = date(2026, 11, 4)
    assert pv.prever(primeiro, fatura, INICIO, ULTIMO_DIA, hoje, [anterior]) == pv.prever(segundo, fatura, INICIO, ULTIMO_DIA, hoje, [anterior])
    assert segundo['quantis'] == primeiro['quantis'] and segundo['limites'] == primeiro['limites']


def test_arquivo_corrompido_treina_de_novo_e_substitui(tmp_path):
    pasta = tmp_path / 'modelo'
    pv.carregar_ou_treinar(pasta, 6, 4)
    caminho = list(pasta.glob('modelo_previsao_*.pkl'))[0]
    caminho.write_bytes(b'nao e um pickle')
    treinado, origem, aviso = pv.carregar_ou_treinar(pasta, 6, 4)
    assert origem == 'treino' and aviso is None
    assert pv.treinado_valido(treinado, 6, 4)
    assert pv.carregar_ou_treinar(pasta, 6, 4)[1] == 'arquivo'


def test_outra_configuracao_usa_outro_arquivo_e_apaga_o_antigo(tmp_path):
    pasta = tmp_path / 'modelo'
    pv.carregar_ou_treinar(pasta, 6, 4)
    antigo = list(pasta.glob('modelo_previsao_*.pkl'))
    assert pv.impressao_digital(6, 4) != pv.impressao_digital(5, 4)
    treinado, origem, aviso = pv.carregar_ou_treinar(pasta, 5, 4)
    assert origem == 'treino' and treinado['pessoas_treino'] == 5
    novos = list(pasta.glob('modelo_previsao_*.pkl'))
    assert len(novos) == 1 and novos != antigo


def test_impressao_digital_muda_quando_o_gerador_muda(monkeypatch, tmp_path):
    # Uma cópia idêntica do gerador (mesmo nome) dá a mesma impressão digital; mudar uma linha muda.
    copia = tmp_path / pv.ARQUIVO_GERADOR.name
    copia.write_bytes(pv.ARQUIVO_GERADOR.read_bytes())
    original = pv.impressao_digital(6, 4)
    monkeypatch.setattr(pv, 'ARQUIVO_GERADOR', copia)
    assert pv.impressao_digital(6, 4) == original
    copia.write_bytes(copia.read_bytes() + b'\n# mudou\n')
    assert pv.impressao_digital(6, 4) != original


def test_falha_ao_gravar_nao_impede_a_previsao(tmp_path):
    # Um arquivo comum no lugar da pasta: não dá para criar a pasta nem gravar.
    pasta = tmp_path / 'ocupado'
    pasta.write_text('arquivo, não pasta', encoding='utf-8')
    treinado, origem, aviso = pv.carregar_ou_treinar(pasta, 6, 4)
    assert origem == 'treino'
    assert pv.treinado_valido(treinado, 6, 4)
    assert 'não consegui guardá-lo' in aviso


# ---------------------------------------------------------------- casos-limite

def test_red_team_f4_at1_erro_qualquer_ao_gravar_nao_impede_a_previsao(tmp_path, monkeypatch):
    import pickle
    def quebra(*args, **kwargs):
        raise pickle.PicklingError('falha simulada ao gravar')
    monkeypatch.setattr(pickle, 'dump', quebra)
    pasta = tmp_path / 'modelo'
    treinado, origem, aviso = pv.carregar_ou_treinar(pasta, 6, 4)
    assert origem == 'treino'
    assert pv.treinado_valido(treinado, 6, 4)
    assert aviso is not None and 'não consegui guardá-lo' in aviso
    assert list(pasta.glob('modelo_previsao_*.pkl')) == []
    assert list(pasta.glob('*.tmp')) == []


def test_red_team_f4_at2_falha_ao_apagar_modelo_antigo_nao_diz_que_nao_guardou(tmp_path):
    pasta = tmp_path / 'modelo'
    pasta.mkdir()
    (pasta / 'modelo_previsao_antigo.pkl').mkdir()  # "modelo antigo" que não pode ser apagado
    treinado, origem, aviso = pv.carregar_ou_treinar(pasta, 6, 4)
    assert origem == 'treino'
    assert (pasta / f'modelo_previsao_{pv.impressao_digital(6, 4)}.pkl').is_file()
    assert aviso is None or 'não consegui guardá-lo' not in aviso
    assert pv.carregar_ou_treinar(pasta, 6, 4)[1] == 'arquivo'


def test_red_team_f4_at3_temporarios_antigos_nao_se_acumulam(tmp_path):
    pasta = tmp_path / 'modelo'
    pasta.mkdir()
    (pasta / 'modelo_previsao_000000000000000000000000.tmp').write_bytes(b'x' * 1000)
    pv.carregar_ou_treinar(pasta, 6, 4)
    assert sorted(p.suffix for p in pasta.iterdir()) == ['.pkl']


def test_red_team_f4_at4_impressao_digital_muda_com_a_versao_do_pandas(monkeypatch):
    original = pv.impressao_digital(6, 4)
    monkeypatch.setattr(pv.pd, '__version__', '0.0.0-teste')
    assert pv.impressao_digital(6, 4) != original


def test_red_team_f4_at5_arquivo_legivel_mas_incompleto_treina_de_novo(tmp_path):
    import pickle
    pasta = tmp_path / 'modelo'
    treinado, _, _ = pv.carregar_ou_treinar(pasta, 6, 4)
    caminho = pasta / f'modelo_previsao_{pv.impressao_digital(6, 4)}.pkl'
    caminho.write_bytes(pickle.dumps(dict(treinado, quantis={}, limites={})))
    novo, origem, aviso = pv.carregar_ou_treinar(pasta, 6, 4)
    assert origem == 'treino'
    assert novo['quantis'] == treinado['quantis'] and novo['limites'] == treinado['limites']
