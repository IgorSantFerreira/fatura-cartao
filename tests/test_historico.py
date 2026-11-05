import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import fatura as ft
import historico as hist


# Fatura de exemplo 100% fictícia (tests/exemplo.py): nenhum dado real nos testes.
from exemplo import CONTEUDO_EXEMPLO
NOV = date(2026, 11, 25)
FECHA_NOV = date(2026, 11, 18)


def csv(*linhas):
    return ('date,title,amount\n' + ''.join(linha + '\n' for linha in linhas)).encode('utf-8')


OUTUBRO = csv(
      '2026-09-20,Restaurante Bom Prato,"38,00"'
    , '2026-09-25,Dl*Deezer Premium,"22,90"'
    , '2026-09-26,Conectanet,"39,90"'
    , '2026-10-01,Auto Posto Primavera,"200,00"'
)


@pytest.fixture
def pasta(tmp_path):
    return str(tmp_path / 'historico')


# ---------------------------------------------------------------- guardar

def test_guarda_nova_e_nao_duplica(pasta):
    conteudo = CONTEUDO_EXEMPLO
    situacao, mensagem = hist.guardar(pasta, conteudo, 'Nubank_2026-11-25.csv', NOV, FECHA_NOV, date(2026, 11, 4))
    assert situacao == hist.NOVA
    salvo = json.loads(Path(pasta, '2026-11-25.json').read_text(encoding='utf-8'))
    assert salvo['vencimento'] == '2026-11-25'
    assert salvo['fechamento'] == '2026-11-18'
    assert salvo['salvo_em'] == '2026-11-04'
    assert salvo['arquivo'] == 'Nubank_2026-11-25.csv'
    assert hist.guardar(pasta, conteudo, 'outro_nome.csv', NOV, FECHA_NOV, date(2026, 11, 5))[0] == hist.IGUAL
    entradas, erros = hist.carregar_historico(pasta)
    assert erros == []
    assert len(entradas) == 1
    assert len(entradas[0]['df']) == 53
    assert entradas[0]['completa'] is False
    assert entradas[0]['salvo_em'] == date(2026, 11, 4)


def test_exportacao_mais_nova_substitui_e_mais_velha_nao(pasta):
    velha = csv('2026-10-20,Restaurante A,"10,00"')
    nova = csv('2026-10-20,Restaurante A,"10,00"', '2026-11-10,Restaurante B,"20,00"')
    assert hist.guardar(pasta, velha, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 4))[0] == hist.NOVA
    assert hist.guardar(pasta, nova, 'b.csv', NOV, FECHA_NOV, date(2026, 11, 20))[0] == hist.SUBSTITUIDA
    entrada = hist.carregar_historico(pasta)[0][0]
    assert len(entrada['df']) == 2
    assert entrada['salvo_em'] == date(2026, 11, 20)
    assert entrada['completa'] is True
    # Reabrir o arquivo antigo depois não apaga os lançamentos a mais.
    assert hist.guardar(pasta, velha, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 21))[0] == hist.MANTIDA
    entrada = hist.carregar_historico(pasta)[0][0]
    assert len(entrada['df']) == 2
    assert entrada['salvo_em'] == date(2026, 11, 20)


def test_lancamento_alterado_substitui(pasta):
    hist.guardar(pasta, csv('2026-10-20,Restaurante A,"10,00"'), 'a.csv', NOV, FECHA_NOV, date(2026, 11, 4))
    situacao = hist.guardar(pasta, csv('2026-10-20,Restaurante A,"12,00"'), 'a.csv', NOV, FECHA_NOV, date(2026, 11, 5))[0]
    assert situacao == hist.SUBSTITUIDA
    assert int(hist.carregar_historico(pasta)[0][0]['df']['centavos'].iloc[0]) == 1200


