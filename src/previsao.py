# Previsão do gasto no fechamento do ciclo por aprendizado de máquina (fase 3). As mesmas funções servem ao
# notebook do experimento (notebooks/previsao_gastos.ipynb) e ao app (aba "Até o fechamento").
#
# Ideia: o modelo é treinado com MUITAS pessoas fictícias (ferramentas/gerar_faturas_sinteticas.py --pessoas),
# não com as faturas de quem usa o app. Na hora de prever, ele olha o ciclo atual da pessoa até a data da
# previsão e as poucas faturas completas anteriores que ela tiver. Assim não é preciso ter dezenas de faturas.
#
# Um "retrato" é o ciclo de uma pessoa visto num dia j (1 = primeiro dia de compras). Atributos do retrato,
# calculados SÓ com o que se sabia naquele dia (lançamentos com data <= dia j e faturas completas anteriores):
#   fracao_decorrida: j / dias de compra do ciclo;
#   atual_n: o gasto até o dia j;
#   linear_a_mais_n: o "a mais" da projeção linear do app (ritmo do dia a dia x dias que faltam);
#   tem_historico e anteriores: se há faturas anteriores e quantas (até ANTERIORES_MAXIMO);
#   hist_restante_n: quanto, em média, a pessoa gastou nas faturas anteriores DEPOIS do mesmo dia j;
#   hist_fracao_feita: que fração do total das anteriores já estava gasta no mesmo dia j;
#   hist_total_n: o total médio das anteriores.
# Os valores ("_n") são divididos pela escala da pessoa (o total médio das anteriores; sem anteriores, a
# projeção linear), para pessoas que gastam R$ 1.000 e R$ 5.000 ficarem comparáveis. O alvo também:
#   alvo_n = (gasto no fechamento - gasto até o dia j) / escala.

import csv
import importlib.util
import io
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import fatura as ft


REGRESSAO_LINEAR = 'Regressão Linear'
FLORESTA = 'Random Forest Regressor'
PROJECAO_LINEAR = 'Projeção linear (ritmo atual)'

ATRIBUTOS = [
      'fracao_decorrida'
    , 'atual_n'
    , 'linear_a_mais_n'
    , 'tem_historico'
    , 'anteriores'
    , 'hist_restante_n'
    , 'hist_restante_mediana_n'
    , 'hist_fracao_feita'
    , 'hist_total_n'
    , 'desvio_n'
]

# Piso da escala (R$ 100): só para não dividir por quase zero no começo de um ciclo sem gastos.
ESCALA_MINIMA = 10000
# Faturas anteriores usadas: as mais recentes, até 12 (o máximo que existe no treino, com 13 meses por pessoa).
ANTERIORES_MAXIMO = 12

# Faixas do ciclo e do histórico em que o erro e o intervalo são medidos.
INICIO = 'início do ciclo'
MEIO = 'meio do ciclo'
FIM = 'fim do ciclo'
FAIXAS_CICLO = [INICIO, MEIO, FIM]
FAIXAS_HISTORICO = ['0', '1', '2', '3+']

# Intervalo de incerteza: entre os quantis 10% e 90% dos erros fora da amostra (cobre 80% das vezes, se o
# comportamento das pessoas for parecido com o das pessoas de calibração).
QUANTIL_BAIXO = 0.10
QUANTIL_ALTO = 0.90


def faixa_do_ciclo(fracao):
    if fracao <= 1 / 3:
        return INICIO
    if fracao <= 2 / 3:
        return MEIO
    return FIM


def faixa_do_historico(anteriores):
    if anteriores >= 3:
        return '3+'
    return str(int(anteriores))


# ---------------------------------------------------------------- curvas diárias de uma fatura

