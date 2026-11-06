# Classificação de despesas por aprendizado de máquina: as mesmas funções servem ao notebook do experimento
# (notebooks/classificacao_despesas.ipynb) e ao app (sugestões na aba Classificar).
#
# Cada lançamento vira:
#   - texto: o nome do estabelecimento já normalizado pelo app (sem acento, sem número de parcela e sem código final);
#   - log_valor: o valor em reais em escala logarítmica (R$ 10 e R$ 100 ficam a uma distância razoável);
#   - frequencia: em que fração das faturas do histórico o estabelecimento aparece (o "histórico disponível");
#   - parcelado: 1 se é parcela;
#   - contexto temporal (opcional): dia da semana e posição no ciclo da fatura (0 = começo, 1 = fim).
#     O CSV do Nubank não tem horário, então não há hora nem sequência dentro do dia.

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import softmax
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import GroupKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import fatura as ft


LOGISTICA = 'Regressão Logística'
FLORESTA = 'Random Forest'


def historico_estabelecimentos(montadas):
    # O que o histórico (sem categorias) diz de cada estabelecimento:
    #   frequencia: fração das faturas em que ele aparece;
    #   valor_repetido: fração dos lançamentos dele com o valor mais comum (assinatura cobra sempre o mesmo valor).
    contagem = {}
    valores = {}
    for item in montadas:
        fatura = item['fatura']
        for chave in set(fatura['chave']):
            contagem[chave] = contagem.get(chave, 0) + 1
        for chave, centavos in zip(fatura['chave'], fatura['centavos']):
            valores.setdefault(chave, []).append(int(centavos))
    total = max(len(montadas), 1)
    resultado = {}
    for chave, vezes in contagem.items():
        lista = pd.Series(valores[chave])
        repetido = 0.0
        # Com um lançamento só não há repetição a medir (senão toda compra única pareceria assinatura).
        if len(lista) >= 2:
            repetido = float((lista == lista.mode()[0]).mean())
        resultado[chave] = {'frequencia': vezes / total, 'valor_repetido': repetido}
    return resultado


def preparar(linhas, historico):
    # linhas: tabela com descricao, centavos, data, vencimento e parcela_total (um lançamento por linha).
    datas = pd.to_datetime(linhas['data'])
    posicoes = []
    for dia, vencimento in zip(datas, linhas['vencimento']):
        # Fatura sem vencimento conhecido: sem ciclo, posição 0 (o modelo do app nem usa o contexto temporal).
        if vencimento is None or pd.isna(vencimento):
            posicoes.append(0.0)
        else:
            posicoes.append((dia.date() - ft.ciclo(vencimento)['inicio']).days / 30)
    textos = [ft.chave_estabelecimento(descricao) for descricao in linhas['descricao']]
    vazio = {'frequencia': 0.0, 'valor_repetido': 0.0}
    tabela = pd.DataFrame({
          'texto': textos
        , 'log_valor': np.log1p(np.abs(linhas['centavos'].astype(float)) / 100)
        , 'frequencia': [historico.get(texto, vazio)['frequencia'] for texto in textos]
        , 'valor_repetido': [historico.get(texto, vazio)['valor_repetido'] for texto in textos]
        , 'parcelado': linhas['parcela_total'].notna().astype(int).to_numpy()
        , 'dia_semana': datas.dt.dayofweek.astype(str).to_numpy()
        , 'posicao_ciclo': posicoes
    })
    return tabela


def montar_pipeline(tipo, usar_tempo=True, C=1.0, min_samples_leaf=1):
    # TF-IDF de pedaços de 2 a 4 letras do nome: pega "posto", "farma", "ifd*" mesmo em nomes nunca vistos.
    numeros = ['log_valor', 'frequencia', 'valor_repetido']
    colunas = [
          ('texto', TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), sublinear_tf=True), 'texto')
        , ('parcelado', 'passthrough', ['parcelado'])
    ]
    if usar_tempo:
        numeros = numeros + ['posicao_ciclo']
        colunas.append(('dia_semana', OneHotEncoder(handle_unknown='ignore'), ['dia_semana']))
    colunas.append(('numeros', StandardScaler(), numeros))
    if tipo == LOGISTICA:
        modelo = LogisticRegression(max_iter=5000, class_weight='balanced', C=C)
    else:
        modelo = RandomForestClassifier(
              n_estimators=300
            , class_weight='balanced_subsample'
            , min_samples_leaf=min_samples_leaf
            , random_state=0
            , n_jobs=1
        )
    return Pipeline([('atributos', ColumnTransformer(colunas)), ('modelo', modelo)])


