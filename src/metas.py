# Metas de gasto por categoria (ou grupo de categorias) para cada fatura.
# Valores em centavos. Arquivo: {"metas": [{"categorias": [...], "centavos": 140000}, ...]}.

import json
import os

import fatura as ft


# Pagamento e saldo anterior não são gasto: não faz sentido meta para eles.
CATEGORIAS_META = [categoria for categoria in ft.CATEGORIAS if categoria not in ft.CATEGORIAS_FORA_DO_GASTO]


def ordenar_categorias(categorias):
    # Mesma ordem de ft.CATEGORIAS, sem repetição: "Transporte + Comida" e "Comida + Transporte" são a mesma meta.
    return [categoria for categoria in CATEGORIAS_META if categoria in categorias]


FATURA_INTEIRA = 'Fatura inteira (todas as categorias)'


def e_fatura_inteira(categorias):
    # Meta com todas as categorias = orçamento do gasto total do período (o que a previsão por ML prevê).
    return list(categorias) == CATEGORIAS_META


def nome_meta(categorias):
    if e_fatura_inteira(categorias):
        return FATURA_INTEIRA
    return ' + '.join(categorias)


def carregar_metas(caminho):
    # Devolve (metas, erro). Com erro, nenhuma meta é usada e o app não grava por cima do arquivo.
    if not os.path.exists(caminho):
        return [], None
    try:
        with open(caminho, encoding='utf-8') as arquivo:
            conteudo = json.load(arquivo)
    except (OSError, ValueError) as erro:
        return [], f'Não consegui ler {caminho}: {erro}'
    if not isinstance(conteudo, dict) or not isinstance(conteudo.get('metas'), list):
        return [], f'{caminho} deveria conter {{"metas": [...]}}.'
    metas = []
    for posicao, item in enumerate(conteudo['metas'], start=1):
        if not isinstance(item, dict):
            return [], f'{caminho}: a meta {posicao} não é um objeto.'
        categorias = item.get('categorias')
        centavos = item.get('centavos')
        if not isinstance(categorias, list) or len(categorias) == 0 or any(categoria not in CATEGORIAS_META for categoria in categorias):
            return [], f'{caminho}: a meta {posicao} tem categorias inválidas.'
        # bool é int em Python: true/false não podem virar 1/0 centavo.
        if not isinstance(centavos, int) or isinstance(centavos, bool) or centavos <= 0:
            return [], f'{caminho}: a meta {posicao} tem um valor inválido.'
        metas = definir_meta(metas, categorias, centavos)
    return metas, None


def salvar_metas(caminho, metas):
    pasta = os.path.dirname(os.path.abspath(caminho))
    os.makedirs(pasta, exist_ok=True)
    temporario = caminho + '.tmp'
    with open(temporario, 'w', encoding='utf-8') as arquivo:
        json.dump({'metas': metas}, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


def definir_meta(metas, categorias, centavos):
    # Cria a meta ou troca o valor da que tem exatamente as mesmas categorias.
    categorias = ordenar_categorias(categorias)
    if len(categorias) == 0:
        raise ValueError('Escolha pelo menos uma categoria.')
    if not isinstance(centavos, int) or isinstance(centavos, bool) or centavos <= 0:
        raise ValueError('O valor da meta precisa ser maior que zero.')
    novas = []
    trocou = False
    for meta in metas:
        if meta['categorias'] == categorias:
            novas.append({'categorias': categorias, 'centavos': centavos})
            trocou = True
        else:
            novas.append(dict(meta))
    if not trocou:
        novas.append({'categorias': categorias, 'centavos': centavos})
    return novas


def remover_meta(metas, categorias):
    categorias = ordenar_categorias(categorias)
    return [dict(meta) for meta in metas if meta['categorias'] != categorias]


RITMO = 'ritmo'
MODELO = 'modelo'


def situacao(metas, atual_por_categoria, projetado_por_categoria=None, dias_restantes=None, previsto_total=None):
    # atual/projetado: {categoria: centavos}. Sem projeção (vencimento desconhecido), só o atual.
    # previsto_total: gasto total previsto pelo modelo de ML (só o total; None se não há previsão). Vale só para a
    # meta da fatura inteira; as metas por categoria seguem a projeção pelo ritmo.
    # "Por dia" é arredondado para baixo: seguindo esse valor, a meta não estoura por centavos.
    linhas = []
    for meta in metas:
        atual = sum(int(atual_por_categoria.get(categoria, 0)) for categoria in meta['categorias'])
        projetado = None
        fonte = RITMO
        if projetado_por_categoria is not None:
            projetado = sum(int(projetado_por_categoria.get(categoria, 0)) for categoria in meta['categorias'])
        if previsto_total is not None and e_fatura_inteira(meta['categorias']):
            projetado = int(previsto_total)
            fonte = MODELO
        restante = meta['centavos'] - atual
        por_dia = None
        if dias_restantes is not None and dias_restantes > 0 and restante > 0:
            por_dia = restante // dias_restantes
        if atual > meta['centavos']:
            estado = 'estourou'
        elif projetado is not None and projetado > meta['centavos']:
            estado = 'vai estourar'
        else:
            estado = 'dentro'
        linhas.append({
              'nome': nome_meta(meta['categorias'])
            , 'categorias': meta['categorias']
            , 'meta': meta['centavos']
            , 'atual': atual
            , 'restante': restante
            , 'projetado': projetado
            , 'fonte': fonte
            , 'por_dia': por_dia
            , 'dias_restantes': dias_restantes
            , 'estado': estado
            , 'percentual': atual * 100 / meta['centavos']
        })
    return linhas


def frase_situacao(linha):
    # Texto para st.markdown (valores escapados).
    nome = ft.escapar_markdown(linha['nome'])
    meta = ft.reais_md(linha['meta'])
    atual = ft.reais_md(linha['atual'])
    if linha['estado'] == 'estourou':
        return f'**{nome}** já passou da meta de {meta}: {atual} até agora ({ft.reais_md(-linha["restante"])} acima).'
    if linha['estado'] == 'vai estourar':
        como = 'pela previsão do modelo deve fechar em' if linha.get('fonte') == MODELO else 'no ritmo atual fecha em'
        return (
            f'**{nome}**: {atual} de {meta} até agora, mas {como} {ft.reais_md(linha["projetado"])} '
            + f'({ft.reais_md(linha["projetado"] - linha["meta"])} acima da meta).'
        )
    return f'**{nome}**: {atual} de {meta} até agora.'