def curva(fatura, inicio, ultimo_dia):
    # Para cada dia j do ciclo (posição j - 1 nas listas): o gasto até aquele dia (mesma conta de ft.projecao:
    # tudo que conta no gasto com data <= dia, inclusive lançamentos datados antes do início, como encargos) e o
    # gasto "no ritmo" desde o início (dia a dia, sem parcelas, assinaturas, encargos e estornos).
    if ultimo_dia < inicio:
        raise ValueError('O último dia de compras é anterior ao início do ciclo.')
    dias_total = (ultimo_dia - inicio).days + 1
    datas = fatura['data'].dt.date
    deslocamentos = np.array([(dia - inicio).days for dia in datas], dtype=int)
    centavos = fatura['centavos'].astype('int64').to_numpy()
    conta = fatura['conta_no_gasto'].to_numpy(dtype=bool)
    ritmo = ft.no_ritmo(fatura).to_numpy(dtype=bool)

    antes = int(centavos[conta & (deslocamentos < 0)].sum())
    por_dia = np.zeros(dias_total, dtype='int64')
    por_dia_ritmo = np.zeros(dias_total, dtype='int64')
    dentro = (deslocamentos >= 0) & (deslocamentos < dias_total)
    np.add.at(por_dia, deslocamentos[conta & dentro], centavos[conta & dentro])
    np.add.at(por_dia_ritmo, deslocamentos[ritmo & dentro], centavos[ritmo & dentro])
    return {
          'inicio': inicio
        , 'dias_total': dias_total
        , 'gasto_ate': antes + np.cumsum(por_dia)
        , 'ritmo_ate': np.cumsum(por_dia_ritmo)
        , 'total': ft.totais(fatura)['gasto']
    }


def curva_da_montada(item, fechamento=None):
    # item: uma fatura de hist.montar (vencimento, fatura e, se houver, fechamento).
    datas = ft.ciclo(item['vencimento'], item.get('fechamento', fechamento))
    return curva(item['fatura'], datas['inicio'], datas['ultimo_dia'])


def linear_a_mais(curva_atual, j):
    # O "a mais" de ft.projecao no dia j: ritmo do dia a dia até j, vezes os dias que faltam, arredondado igual.
    dias_total = curva_atual['dias_total']
    return ft.dividir_arredondando(int(curva_atual['ritmo_ate'][j - 1]) * (dias_total - j), j)


# ---------------------------------------------------------------- atributos de um retrato

def atributos(curva_atual, j, anteriores):
    # curva_atual: a curva do ciclo atual; j: dias decorridos (1 a dias_total); anteriores: curvas de faturas
    # COMPLETAS que vencem antes da atual, da mais antiga para a mais recente. Só usa o que se sabia no dia j.
    dias_total = curva_atual['dias_total']
    if not 1 <= j <= dias_total:
        raise ValueError('O dia da previsão precisa estar dentro do ciclo.')
    anteriores = list(anteriores)[-ANTERIORES_MAXIMO:]
    atual = int(curva_atual['gasto_ate'][j - 1])
    a_mais_linear = linear_a_mais(curva_atual, j)
    fracao = j / dias_total
    quantas = len(anteriores)
    if quantas > 0:
        totais = []
        restantes = []
        feitas = []
        ate_alis = []
        for anterior in anteriores:
            dia = min(j, anterior['dias_total'])
            ate_ali = int(anterior['gasto_ate'][dia - 1])
            totais.append(anterior['total'])
            restantes.append(anterior['total'] - ate_ali)
            ate_alis.append(ate_ali)
            feitas.append(ate_ali / anterior['total'] if anterior['total'] > 0 else fracao)
        escala = max(float(np.mean(totais)), ESCALA_MINIMA)
        hist_restante = float(np.mean(restantes))
        hist_restante_mediana = float(np.median(restantes))
        hist_feita = float(np.mean(feitas))
        hist_total = float(np.mean(totais))
        desvio = atual - float(np.mean(ate_alis))
    else:
        # Sem histórico: escala pela própria projeção linear; os atributos de histórico ficam neutros.
        escala = float(max(atual + a_mais_linear, ESCALA_MINIMA))
        hist_restante = 0.0
        hist_restante_mediana = 0.0
        hist_feita = fracao
        hist_total = 0.0
        desvio = 0.0
    return {
          'fracao_decorrida': fracao
        , 'atual_n': atual / escala
        , 'linear_a_mais_n': a_mais_linear / escala
        , 'tem_historico': 1 if quantas > 0 else 0
        , 'anteriores': quantas
        , 'hist_restante_n': hist_restante / escala
        , 'hist_restante_mediana_n': hist_restante_mediana / escala
        , 'hist_fracao_feita': hist_feita
        , 'hist_total_n': hist_total / escala
        , 'desvio_n': desvio / escala
        , 'escala': escala
        , 'atual': atual
        , 'linear_a_mais': a_mais_linear
        , 'hist_restante': hist_restante
        , 'j': j
        , 'dias_total': dias_total
    }