def linhas_do_conjunto(conjunto):
    # Conjunto rotulado do app (rotulos.conjunto_rotulado) no formato de preparar().
    return pd.DataFrame({
          'descricao': conjunto['descricao']
        , 'centavos': conjunto['centavos']
        , 'data': conjunto['data']
        , 'vencimento': conjunto['vencimento']
        , 'parcela_total': conjunto['parcela_total']
    })


# ---------------------------------------------------------------- calibração por temperatura (só no notebook)
# A Regressão Logística dá uma pontuação por categoria (logit); a probabilidade é o softmax dessas pontuações.
# O ajuste de temperatura divide todas as pontuações por um número T, aprendido com estabelecimentos que o
# modelo não viu no treino: T > 1 deixa o modelo menos confiante, T < 1 mais. A categoria sugerida não muda.
# Testado no notebook: com os dados disponíveis piorou a calibração (e a sigmoide piorou o acerto), então o app
# mostra a probabilidade do modelo sem calibração, avisando que ela tende a ser otimista.

def pontuacoes(pipeline, atributos, classes):
    # Logits nas colunas de "classes"; categoria que o modelo não conheceu no treino fica com pontuação mínima.
    brutas = pipeline.decision_function(atributos)
    conhecidas = list(pipeline.named_steps['modelo'].classes_)
    if brutas.ndim == 1:
        # Com 2 categorias o sklearn devolve uma coluna só (a da segunda); a primeira equivale a 0.
        brutas = np.column_stack([np.zeros(len(brutas)), brutas])
    resultado = np.full((len(atributos), len(classes)), -1e6)
    for coluna, categoria in enumerate(conhecidas):
        resultado[:, classes.index(categoria)] = brutas[:, coluna]
    return resultado


def ajustar_temperatura(logits, certo, classes):
    # T que minimiza a perda logarítmica (log loss) das probabilidades nos dados de calibração.
    indices = np.array([classes.index(categoria) for categoria in certo])

    def perda(temperatura):
        probabilidades = softmax(logits / temperatura, axis=1)
        return -np.mean(np.log(np.clip(probabilidades[np.arange(len(indices)), indices], 1e-12, 1)))

    return float(minimize_scalar(perda, bounds=(0.05, 20.0), method='bounded').x)


def temperatura_por_validacao(tipo, atributos, certo, grupos, usar_tempo=False, C=1.0, dobras=3):
    # Pontuações fora da dobra (validação agrupada por estabelecimento) -> temperatura.
    # Devolve None se não há estabelecimentos suficientes para separar.
    classes = sorted(set(certo))
    if len(set(grupos)) < dobras:
        return None
    logits = np.zeros((len(certo), len(classes)))
    for treino, teste in GroupKFold(n_splits=dobras).split(atributos, certo, grupos):
        if len(set(certo[treino])) < 2:
            return None
        pipeline = montar_pipeline(tipo, usar_tempo=usar_tempo, C=C)
        pipeline.fit(atributos.iloc[treino], certo[treino])
        logits[teste] = pontuacoes(pipeline, atributos.iloc[teste], classes)
    return ajustar_temperatura(logits, certo, classes)


# Configuração do app: a que o procedimento de escolha do notebook (14 combinações de modelo, contexto temporal e
# hiperparâmetro; validação agrupada por estabelecimento) escolhe com todos os dados sintéticos.
# O notebook tem uma trava que falha se estes valores ficarem diferentes do que ele calcula.
TIPO_APP = LOGISTICA
C_APP = 100.0
TEMPO_APP = False

