# Histórico de faturas: um arquivo JSON por vencimento, com o texto do CSV como veio do Nubank.
# O CSV é guardado bruto e reclassificado a cada abertura, para as regras do usuário valerem também no passado.

import json
import os
import re
from collections import Counter
from datetime import date

import pandas as pd

import fatura as ft


PADRAO_ARQUIVO = re.compile(r'^(\d{4}-\d{2}-\d{2})\.json$')

NOVA = 'nova'
SUBSTITUIDA = 'substituida'
ATUALIZADA = 'atualizada'
IGUAL = 'igual'
MANTIDA = 'mantida'
DUPLICADA = 'duplicada'
CONFLITO = 'conflito'
ERRO = 'erro'
REMOVIDA = 'removida'


def data_de_hoje():
    # A data real (não a "Considerar compras até" da barra lateral): diz se a fatura já tinha fechado ao ser guardada.
    return date.today()


def caminho_da_fatura(pasta, vencimento):
    return os.path.join(pasta, f'{vencimento.isoformat()}.json')


def lancamentos(df):
    # Conjunto (com repetição) dos lançamentos: compara exportações da mesma fatura sem olhar a ordem.
    return Counter(zip(df['data'].dt.date, df['descricao'], df['centavos'].astype(int)))


def contem(maior, menor):
    for lancamento, vezes in menor.items():
        if maior.get(lancamento, 0) < vezes:
            return False
    return True


def ler_entrada(caminho, vencimento_do_nome):
    with open(caminho, encoding='utf-8') as arquivo:
        conteudo = json.load(arquivo)
    if not isinstance(conteudo, dict):
        raise ValueError('não é um objeto JSON')
    for campo in ['vencimento', 'fechamento', 'salvo_em', 'csv']:
        if not isinstance(conteudo.get(campo), str):
            raise ValueError(f'campo {campo} ausente ou inválido')
    vencimento = date.fromisoformat(conteudo['vencimento'])
    if vencimento != vencimento_do_nome:
        raise ValueError('o vencimento do conteúdo não bate com o nome do arquivo')
    fechamento = date.fromisoformat(conteudo['fechamento'])
    salvo_em = date.fromisoformat(conteudo['salvo_em'])
    df = ft.ler_csv(conteudo['csv'])
    return {
          'vencimento': vencimento
        , 'fechamento': fechamento
        , 'salvo_em': salvo_em
        , 'arquivo': str(conteudo.get('arquivo', ''))
        , 'csv': conteudo['csv']
        , 'df': df
        # Guardada antes de fechar: os lançamentos dos dias seguintes não estão nela.
        , 'completa': salvo_em >= fechamento
        , 'caminho': caminho
    }


def carregar_historico(pasta):
    # Devolve (entradas ordenadas por vencimento, erros). Um arquivo ruim não impede os outros.
    entradas = []
    erros = []
    if not os.path.isdir(pasta):
        return entradas, erros
    for nome in sorted(os.listdir(pasta)):
        achado = PADRAO_ARQUIVO.match(nome)
        if achado is None:
            continue
        caminho = os.path.join(pasta, nome)
        try:
            entradas.append(ler_entrada(caminho, date.fromisoformat(achado.group(1))))
        except (OSError, ValueError, TypeError) as erro:
            erros.append({'vencimento': achado.group(1), 'caminho': caminho, 'erro': str(erro)})
    return entradas, erros


def gravar(caminho, vencimento, fechamento, salvo_em, nome_arquivo, texto):
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    temporario = caminho + '.tmp'
    with open(temporario, 'w', encoding='utf-8') as arquivo:
        json.dump(
              {
                  'vencimento': vencimento.isoformat()
                , 'fechamento': fechamento.isoformat()
                , 'salvo_em': salvo_em.isoformat()
                , 'arquivo': nome_arquivo
                , 'csv': texto
              }
            , arquivo
            , ensure_ascii=False
            , indent=2
        )
    os.replace(temporario, caminho)


