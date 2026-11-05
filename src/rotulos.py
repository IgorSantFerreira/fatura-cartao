# Rótulos humanos: a categoria que o usuário conferiu para cada estabelecimento.
# São a "resposta certa" para treinar e avaliar a classificação por ML. Um rótulo só existe quando o usuário
# confirma: concordar com a categoria que as regras deram também conta, e é isso que evita rótulos circulares.
# Arquivo: {"chave do estabelecimento": "categoria"}.

import json
import os

import pandas as pd

import fatura as ft


# Lançamentos que não entram na rotulagem: movimentos da fatura, estornos (seguem a compra original)
# e encargos (gerados pelo próprio banco, sem estabelecimento).
CATEGORIAS_FORA = ft.CATEGORIAS_FORA_DO_GASTO + [ft.ENCARGOS]

# Categorias que um rótulo pode ter: as de compra. "A classificar" não é resposta; pagamento e saldo não são
# compra; juros/multas/IOF e estornos ficam fora da rotulagem (um rótulo assim sumiria da conferência e do conjunto).
CATEGORIAS_ROTULO = [
    categoria for categoria in ft.CATEGORIAS_ESCOLHA
    if categoria not in [ft.A_CLASSIFICAR, ft.ENCARGOS, ft.ESTORNOS]
]

# De onde veio cada rótulo (arquivo à parte, rotulos_origem.json): permite medir no notebook quanto dos rótulos
# só confirmou a categoria das regras (viés de ancoragem) e quanto o usuário corrigiu.
ORIGEM_CONFIRMOU = 'conferência: confirmou a categoria do app'
ORIGEM_TROCOU = 'conferência: trocou a categoria'
ORIGEM_A_CLASSIFICAR = 'formulário A classificar'
ORIGEM_CORRIGIR = 'corrigir'
ORIGEM_DESCONHECIDA = 'desconhecida'


def rotulavel(fatura):
    return fatura['conta_no_gasto'] & ~fatura['estorno'] & ~fatura['categoria'].isin(CATEGORIAS_FORA)


def carregar_rotulos(caminho):
    # Devolve (rótulos, erro). Com erro, nenhum rótulo é usado e o app não grava por cima do arquivo.
    if not os.path.exists(caminho):
        return {}, None
    try:
        with open(caminho, encoding='utf-8') as arquivo:
            conteudo = json.load(arquivo)
    except (OSError, ValueError) as erro:
        return {}, f'Não consegui ler {caminho}: {erro}'
    if not isinstance(conteudo, dict):
        return {}, f'{caminho} deveria conter um objeto JSON {{"estabelecimento": "categoria"}}.'
    rotulos = {}
    invalidos = []
    for chave, categoria in conteudo.items():
        if not isinstance(chave, str) or categoria not in CATEGORIAS_ROTULO:
            invalidos.append(str(chave))
            continue
        rotulos[ft.normalizar(chave)] = categoria
    if invalidos:
        return {}, f'{caminho} tem rótulos inválidos em: ' + ', '.join(invalidos[:10])
    return rotulos, None