# Confiança x acerto medidos no notebook, fora da dobra, nos lançamentos que as regras deixam "A classificar"
# (os únicos que recebem sugestão). Por estabelecimento é o que o app mostra (média das probabilidades).
# O texto do app é montado com estes números; o notebook tem uma trava que falha se eles mudarem.
CALIBRACAO_SUGESTOES = {
      'por_lancamento': {'confianca': 0.634, 'acerto': 0.537, 'quantidade': 149}
    , 'por_estabelecimento': {'confianca': 0.565, 'acerto': 0.452, 'quantidade': 31}
}


def texto_da_confianca():
    # Frase para o app, montada com os números medidos (nada escrito à mão).
    medida = CALIBRACAO_SUGESTOES['por_estabelecimento']
    lancamento = CALIBRACAO_SUGESTOES['por_lancamento']
    otimista = medida['confianca'] > medida['acerto'] and lancamento['confianca'] > lancamento['acerto']
    pessimista = medida['confianca'] < medida['acerto'] and lancamento['confianca'] < lancamento['acerto']
    if otimista:
        tendencia = 'ele tende a ser otimista'
    elif pessimista:
        tendencia = 'ele tende a ser pessimista'
    else:
        tendencia = 'a confiança não tende claramente para nenhum lado'
    return (
        f'Nos testes com faturas fictícias, nos {medida["quantidade"]} estabelecimentos que as regras não '
        + f'reconheciam, o modelo dizia em média {medida["confianca"]:.0%} e acertou {medida["acerto"]:.0%} '
        + f'(contando os {lancamento["quantidade"]} lançamentos deles: {lancamento["confianca"]:.0%} e '
        + f'{lancamento["acerto"]:.0%}): {tendencia}.'
    )


def treinar(conjunto, historico, tipo=TIPO_APP, C=C_APP, usar_tempo=TEMPO_APP):
    # Treina com os rótulos humanos da base. historico: historico_estabelecimentos() das faturas da base.
    # Devolve None se houver menos de 2 categorias (não há o que separar).
    if len(conjunto) == 0 or conjunto['rotulo'].nunique() < 2:
        return None
    atributos = preparar(linhas_do_conjunto(conjunto), historico)
    pipeline = montar_pipeline(tipo, usar_tempo=usar_tempo, C=C)
    pipeline.fit(atributos, conjunto['rotulo'].to_numpy())
    rotulados = conjunto.drop_duplicates('chave')[['chave', 'estabelecimento', 'rotulo']].reset_index(drop=True)
    return {'pipeline': pipeline, 'historico': historico, 'rotulados': rotulados, 'tipo': tipo}


def sugerir(treinado, linhas, quantos_parecidos=3):
    # linhas: tabela no formato de preparar() mais a coluna chave. Uma sugestão por estabelecimento
    # (a média das probabilidades dos lançamentos dele), com os estabelecimentos rotulados mais parecidos.
    atributos = preparar(linhas, treinado['historico'])
    pipeline = treinado['pipeline']
    classes = list(pipeline.named_steps['modelo'].classes_)
    probabilidades = pipeline.predict_proba(atributos)
    tabela = pd.DataFrame(probabilidades, columns=classes)
    tabela['chave'] = list(linhas['chave'])
    media = tabela.groupby('chave', sort=False)[classes].mean()

    vetorizador = pipeline.named_steps['atributos'].named_transformers_['texto']
    rotulados = treinado['rotulados']
    vetores_rotulados = vetorizador.transform(list(rotulados['chave']))
    vetores_novos = vetorizador.transform(list(media.index))
    semelhanca = cosine_similarity(vetores_novos, vetores_rotulados)

    resultado = []
    for posicao, chave in enumerate(media.index):
        linha = media.loc[chave]
        categoria = linha.idxmax()
        ordem = np.argsort(-semelhanca[posicao])[:quantos_parecidos]
        parecidos = []
        for indice in ordem:
            if semelhanca[posicao][indice] > 0:
                parecidos.append((rotulados['estabelecimento'].iloc[indice], rotulados['rotulo'].iloc[indice]))
        resultado.append([chave, categoria, float(linha.max()), parecidos])
    return pd.DataFrame(resultado, columns=['chave', 'categoria', 'confianca', 'parecidos'])