def guardar(pasta, conteudo, nome_arquivo, vencimento, fechamento, hoje):
    # Devolve (situação, mensagem). "hoje" é a data real em que a fatura é guardada.
    texto = ft.decodificar(conteudo)
    nova = lancamentos(ft.ler_csv(texto))
    entradas, erros = carregar_historico(pasta)
    caminho = caminho_da_fatura(pasta, vencimento)

    for erro in erros:
        if erro['caminho'] == caminho:
            return ERRO, (
                f'Não guardei esta fatura no histórico: o arquivo já guardado para {vencimento:%d/%m/%Y} '
                + f'está com problema ({erro["erro"]}). Remova-o na aba Mês a mês para guardar de novo.'
            )

    for entrada in entradas:
        if entrada['vencimento'] != vencimento and lancamentos(entrada['df']) == nova:
            return DUPLICADA, (
                f'Não guardei: estes mesmos lançamentos já estão no histórico como a fatura que vence em '
                + f'{entrada["vencimento"]:%d/%m/%Y}. Se o vencimento certo é outro, corrija na barra lateral '
                + 'e remova a errada na aba Mês a mês.'
            )

    for entrada in entradas:
        if entrada['vencimento'] != vencimento:
            continue
        guardada = lancamentos(entrada['df'])
        if guardada == nova:
            # Mesmo conteúdo aberto depois do fechamento conta como completo, igual a abrir pela primeira vez
            # depois do fechamento: o CSV não diz quando foi exportado.
            salvo_em = entrada['salvo_em']
            completou = salvo_em < fechamento <= hoje
            if completou:
                salvo_em = hoje
            if entrada['fechamento'] == fechamento and not completou:
                return IGUAL, f'Esta fatura já está no histórico (vencimento {vencimento:%d/%m/%Y}).'
            gravar(caminho, vencimento, fechamento, salvo_em, entrada['arquivo'], entrada['csv'])
            partes = []
            if entrada['fechamento'] != fechamento:
                partes.append(f'fechamento atualizado para {fechamento:%d/%m/%Y}')
            if completou:
                partes.append('agora marcada como completa (aberta depois do fechamento)')
            elif salvo_em < fechamento:
                partes.append('continua parcial (guardada antes do fechamento)')
            return ATUALIZADA, f'Fatura {vencimento:%d/%m/%Y} no histórico: ' + '; '.join(partes) + '.'
        if contem(guardada, nova):
            return MANTIDA, (
                f'O histórico já tem uma versão mais completa da fatura {vencimento:%d/%m/%Y} '
                + f'({sum(guardada.values())} lançamentos, este arquivo tem {sum(nova.values())}). Mantive a guardada.'
            )
        ultima_nova = max(data for data, descricao, centavos in nova)
        ultima_guardada = max(data for data, descricao, centavos in guardada)
        if ultima_nova < ultima_guardada:
            # Lançamentos diferentes e este arquivo termina antes: parece uma exportação mais antiga.
            return CONFLITO, (
                f'Não troquei a fatura {vencimento:%d/%m/%Y} guardada: este arquivo parece mais antigo '
                + f'(último lançamento em {ultima_nova:%d/%m/%Y}; a guardada vai até {ultima_guardada:%d/%m/%Y}) '
                + 'e tem lançamentos diferentes. Se este é o certo, remova a guardada na aba Mês a mês.'
            )
        gravar(caminho, vencimento, fechamento, hoje, nome_arquivo, texto)
        return SUBSTITUIDA, (
            f'Fatura {vencimento:%d/%m/%Y} atualizada no histórico: a versão guardada em {entrada["salvo_em"]:%d/%m/%Y} '
            + f'tinha {sum(guardada.values())} lançamentos, esta tem {sum(nova.values())}.'
        )

    gravar(caminho, vencimento, fechamento, hoje, nome_arquivo, texto)
    return NOVA, f'Fatura {vencimento:%d/%m/%Y} guardada no histórico.'


OUTRA_BASE = 'outra base'