def salvar_rotulos(caminho, rotulos):
    pasta = os.path.dirname(os.path.abspath(caminho))
    os.makedirs(pasta, exist_ok=True)
    temporario = caminho + '.tmp'
    with open(temporario, 'w', encoding='utf-8') as arquivo:
        json.dump(dict(sorted(rotulos.items())), arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


def caminho_origens(caminho_rotulos):
    return os.path.splitext(caminho_rotulos)[0] + '_origem.json'


def carregar_origens(caminho):
    # Devolve (origens, erro). {chave: {"origem": ..., "data": "AAAA-MM-DD"}}.
    if not os.path.exists(caminho):
        return {}, None
    try:
        with open(caminho, encoding='utf-8') as arquivo:
            conteudo = json.load(arquivo)
    except (OSError, ValueError) as erro:
        return {}, f'Não consegui ler {caminho}: {erro}'
    if not isinstance(conteudo, dict) or not all(isinstance(valor, dict) for valor in conteudo.values()):
        return {}, f'{caminho} deveria conter {{"estabelecimento": {{"origem": ..., "data": ...}}}}.'
    return conteudo, None


def salvar_origens(caminho, origens):
    pasta = os.path.dirname(os.path.abspath(caminho))
    os.makedirs(pasta, exist_ok=True)
    temporario = caminho + '.tmp'
    with open(temporario, 'w', encoding='utf-8') as arquivo:
        json.dump(dict(sorted(origens.items())), arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


def atualizar_origens(origens, antes, depois, origem_por_chave, data):
    # Rótulo novo ou com categoria trocada ganha origem e data; rótulo removido perde a origem.
    novas = dict(origens)
    for chave, categoria in depois.items():
        if antes.get(chave) != categoria:
            novas[chave] = {'origem': origem_por_chave.get(chave, ORIGEM_DESCONHECIDA), 'data': data.isoformat()}
    for chave in antes:
        if chave not in depois:
            novas.pop(chave, None)
    return novas


def para_conferir(fatura, rotulos):
    # Um item por estabelecimento rotulável da fatura, na ordem de quanto pesa no gasto.
    linhas = []
    candidatos = fatura[rotulavel(fatura)]
    for chave, grupo in candidatos.groupby('chave', sort=False):
        primeira = grupo.iloc[0]
        linhas.append([
              chave
            , primeira['estabelecimento']
            , primeira['descricao']
            , int(primeira['centavos'])
            , primeira['categoria']
            , int(len(grupo))
            , int(grupo['centavos'].sum())
            , chave in rotulos
            , rotulos.get(chave, primeira['categoria'])
        ])
    tabela = pd.DataFrame(linhas, columns=[
          'chave', 'estabelecimento', 'descricao', 'centavos_exemplo', 'categoria_atual'
        , 'lancamentos', 'centavos', 'conferido', 'categoria_sugerida'
    ])
    return tabela.sort_values(['centavos', 'estabelecimento'], ascending=[False, True]).reset_index(drop=True)


def aplicar_conferencia(rotulos, regras, itens, escolhas):
    # itens: tabela de para_conferir; escolhas: {chave: (categoria, conferido)}.
    # Conferido grava o rótulo e faz a categoria valer no app (regras do usuário). Desmarcar remove o rótulo.
    # Só as linhas que o usuário mexeu (diferentes do que a tela mostrou) contam: uma linha intocada nunca
    # desfaz um rótulo ou uma regra gravados por outro caminho.
    # Devolve (rótulos, regras, quantos conferidos, quantos removidos).
    novos_rotulos = dict(rotulos)
    novas_regras = dict(regras)
    conferidos = 0
    removidos = 0
    for item in itens.itertuples(index=False):
        if item.chave not in escolhas:
            continue
        categoria, conferido = escolhas[item.chave]
        if (categoria, bool(conferido)) == (item.categoria_sugerida, bool(item.conferido)):
            continue
        if conferido:
            if categoria not in CATEGORIAS_ROTULO:
                raise ValueError(f'Escolha uma categoria para {item.estabelecimento} antes de marcar como conferido.')
            novos_rotulos[item.chave] = categoria
            novas_regras = ft.aplicar_escolha(novas_regras, item.descricao, item.centavos_exemplo, categoria)
            conferidos = conferidos + 1
        elif item.chave in novos_rotulos:
            del novos_rotulos[item.chave]
            removidos = removidos + 1
    return novos_rotulos, novas_regras, conferidos, removidos


def registrar_escolha(rotulos, fatura, chave, categoria):
    # Escolha feita em outro lugar do app (formulário "A classificar", "Corrigir") também é rótulo humano,
    # se o estabelecimento é rotulável e a categoria é de compra. categoria=None remove o rótulo.
    novos = dict(rotulos)
    elegiveis = set(fatura.loc[rotulavel(fatura), 'chave'])
    if categoria is None:
        novos.pop(chave, None)
    elif chave in elegiveis and categoria in CATEGORIAS_ROTULO:
        novos[chave] = categoria
    return novos


def conjunto_rotulado(montadas, rotulos, origens=None, base=None):
    # Todos os lançamentos rotuláveis do histórico cujo estabelecimento tem rótulo humano.
    # "categoria_regras" é o que as regras automáticas dariam sozinhas (sem escolhas do usuário): baseline do ML.
    # "origem"/"data_rotulo": de onde veio o rótulo; "base": de qual base de dados (minhas ou simuladas).
    origens = origens or {}
    linhas = []
    for item in montadas:
        fatura = item['fatura']
        candidatos = fatura[rotulavel(fatura) & fatura['chave'].isin(rotulos.keys())]
        for lancamento in candidatos.itertuples(index=False):
            linhas.append([
                  item['vencimento']
                , lancamento.data.date()
                , lancamento.descricao
                , int(lancamento.centavos)
                , lancamento.estabelecimento
                , lancamento.chave
                , lancamento.parcela_atual if pd.notna(lancamento.parcela_atual) else None
                , lancamento.parcela_total if pd.notna(lancamento.parcela_total) else None
                , ft.classificar(lancamento.descricao, int(lancamento.centavos))[0]
                , rotulos[lancamento.chave]
                , origens.get(lancamento.chave, {}).get('origem', ORIGEM_DESCONHECIDA)
                , origens.get(lancamento.chave, {}).get('data')
                , base
            ])
    return pd.DataFrame(linhas, columns=[
          'vencimento', 'data', 'descricao', 'centavos', 'estabelecimento', 'chave'
        , 'parcela_atual', 'parcela_total', 'categoria_regras', 'rotulo', 'origem', 'data_rotulo', 'base'
    ])