def retratos(curvas, pessoa):
    # Todos os retratos de uma pessoa: cada ciclo, em cada dia com pelo menos um dia de compra pela frente,
    # com as faturas anteriores dela como histórico. curvas: da mais antiga para a mais recente.
    linhas = []
    for ciclo_numero, curva_atual in enumerate(curvas):
        anteriores = curvas[:ciclo_numero]
        for j in range(1, curva_atual['dias_total']):
            linha = atributos(curva_atual, j, anteriores)
            linha['pessoa'] = pessoa
            linha['ciclo'] = ciclo_numero
            linha['total'] = curva_atual['total']
            linha['alvo_n'] = (curva_atual['total'] - linha['atual']) / linha['escala']
            linhas.append(linha)
    return linhas


# ---------------------------------------------------------------- população fictícia

ARQUIVO_GERADOR = Path(__file__).resolve().parent.parent / 'ferramentas' / 'gerar_faturas_sinteticas.py'


def carregar_gerador():
    especificacao = importlib.util.spec_from_file_location('gerar_faturas_sinteticas', ARQUIVO_GERADOR)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


def fatura_das_linhas(gerador, linhas):
    # As linhas do gerador passam pelo mesmo caminho de uma fatura de verdade: CSV do Nubank -> ler -> montar
    # (com as regras do app, sem regras do usuário).
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator='\n')
    escritor.writerow(['date', 'title', 'amount'])
    for dia, titulo, centavos, categoria, comportamento in linhas:
        escritor.writerow([dia.isoformat(), titulo, gerador.reais(centavos)])
    return ft.montar_fatura(ft.ler_csv(saida.getvalue()), {})


def curvas_da_populacao(pessoas, semente, meses=13, com_salario=True, primeiro_vencimento=date(2025, 10, 25)):
    # {pessoa: [curvas das faturas, da mais antiga para a mais recente]}
    gerador = carregar_gerador()
    populacao = gerador.gerar_populacao(pessoas, meses, semente, primeiro_vencimento, com_salario)
    resultado = {}
    for pessoa in populacao:
        curvas = []
        for vencimento, linhas in pessoa['faturas']:
            datas = ft.ciclo(vencimento)
            curvas.append(curva(fatura_das_linhas(gerador, linhas), datas['inicio'], datas['ultimo_dia']))
        resultado[pessoa['pessoa']] = curvas
    return resultado


def retratos_com_historico_curto(curvas, pessoa, quantidades=(1, 2)):
    # Simula quem só tem 1 (ou 2) faturas anteriores em TODOS os ciclos da pessoa, cortando o histórico: as
    # anteriores são só as 1 (ou 2) imediatamente antes. Na população, cada pessoa tem um único ciclo com
    # exatamente 1 anterior; com o corte, cada ciclo vira também um caso de "pessoa nova no app".
    # Os casos em que o corte não muda nada (o ciclo já tinha exatamente essa quantidade) ficam de fora.
    linhas = []
    for ciclo_numero, curva_atual in enumerate(curvas):
        for quantas in quantidades:
            if ciclo_numero <= quantas:
                continue
            anteriores = curvas[ciclo_numero - quantas:ciclo_numero]
            for j in range(1, curva_atual['dias_total']):
                linha = atributos(curva_atual, j, anteriores)
                linha['pessoa'] = pessoa
                linha['ciclo'] = f'{ciclo_numero} com {quantas} anterior(es)'
                linha['total'] = curva_atual['total']
                linha['alvo_n'] = (curva_atual['total'] - linha['atual']) / linha['escala']
                linhas.append(linha)
    return linhas


def tabela_de_retratos(curvas_por_pessoa, historico_curto=False):
    # historico_curto: inclui também os retratos com o histórico cortado (retratos_com_historico_curto).
    linhas = []
    for pessoa, curvas in curvas_por_pessoa.items():
        linhas.extend(retratos(curvas, pessoa))
        if historico_curto:
            linhas.extend(retratos_com_historico_curto(curvas, pessoa))
    tabela = pd.DataFrame(linhas)
    tabela['faixa_ciclo'] = [faixa_do_ciclo(fracao) for fracao in tabela['fracao_decorrida']]
    tabela['faixa_historico'] = [faixa_do_historico(quantas) for quantas in tabela['anteriores']]
    tabela['linear_total'] = tabela['atual'] + tabela['linear_a_mais']
    return tabela