def guardada_em(pasta, conteudo):
    # Vencimento da fatura guardada nesta pasta que é a mesma fatura (mesmos lançamentos) ou outra exportação
    # dela (uma contém todos os lançamentos da outra: exportação parcial, ou mais nova). Senão None.
    # Usado para recusar a mesma fatura nas duas bases (reais e simuladas não se misturam).
    nova = lancamentos(ft.ler_csv(ft.decodificar(conteudo)))
    entradas, erros = carregar_historico(pasta)
    for entrada in entradas:
        guardada = lancamentos(entrada['df'])
        if contem(guardada, nova) or contem(nova, guardada):
            return entrada['vencimento']
    return None


def remover(pasta, vencimento):
    caminho = caminho_da_fatura(pasta, vencimento)
    if os.path.exists(caminho):
        os.remove(caminho)
        return True
    return False


# ---------------------------------------------------------------- comparações

def montar(entradas, regras_usuario):
    # Rótulo "nov/2026"; se duas faturas vencem no mesmo mês (troca de vencimento), a data inteira.
    meses = Counter(ft.nome_mes(entrada['vencimento']) for entrada in entradas)
    montadas = []
    for entrada in entradas:
        rotulo = ft.nome_mes(entrada['vencimento'])
        if meses[rotulo] > 1:
            rotulo = entrada['vencimento'].strftime('%d/%m/%Y')
        montadas.append({
              'vencimento': entrada['vencimento']
            , 'fechamento': entrada['fechamento']
            , 'rotulo': rotulo
            , 'completa': entrada['completa']
            , 'fatura': ft.montar_fatura(entrada['df'], regras_usuario)
        })
    return montadas


def gasto_por_categoria(fatura):
    resumo = ft.resumo_categorias(fatura)
    return {linha.categoria: int(linha.centavos) for linha in resumo.itertuples(index=False)}


def tabela_mensal(montadas):
    # Formato longo: uma linha por fatura e categoria, mais o total da fatura.
    linhas = []
    for item in montadas:
        valores = gasto_por_categoria(item['fatura'])
        for categoria, centavos in valores.items():
            linhas.append([item['vencimento'], item['rotulo'], item['completa'], categoria, centavos])
        linhas.append([item['vencimento'], item['rotulo'], item['completa'], 'Total', ft.totais(item['fatura'])['gasto']])
    return pd.DataFrame(linhas, columns=['vencimento', 'fatura', 'completa', 'categoria', 'centavos'])


def media_anterior(montadas, vencimento_atual):
    # Média por categoria das faturas completas que vencem antes da atual (categoria ausente conta zero).
    anteriores = [item for item in montadas if item['completa'] and item['vencimento'] < vencimento_atual]
    if len(anteriores) == 0:
        return {}, []
    somas = {}
    for item in anteriores:
        for categoria, centavos in gasto_por_categoria(item['fatura']).items():
            somas[categoria] = somas.get(categoria, 0) + centavos
        somas['Total'] = somas.get('Total', 0) + ft.totais(item['fatura'])['gasto']
    medias = {}
    for categoria, soma in somas.items():
        medias[categoria] = ft.dividir_arredondando(soma, len(anteriores))
    return medias, anteriores


ACIMA = 'acima'
ABAIXO = 'abaixo'


CATEGORIAS_FORA_DO_PADRAO = [ft.A_CLASSIFICAR, ft.ESTORNOS]