def test_lancamentos_repetidos_contam(pasta):
    # Duas pizzas iguais no mesmo dia não são "o mesmo lançamento" de uma exportação com uma só.
    uma = csv('2026-10-24,Ifd*Pizza,"47,35"')
    duas = csv('2026-10-24,Ifd*Pizza,"47,35"', '2026-10-24,Ifd*Pizza,"47,35"')
    hist.guardar(pasta, duas, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 4))
    assert hist.guardar(pasta, uma, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 5))[0] == hist.MANTIDA
    assert len(hist.carregar_historico(pasta)[0][0]['df']) == 2


def test_fechamento_corrigido_atualiza_sem_mudar_data_guardada(pasta):
    conteudo = csv('2026-10-20,Restaurante A,"10,00"')
    hist.guardar(pasta, conteudo, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 4))
    situacao = hist.guardar(pasta, conteudo, 'a.csv', NOV, date(2026, 11, 3), date(2026, 11, 6))[0]
    assert situacao == hist.ATUALIZADA
    entrada = hist.carregar_historico(pasta)[0][0]
    assert entrada['fechamento'] == date(2026, 11, 3)
    assert entrada['salvo_em'] == date(2026, 11, 4)
    assert entrada['completa'] is True


def test_mesmo_conteudo_com_outro_vencimento_nao_e_guardado(pasta):
    hist.guardar(pasta, OUTUBRO, 'a.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    situacao, mensagem = hist.guardar(pasta, OUTUBRO, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 4))
    assert situacao == hist.DUPLICADA
    assert '25/10/2026' in mensagem
    assert not Path(pasta, '2026-11-25.json').exists()


def test_arquivo_corrompido_nao_e_sobrescrito_nem_derruba_os_outros(pasta):
    hist.guardar(pasta, OUTUBRO, 'a.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    corrompido = Path(pasta, '2026-11-25.json')
    corrompido.write_text('{quebrado', encoding='utf-8')
    Path(pasta, 'anotacoes.txt').write_text('não é fatura', encoding='utf-8')
    situacao = hist.guardar(pasta, CONTEUDO_EXEMPLO, 'n.csv', NOV, FECHA_NOV, date(2026, 11, 4))[0]
    assert situacao == hist.ERRO
    assert corrompido.read_text(encoding='utf-8') == '{quebrado'
    entradas, erros = hist.carregar_historico(pasta)
    assert [entrada['vencimento'] for entrada in entradas] == [date(2026, 10, 25)]
    assert [erro['vencimento'] for erro in erros] == ['2026-11-25']
    assert hist.remover(pasta, NOV) is True
    assert hist.guardar(pasta, CONTEUDO_EXEMPLO, 'n.csv', NOV, FECHA_NOV, date(2026, 11, 4))[0] == hist.NOVA


def test_vencimento_do_conteudo_tem_que_bater_com_o_nome(pasta):
    hist.guardar(pasta, OUTUBRO, 'a.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    Path(pasta, '2026-10-25.json').rename(Path(pasta, '2026-12-25.json'))
    entradas, erros = hist.carregar_historico(pasta)
    assert entradas == []
    assert erros[0]['vencimento'] == '2026-12-25'


def test_csv_invalido_nao_e_guardado(pasta):
    with pytest.raises(ValueError):
        hist.guardar(pasta, b'date,title,amount\n2026-10-28,Compra,1.385\n', 'a.csv', NOV, FECHA_NOV, date(2026, 11, 4))
    assert hist.carregar_historico(pasta) == ([], [])


# ---------------------------------------------------------------- comparações

def historico_com_duas(pasta):
    hist.guardar(pasta, OUTUBRO, 'Nubank_2026-10-25.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    hist.guardar(pasta, CONTEUDO_EXEMPLO, 'Nubank_2026-11-25.csv', NOV, FECHA_NOV, date(2026, 11, 4))
    return hist.montar(hist.carregar_historico(pasta)[0], {})


def test_media_usa_so_completas_anteriores(pasta):
    montadas = historico_com_duas(pasta)
    medias, anteriores = hist.media_anterior(montadas, NOV)
    assert [item['vencimento'] for item in anteriores] == [date(2026, 10, 25)]
    assert medias[ft.COMIDA] == 3800
    assert medias[ft.TRANSPORTE] == 20000
    assert medias['Total'] == 3800 + 2290 + 3990 + 20000
    # A fatura de novembro é parcial: não entra nem como anterior de uma fatura futura.
    medias_dez, anteriores_dez = hist.media_anterior(montadas, date(2026, 12, 25))
    assert [item['vencimento'] for item in anteriores_dez] == [date(2026, 10, 25)]


def test_media_arredonda_e_conta_zero_onde_nao_houve_gasto(pasta):
    hist.guardar(pasta, csv('2026-08-20,Restaurante A,"10,01"'), 'a.csv', date(2026, 9, 25), date(2026, 9, 18), date(2026, 11, 4))
    hist.guardar(pasta, csv('2026-09-20,Auto Posto X,"10,00"', '2026-09-21,Restaurante A,"10,00"'), 'b.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    montadas = hist.montar(hist.carregar_historico(pasta)[0], {})
    medias, anteriores = hist.media_anterior(montadas, NOV)
    assert len(anteriores) == 2
    assert medias[ft.COMIDA] == 1001
    assert medias[ft.TRANSPORTE] == 500
    comparacao = hist.comparar_com_media({ft.COMIDA: 1500, 'Total': 1500}, medias)
    linhas = {linha.categoria: linha for linha in comparacao.itertuples(index=False)}
    assert linhas[ft.TRANSPORTE].atual == 0
    assert linhas[ft.TRANSPORTE].diferenca == -500
    assert linhas[ft.COMIDA].diferenca == 499


def test_historico_usa_as_regras_atuais_do_usuario(pasta):
    hist.guardar(pasta, OUTUBRO, 'a.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    entradas = hist.carregar_historico(pasta)[0]
    sem = hist.media_anterior(hist.montar(entradas, {}), NOV)[0]
    com = hist.media_anterior(hist.montar(entradas, {'conectanet': ft.CASA}), NOV)[0]
    assert sem[ft.A_CLASSIFICAR] == 3990
    assert ft.A_CLASSIFICAR not in com
    assert com[ft.CASA] == 3990


def test_tabela_mensal(pasta):
    tabela = hist.tabela_mensal(historico_com_duas(pasta))
    total_nov = tabela[(tabela['fatura'] == 'nov/2026') & (tabela['categoria'] == 'Total')]
    assert int(total_nov['centavos'].iloc[0]) == 250814
    assert bool(total_nov['completa'].iloc[0]) is False
    comida_out = tabela[(tabela['fatura'] == 'out/2026') & (tabela['categoria'] == ft.COMIDA)]
    assert int(comida_out['centavos'].iloc[0]) == 3800


def test_rotulo_com_dois_vencimentos_no_mesmo_mes(pasta):
    hist.guardar(pasta, csv('2026-10-01,Restaurante A,"10,00"'), 'a.csv', date(2026, 11, 5), date(2026, 10, 29), date(2026, 11, 30))
    hist.guardar(pasta, csv('2026-10-20,Restaurante B,"10,00"'), 'b.csv', NOV, FECHA_NOV, date(2026, 11, 30))
    rotulos = [item['rotulo'] for item in hist.montar(hist.carregar_historico(pasta)[0], {})]
    assert rotulos == ['05/11/2026', '25/11/2026']


# ---------------------------------------------------------------- recorrentes

def montada(vencimento, *linhas):
    return {'vencimento': vencimento, 'rotulo': '', 'completa': True, 'fatura': ft.montar_fatura(ft.ler_csv(csv(*linhas)), {})}


def test_recorrentes_nas_duas_faturas(pasta):
    fixos = hist.recorrentes(historico_com_duas(pasta))
    por_nome = {(linha.estabelecimento, linha.centavos): linha for linha in fixos.itertuples(index=False)}
    # Conectanet (39,90) e Deezer (22,90) aparecem uma vez em outubro e uma em novembro.
    assert por_nome[('Conectanet', 3990)].como == 'repete todo mês'
    assert por_nome[('Conectanet', 3990)].faturas == 2
    assert por_nome[('Dl*Deezer Premium', 2290)].como == 'repete todo mês; assinatura conhecida'
    # Assinaturas só de novembro entram pelo nome.
    assert por_nome[('Openai *Chatgpt Subscr', 10830)].como == 'assinatura conhecida'
    assert por_nome[('Icloud *Storage', 490)].faturas == 1
    assert ('Icloud *Storage', 1690) in por_nome
    # Restaurante Bom Prato de outubro (38,00) aparece em novembro com 38,00 uma vez e 27,00 outra.
    assert ('Restaurante Bom Prato', 3800) in por_nome
    # O posto mudou de valor: não é fixo.
    assert all(linha.estabelecimento != 'Auto Posto Primavera' for linha in fixos.itertuples(index=False))
    assert all(linha.ativa for linha in fixos.itertuples(index=False))
    assert list(fixos['por_ano']) == [valor * 12 for valor in fixos['centavos']]


def test_repetido_na_mesma_fatura_nao_e_fixo():
    fixos = hist.recorrentes([
          montada(date(2026, 10, 25), '2026-09-20,Emv Metrô*1556448,"5,40"', '2026-09-21,Emv Metrô*1556449,"5,40"')
        , montada(date(2026, 11, 25), '2026-10-20,Emv Metrô*1556450,"5,40"')
    ])
    assert len(fixos) == 0


def test_fixo_precisa_ser_seguido_e_parcelas_nao_entram():
    fixos = hist.recorrentes([
          montada(date(2026, 9, 25), '2026-08-20,Academia X,"99,00"', '2026-08-20,Loja - Parcela 1/3,"50,00"')
        , montada(date(2026, 10, 25), '2026-09-20,Restaurante A,"1,00"', '2026-09-20,Loja - Parcela 2/3,"50,00"')
        , montada(date(2026, 11, 25), '2026-10-20,Academia X,"99,00"', '2026-10-20,Loja - Parcela 3/3,"50,00"', '2026-10-21,Netflix,"20,00"', '2026-09-21,Netflix,"20,00"')
    ])
    nomes = list(fixos['estabelecimento'])
    # Academia: falhou em outubro (não é seguida); mas é Assinaturas pelo nome na mais recente.
    academia = fixos[fixos['estabelecimento'] == 'Academia X'].iloc[0]
    assert academia['como'] == 'assinatura conhecida'
    assert 'Loja' not in nomes
    # Netflix duas vezes na mesma fatura: entra pelo nome, uma linha só.
    assert nomes.count('Netflix') == 1


def test_fixo_que_sumiu_nao_conta_no_total():
    fixos = hist.recorrentes([
          montada(date(2026, 9, 25), '2026-08-20,Fibra,"36,90"')
        , montada(date(2026, 10, 25), '2026-09-20,Fibra,"36,90"')
        , montada(date(2026, 11, 25), '2026-10-20,Restaurante A,"1,00"')
    ])
    assert len(fixos) == 1
    assert bool(fixos['ativa'].iloc[0]) is False


def test_fatura_parcial_no_fim_nao_desativa_fixos_nem_assinaturas():
    parcial = montada(date(2026, 12, 25), '2026-11-19,Restaurante Y,"30,00"')
    parcial['completa'] = False
    fixos = hist.recorrentes([
          montada(date(2026, 10, 25), '2026-09-20,Fibra,"36,90"')
        , montada(date(2026, 11, 25), '2026-10-20,Fibra,"36,90"', '2026-10-21,Spotify,"21,90"')
        , parcial
    ])
    linhas = {linha.estabelecimento: linha for linha in fixos.itertuples(index=False)}
    assert linhas['Fibra'].ativa
    assert linhas['Spotify'].ativa
    assert linhas['Spotify'].como == 'assinatura conhecida'
    assert int(fixos.loc[fixos['ativa'], 'centavos'].sum()) == 3690 + 2190


def test_exportacao_mais_antiga_com_lancamento_diferente_nao_substitui(pasta):
    nova = csv('2026-10-20,Restaurante A,"10,00"', '2026-11-10,Restaurante B,"20,00"')
    velha_alterada = csv('2026-10-20,Restaurante A,"12,00"')
    hist.guardar(pasta, nova, 'b.csv', NOV, FECHA_NOV, date(2026, 11, 20))
    situacao, mensagem = hist.guardar(pasta, velha_alterada, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 21))
    assert situacao == hist.CONFLITO
    assert '20/10/2026' in mensagem and '10/11/2026' in mensagem
    entrada = hist.carregar_historico(pasta)[0][0]
    assert len(entrada['df']) == 2
    assert entrada['salvo_em'] == date(2026, 11, 20)


def test_reabrir_igual_antes_do_fechamento_continua_parcial(pasta):
    conteudo = csv('2026-10-20,Restaurante A,"10,00"')
    hist.guardar(pasta, conteudo, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 4))
    assert hist.guardar(pasta, conteudo, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 17))[0] == hist.IGUAL
    situacao, mensagem = hist.guardar(pasta, conteudo, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 18))
    assert situacao == hist.ATUALIZADA
    assert 'agora marcada como completa' in mensagem
    entrada = hist.carregar_historico(pasta)[0][0]
    assert entrada['salvo_em'] == date(2026, 11, 18)
    assert entrada['completa'] is True
    assert hist.guardar(pasta, conteudo, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 30))[0] == hist.IGUAL


def test_csv_com_aspa_sem_fechar_vira_erro_de_leitura():
    with pytest.raises(ValueError, match='não é um CSV válido'):
        ft.ler_csv('date,title,amount\n2026-10-20,"' + 'x' * 200000 + '\n')


# ---------------------------------------------------------------- casos-limite

def test_reexportacao_igual_depois_do_fechamento_completa_a_parcial(pasta):
    conteudo = csv('2026-10-20,Restaurante A,"10,00"')
    assert hist.guardar(pasta, conteudo, 'a.csv', NOV, FECHA_NOV, date(2026, 11, 10))[0] == hist.NOVA
    assert hist.carregar_historico(pasta)[0][0]['completa'] is False
    # README: "Para atualizá-la, abra a exportação feita depois do fechamento."
    hist.guardar(pasta, conteudo, 'b.csv', NOV, FECHA_NOV, date(2026, 11, 20))
    entrada = hist.carregar_historico(pasta)[0][0]
    assert entrada['completa'] is True
    assert len(entrada['df']) == 1


def test_historico_com_csv_que_quebra_o_leitor_nao_derruba(pasta):
    Path(pasta).mkdir(parents=True)
    texto = 'date,title,amount\n2026-10-20,"' + 'x' * 200000 + '\n'
    Path(pasta, '2026-10-25.json').write_text(json.dumps({'vencimento': '2026-10-25', 'fechamento': '2026-10-18', 'salvo_em': '2026-11-04', 'csv': texto}), encoding='utf-8')
    entradas, erros = hist.carregar_historico(pasta)
    assert entradas == []
    assert [erro['vencimento'] for erro in erros] == ['2026-10-25']


# ---------------------------------------------------------------- casos-limite

def test_assinatura_com_valor_que_muda_conta_uma_vez_so():
    aberta = montada(date(2026, 12, 25), '2026-11-20,Openai *Chatgpt Subscr,"110,20"')
    aberta['completa'] = False
    fixos = hist.recorrentes([
          montada(date(2026, 10, 25), '2026-09-20,Openai *Chatgpt Subscr,"104,00"', '2026-09-21,Icloud *Storage,"4,90"', '2026-09-22,Icloud *Storage,"16,90"')
        , montada(date(2026, 11, 25), '2026-10-20,Openai *Chatgpt Subscr,"108,30"', '2026-10-21,Icloud *Storage,"4,90"', '2026-10-22,Icloud *Storage,"16,90"')
        , aberta
    ])
    ativas = fixos[fixos['ativa']]
    # Assinatura em dólar só com o valor mais recente; as duas do iCloud na mesma fatura continuam separadas.
    assert sorted(int(valor) for valor in ativas['centavos']) == [490, 1690, 11020]
    assert int(ativas['centavos'].sum()) == 490 + 1690 + 11020


def recorrentes_com_aberta(*faturas, aberta):
    parcial = montada(date(2026, 12, 25), *aberta)
    parcial['completa'] = False
    return hist.recorrentes(list(faturas) + [parcial])


def test_assinatura_ainda_nao_cobrada_na_aberta_continua_ao_lado_de_outra_do_mesmo_lugar():
    fixos = recorrentes_com_aberta(
          montada(date(2026, 11, 25), '2026-10-21,Icloud *Storage,"4,90"', '2026-10-22,Icloud *Storage,"16,90"')
        , aberta=['2026-11-22,Icloud *Storage,"16,90"']
    )
    assert sorted(int(valor) for valor in fixos.loc[fixos['ativa'], 'centavos']) == [490, 1690]


def test_reajuste_na_aberta_substitui_o_valor_mais_proximo():
    fixos = recorrentes_com_aberta(
          montada(date(2026, 11, 25), '2026-10-21,Icloud *Storage,"4,90"', '2026-10-22,Icloud *Storage,"16,90"')
        , aberta=['2026-11-22,Icloud *Storage,"18,90"']
    )
    assert sorted(int(valor) for valor in fixos.loc[fixos['ativa'], 'centavos']) == [490, 1890]


def test_reajuste_entre_faturas_completas_conta_so_o_novo():
    fixos = hist.recorrentes([
          montada(date(2026, 9, 25), '2026-08-20,Spotify,"21,90"')
        , montada(date(2026, 10, 25), '2026-09-20,Spotify,"21,90"')
        , montada(date(2026, 11, 25), '2026-10-20,Spotify,"24,90"')
    ])
    assert sorted(int(valor) for valor in fixos.loc[fixos['ativa'], 'centavos']) == [2490]
    antigo = fixos[fixos['centavos'] == 2190].iloc[0]
    assert antigo['como'] == 'repete todo mês'
    assert bool(antigo['ativa']) is False


def test_recorrentes_sem_historico_usa_a_fatura_atual():
    fatura = ft.montar_fatura(ft.ler_csv(CONTEUDO_EXEMPLO), {})
    fixos = hist.recorrentes([{'vencimento': None, 'rotulo': '', 'completa': False, 'fatura': fatura}])
    assert int(fixos['centavos'].sum()) == 27580
    assert int(fixos['por_ano'].sum()) == 330960
    assert set(fixos['como']) == {'assinatura conhecida'}


# ---------------------------------------------------------------- fase 1: m-c3 e fora do padrão

def test_fixo_que_nao_e_assinatura_e_muda_de_valor_na_aberta_continua_no_total():
    # Caso: Fibra 36,90 -> 41,90 na fatura aberta.
    fixos = recorrentes_com_aberta(
          montada(date(2026, 10, 25), '2026-09-20,Fibra,"36,90"')
        , montada(date(2026, 11, 25), '2026-10-20,Fibra,"36,90"')
        , aberta=['2026-11-20,Fibra,"41,90"']
    )
    linhas = {int(linha.centavos): linha for linha in fixos.itertuples(index=False)}
    assert bool(linhas[3690].ativa) is False
    assert bool(linhas[4190].ativa) is True
    assert linhas[4190].como == 'valor mudou (a confirmar)'
    assert int(fixos.loc[fixos['ativa'], 'centavos'].sum()) == 4190


def test_valor_mudou_nao_duplica_quando_o_novo_ja_tem_linha():
    # T7 continua igual: assinatura 108,30 -> 110,20 já entra como assinatura conhecida, sem linha extra.
    fixos = recorrentes_com_aberta(
          montada(date(2026, 11, 25), '2026-10-20,Openai *Chatgpt Subscr,"108,30"')
        , aberta=['2026-11-20,Openai *Chatgpt Subscr,"110,20"']
    )
    assert 'valor mudou (a confirmar)' not in set(fixos['como'])
    assert sorted(int(valor) for valor in fixos.loc[fixos['ativa'], 'centavos']) == [11020]


# ---------------------------------------------------------------- casos-limite

def test_valor_novo_repetido_na_aberta_nao_vira_fixo():
    # F1: compra repetida na mesma fatura não é cobrança recorrente.
    fixos = recorrentes_com_aberta(
          montada(date(2026, 10, 25), '2026-09-20,Padaria Pao Bom,"15,00"')
        , montada(date(2026, 11, 25), '2026-10-20,Padaria Pao Bom,"15,00"')
        , aberta=['2026-11-20,Padaria Pao Bom,"12,00"', '2026-11-21,Padaria Pao Bom,"12,00"', '2026-11-22,Padaria Pao Bom,"12,00"']
    )
    assert 1200 not in set(int(valor) for valor in fixos['centavos'])


def tres_meses(pasta):
    meses = [
          (date(2026, 9, 25), 'date,title,amount\n2026-08-20,Restaurante A,"100,00"\n2026-08-21,Auto Posto X,"200,00"\n')
        , (date(2026, 10, 25), 'date,title,amount\n2026-09-20,Restaurante A,"150,00"\n2026-09-21,Auto Posto X,"100,00"\n2026-09-22,Cinemark,"30,00"\n')
    ]
    for vencimento, texto in meses:
        hist.guardar(pasta, texto.encode('utf-8'), 'a.csv', vencimento, vencimento - timedelta(days=7), date(2026, 11, 20))
    return hist.montar(hist.carregar_historico(pasta)[0], {})


def test_fora_do_padrao_acima_do_maximo_e_abaixo_do_minimo(pasta):
    montadas = tres_meses(pasta)
    atuais = {ft.COMIDA: 15001, ft.TRANSPORTE: 9999, 'Total': 25000, ft.A_CLASSIFICAR: 99999}
    fora, quantas, comparadas = hist.fora_do_padrao(montadas, NOV, atuais)
    assert quantas == 2
    # Comida, Transporte, Lazer e Total; "A classificar" não é consumo e fica de fora.
    assert comparadas == 4
    assert ft.A_CLASSIFICAR not in set(fora['categoria'])
    linhas = {linha.categoria: linha for linha in fora.itertuples(index=False)}
    assert linhas[ft.COMIDA].direcao == hist.ACIMA
    assert linhas[ft.COMIDA].maximo == 15000
    assert linhas[ft.TRANSPORTE].direcao == hist.ABAIXO
    assert linhas[ft.TRANSPORTE].minimo == 10000
    # Lazer: 0 nesta fatura, mas houve mês com 0 (setembro): está dentro do intervalo [0, 30,00].
    assert ft.LAZER not in linhas
    # Total: setembro 300,00 e outubro 280,00; 250,00 fica abaixo do menor.
    assert linhas['Total'].direcao == hist.ABAIXO
    assert linhas['Total'].minimo == 28000
    # No limite exato não é "fora".
    fora_limite, _, _ = hist.fora_do_padrao(montadas, NOV, {ft.COMIDA: 15000, ft.TRANSPORTE: 10000, 'Total': 28000})
    assert len(fora_limite) == 0


def test_fora_do_padrao_precisa_de_duas_completas_anteriores(pasta):
    hist.guardar(pasta, 'date,title,amount\n2026-09-20,Restaurante A,"100,00"\n'.encode('utf-8'), 'a.csv', date(2026, 10, 25), date(2026, 10, 18), date(2026, 11, 4))
    hist.guardar(pasta, 'date,title,amount\n2026-08-20,Restaurante B,"100,00"\n'.encode('utf-8'), 'b.csv', date(2026, 9, 25), date(2026, 9, 18), date(2026, 9, 10))
    montadas = hist.montar(hist.carregar_historico(pasta)[0], {})
    # Setembro foi guardada antes do fechamento (parcial): só outubro conta.
    fora, quantas, comparadas = hist.fora_do_padrao(montadas, NOV, {ft.COMIDA: 1})
    assert fora is None
    assert comparadas == 0
    assert quantas == 1