# ---------------------------------------------------------------- modelos

def montar_modelo(tipo, folhas=1):
    if tipo == REGRESSAO_LINEAR:
        return Pipeline([('escala', StandardScaler()), ('modelo', LinearRegression())])
    return RandomForestRegressor(n_estimators=200, min_samples_leaf=folhas, random_state=0, n_jobs=1)


def treinar(tabela, tipo, folhas=1):
    modelo = montar_modelo(tipo, folhas)
    modelo.fit(tabela[ATRIBUTOS], tabela['alvo_n'])
    return modelo


def prever_totais(modelo, tabela):
    # Gasto previsto no fechamento, em centavos (float): gasto até agora + "a mais" previsto x escala.
    # O "a mais" não fica negativo: só um estorno faria a fatura fechar abaixo do gasto até agora, e o modelo não
    # prevê estornos (a Regressão Linear, sem esse limite, pode extrapolar para baixo).
    a_mais = np.maximum(modelo.predict(tabela[ATRIBUTOS]), 0.0)
    return tabela['atual'].to_numpy() + a_mais * tabela['escala'].to_numpy()


def limites_do_treino(tabela):
    # Menor e maior valor de cada atributo no treino: fora disso, o modelo estaria extrapolando.
    limites = {}
    for atributo in ATRIBUTOS:
        limites[atributo] = (float(tabela[atributo].min()), float(tabela[atributo].max()))
    return limites


ATRIBUTOS_DE_VALOR = ['atual_n', 'linear_a_mais_n', 'hist_restante_n', 'hist_restante_mediana_n', 'hist_total_n', 'desvio_n']


def fora_do_treino(limites, linha):
    # Atributos do retrato fora da faixa vista no treino (lista vazia = dentro).
    fora = []
    for atributo in ATRIBUTOS:
        menor, maior = limites[atributo]
        if not menor <= linha[atributo] <= maior:
            fora.append(atributo)
    return fora


def quantis_de_erro(tabela, previstos):
    # Erro relativo (real - previsto) / escala, por faixa do ciclo e do histórico: os quantis viram o intervalo,
    # e o erro absoluto médio (do modelo e da projeção linear) vira o "erro histórico" mostrado no app.
    relativo = (tabela['total'].to_numpy() - previstos) / tabela['escala'].to_numpy()
    relativo_linear = (tabela['total'].to_numpy() - tabela['linear_total'].to_numpy()) / tabela['escala'].to_numpy()
    resultado = {}
    for faixa_ciclo in FAIXAS_CICLO:
        for faixa_historico in FAIXAS_HISTORICO:
            filtro = ((tabela['faixa_ciclo'] == faixa_ciclo) & (tabela['faixa_historico'] == faixa_historico)).to_numpy()
            if filtro.sum() == 0:
                continue
            resultado[(faixa_ciclo, faixa_historico)] = {
                  'baixo': float(np.quantile(relativo[filtro], QUANTIL_BAIXO))
                , 'alto': float(np.quantile(relativo[filtro], QUANTIL_ALTO))
                , 'erro_medio': float(np.mean(np.abs(relativo[filtro])))
                , 'erro_medio_linear': float(np.mean(np.abs(relativo_linear[filtro])))
                , 'ciclos': int(tabela.loc[filtro, ['pessoa', 'ciclo']].drop_duplicates().shape[0])
                , 'retratos': int(filtro.sum())
            }
    return resultado


# ---------------------------------------------------------------- configuração do app
# Escolhidas no notebook (notebooks/previsao_gastos.ipynb), que tem travas que falham se estes valores ficarem
# diferentes do que ele mede.
TIPO_APP = FLORESTA
FOLHAS_APP = 50
# Fração dos casos de teste do notebook (pessoas novas) em que o gasto real ficou dentro da faixa provável.
COBERTURA_MEDIDA = 0.79
# Faturas completas anteriores necessárias para mostrar a previsão por ML (o modelo do app só treina com
# retratos que têm pelo menos esse histórico).
HISTORICO_MINIMO = 1
# Um retrato a cada PASSO_DIAS_APP dias do ciclo no treino (os retratos do mesmo ciclo são muito parecidos).
PASSO_DIAS_APP = 3
# População do app: pessoas de treino e de calibração (o intervalo e o erro histórico vêm destas, que o modelo
# não viu). Semente própria, diferente das do notebook.
SEMENTE_APP = 7
PESSOAS_TREINO_APP = 80
PESSOAS_CALIBRACAO_APP = 40