def fora_do_padrao(montadas, vencimento_atual, valores_atuais):
    # Categorias em que esta fatura fica acima do maior ou abaixo do menor valor das faturas completas anteriores.
    # Sem parâmetro escolhido a dedo: se os meses fossem trocáveis entre si (nenhum é especial), a chance de um mês
    # comum passar do maior de n anteriores é 1/(n+1), e a de ficar fora do intervalo (acima ou abaixo) é 2/(n+1).
    # Com k categorias comparadas, espera-se perto de 2k/(n+1) avisos só por acaso.
    # "A classificar" e estornos não são consumo: ficam de fora.
    # Devolve (tabela, n, k) ou (None, n, 0) se faltar histórico (menos de 2 faturas completas anteriores).
    anteriores = [item for item in montadas if item['completa'] and item['vencimento'] < vencimento_atual]
    if len(anteriores) < 2:
        return None, len(anteriores), 0
    por_fatura = []
    for item in anteriores:
        valores = gasto_por_categoria(item['fatura'])
        valores['Total'] = ft.totais(item['fatura'])['gasto']
        por_fatura.append(valores)
    linhas = []
    comparadas = 0
    for categoria in ft.CATEGORIAS + ['Total']:
        if categoria in CATEGORIAS_FORA_DO_PADRAO:
            continue
        if categoria not in valores_atuais and all(categoria not in valores for valores in por_fatura):
            continue
        comparadas = comparadas + 1
        historico_categoria = [int(valores.get(categoria, 0)) for valores in por_fatura]
        atual = int(valores_atuais.get(categoria, 0))
        maximo = max(historico_categoria)
        minimo = min(historico_categoria)
        if atual > maximo:
            linhas.append([categoria, atual, minimo, maximo, ACIMA])
        elif atual < minimo:
            linhas.append([categoria, atual, minimo, maximo, ABAIXO])
    return pd.DataFrame(linhas, columns=['categoria', 'atual', 'minimo', 'maximo', 'direcao']), len(anteriores), comparadas


def comparar_com_media(valores_atuais, medias):
    # valores_atuais: {categoria: centavos} desta fatura (com 'Total'). Uma linha por categoria presente em um dos dois.
    linhas = []
    for categoria in ft.CATEGORIAS + ['Total']:
        if categoria not in valores_atuais and categoria not in medias:
            continue
        atual = int(valores_atuais.get(categoria, 0))
        media = int(medias.get(categoria, 0))
        percentual = None
        if media > 0:
            percentual = (atual - media) * 100 / media
        linhas.append([categoria, atual, media, atual - media, percentual])
    return pd.DataFrame(linhas, columns=['categoria', 'atual', 'media', 'diferenca', 'percentual'])


CATEGORIAS_NAO_RECORRENTES = [ft.ENCARGOS, ft.ESTORNOS]


def candidatos_recorrentes(fatura):
    return fatura[
          fatura['conta_no_gasto']
        & (fatura['centavos'] > 0)
        & fatura['parcela_total'].isna()
        & ~fatura['estorno']
        & ~fatura['categoria'].isin(CATEGORIAS_NAO_RECORRENTES)
    ]


def valores_ativos(valores_completa, valores_depois):
    # Valores ainda cobrados de um estabelecimento: os da fatura mais nova em que ele aparece depois da
    # última completa (aberta) e, da última completa, os que não foram substituídos.
    # Um valor novo na aberta substitui o valor mais próximo da completa (reajuste, assinatura em dólar);
    # um valor da completa que ainda não apareceu na aberta continua (só não foi cobrado ainda).
    # Devolve (valores ativos, {valor novo: valor antigo que ele substituiu}).
    restantes = sorted(valores_completa - valores_depois)
    substituicoes = {}
    for novo in sorted(valores_depois - valores_completa):
        if restantes:
            mais_proximo = min(restantes, key=lambda valor: (abs(valor - novo), valor))
            restantes.remove(mais_proximo)
            substituicoes[novo] = mais_proximo
    return set(valores_depois) | set(restantes), substituicoes


def recorrentes(montadas):
    # Cobrança recorrente: mesmo estabelecimento e mesmo valor, uma única vez em cada fatura em que aparece,
    # em pelo menos 2 faturas, sem faltar em nenhuma fatura guardada entre a primeira e a última vez.
    # Também entram as cobranças da categoria Assinaturas da última fatura completa e das seguintes (pelo nome).
    montadas = sorted(montadas, key=lambda item: (item['vencimento'] is None, item['vencimento'] or date.min))
    aparicoes = {}
    valores_por_fatura = []
    for posicao, item in enumerate(montadas):
        candidatos = candidatos_recorrentes(item['fatura'])
        valores = {}
        for (chave, centavos), grupo in candidatos.groupby(['chave', 'centavos'], sort=False):
            aparicoes.setdefault((chave, int(centavos)), []).append(
                (posicao, len(grupo), grupo['estabelecimento'].iloc[-1], grupo['categoria'].iloc[-1])
            )
            valores.setdefault(chave, set()).add(int(centavos))
        valores_por_fatura.append(valores)

    # Ativa (ainda cobrada): conta a partir da última fatura completa. Uma fatura parcial (aberta) ainda não
    # teve todas as cobranças do mês, então não tira uma cobrança fixa do total; mas um valor novo nela
    # substitui o antigo, para a mesma assinatura não contar duas vezes. Sem fatura completa, vale a mais recente.
    referencia = len(montadas) - 1
    completas = [posicao for posicao, item in enumerate(montadas) if item.get('completa')]
    if completas:
        referencia = max(completas)
    chaves = set()
    for valores in valores_por_fatura:
        chaves.update(valores)
    ativos = {}
    substituicoes = {}
    for chave in chaves:
        valores_completa = set()
        if referencia >= 0:
            valores_completa = valores_por_fatura[referencia].get(chave, set())
        valores_depois = set()
        for valores in valores_por_fatura[referencia + 1:]:
            if chave in valores:
                valores_depois = valores[chave]
        ativos[chave], substituicoes[chave] = valores_ativos(valores_completa, valores_depois)

    def ativa(par):
        return par[1] in ativos.get(par[0], set())

    linhas = {}
    for (chave, centavos), lista in aparicoes.items():
        posicoes = [posicao for posicao, vezes, nome, categoria in lista]
        uma_vez = all(vezes == 1 for posicao, vezes, nome, categoria in lista)
        seguidas = max(posicoes) - min(posicoes) + 1 == len(posicoes)
        if uma_vez and seguidas and len(posicoes) >= 2:
            posicao, vezes, nome, categoria = lista[-1]
            linhas[(chave, centavos)] = [nome, categoria, centavos, len(posicoes), ativa((chave, centavos)), 'repete todo mês']

    for item_fatura in montadas[max(referencia, 0):]:
        assinaturas = candidatos_recorrentes(item_fatura['fatura'])
        assinaturas = assinaturas[assinaturas['categoria'] == ft.ASSINATURAS]
        for item in assinaturas.itertuples(index=False):
            par = (item.chave, int(item.centavos))
            if par in linhas:
                if 'assinatura conhecida' not in linhas[par][5]:
                    linhas[par][5] = linhas[par][5] + '; assinatura conhecida'
            else:
                linhas[par] = [item.estabelecimento, item.categoria, int(item.centavos), len(aparicoes.get(par, [])), ativa(par), 'assinatura conhecida']

    # Um fixo que mudou de valor na fatura aberta (reajuste da internet, conta com outro valor) não pode sumir
    # do total: o valor novo entra no lugar do antigo, marcado para o usuário conferir.
    # Como em todo fixo, o valor novo precisa aparecer uma vez só na fatura (três compras de 12,00 são hábito).
    for chave, trocas in substituicoes.items():
        for novo, antigo in trocas.items():
            if (chave, antigo) in linhas and (chave, novo) not in linhas:
                posicao, vezes, nome, categoria = aparicoes[(chave, novo)][-1]
                if vezes != 1:
                    continue
                linhas[(chave, novo)] = [nome, categoria, novo, len(aparicoes[(chave, novo)]), ativa((chave, novo)), 'valor mudou (a confirmar)']

    tabela = pd.DataFrame(
          [[par[0]] + valores for par, valores in linhas.items()]
        , columns=['chave', 'estabelecimento', 'categoria', 'centavos', 'faturas', 'ativa', 'como']
    )
    tabela['por_ano'] = tabela['centavos'] * 12
    tabela = tabela.sort_values(['ativa', 'centavos', 'estabelecimento'], ascending=[False, False, True]).reset_index(drop=True)
    return tabela