def retratos_de_treino(tabela, passo=PASSO_DIAS_APP, historico_minimo=HISTORICO_MINIMO):
    filtro = ((tabela['j'] % passo) == 0) & (tabela['anteriores'] >= historico_minimo)
    return tabela[filtro].reset_index(drop=True)


def treinar_para_app(semente=SEMENTE_APP, pessoas_treino=PESSOAS_TREINO_APP, pessoas_calibracao=PESSOAS_CALIBRACAO_APP, tipo=TIPO_APP, folhas=FOLHAS_APP):
    # Gera a população (com o efeito do salário), treina com as primeiras pessoas e mede o erro nas restantes.
    curvas = curvas_da_populacao(pessoas_treino + pessoas_calibracao, semente)
    nomes = list(curvas)
    todos_os_dias = tabela_de_retratos({nome: curvas[nome] for nome in nomes[:pessoas_treino]})
    treino = retratos_de_treino(todos_os_dias)
    # Calibração com o histórico cortado também: senão a faixa de quem tem 1 ou 2 faturas anteriores sairia de um
    # único ciclo por pessoa (40 no total) e ficava larga demais (medido na população de treino do notebook).
    calibracao = tabela_de_retratos({nome: curvas[nome] for nome in nomes[pessoas_treino:]}, historico_curto=True)
    modelo = treinar(treino, tipo, folhas)
    return {
          'modelo': modelo
        # Os limites vêm de todos os dias do ciclo das pessoas de treino (não só dos dias usados no treino): senão os
        # dias 1 e 2 de todo ciclo ficariam "fora do treino" só pela fração do ciclo.
        , 'limites': limites_do_treino(retratos_de_treino(todos_os_dias, passo=1))
        , 'tipo': tipo
        , 'quantis': quantis_de_erro(calibracao, prever_totais(modelo, calibracao))
        , 'pessoas_treino': pessoas_treino
        , 'pessoas_calibracao': pessoas_calibracao
    }


def prever(treinado, fatura, inicio, ultimo_dia, hoje, anteriores):
    # Previsão para o app. anteriores: curvas das faturas completas que vencem antes da atual (mais antiga
    # primeiro). Devolve None se não há o que prever (data antes do início ou compras já encerradas).
    # Com histórico abaixo do mínimo, ou fora do que o modelo viu no treino, devolve só o aviso (sem 'previsto').
    if hoje < inicio or hoje >= ultimo_dia:
        return None
    curva_atual = curva(fatura, inicio, ultimo_dia)
    j = (hoje - inicio).days + 1
    linha = atributos(curva_atual, j, anteriores)
    faixa = (faixa_do_ciclo(linha['fracao_decorrida']), faixa_do_historico(linha['anteriores']))
    resultado = {
          'anteriores': linha['anteriores']
        , 'historico_suficiente': linha['anteriores'] >= HISTORICO_MINIMO
        , 'fora_do_treino': fora_do_treino(treinado['limites'], linha)
        , 'linear': linha['atual'] + linha['linear_a_mais']
        , 'atual': linha['atual']
        , 'faixa_ciclo': faixa[0]
        , 'faixa_historico': faixa[1]
        , 'medido': treinado['quantis'].get(faixa)
        , 'escala': linha['escala']
    }
    # Sem o histórico mínimo, ou com a situação fora do que o modelo viu no treino: só o aviso, sem número do ML.
    if not resultado['historico_suficiente'] or resultado['fora_do_treino']:
        return resultado
    tabela = pd.DataFrame([linha])
    previsto = float(prever_totais(treinado['modelo'], tabela)[0])
    resultado['previsto'] = int(round(previsto))
    if resultado['medido'] is not None:
        # O gasto no fechamento só fica abaixo do gasto até agora com estorno; a faixa não desce além dele.
        resultado['baixo'] = max(int(round(previsto + resultado['medido']['baixo'] * linha['escala'])), linha['atual'])
        resultado['alto'] = max(int(round(previsto + resultado['medido']['alto'] * linha['escala'])), resultado['baixo'])
        resultado['erro_tipico'] = int(round(resultado['medido']['erro_medio'] * linha['escala']))
        resultado['erro_tipico_linear'] = int(round(resultado['medido']['erro_medio_linear'] * linha['escala']))
    return resultado
