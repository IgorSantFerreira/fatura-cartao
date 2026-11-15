# Leitura, classificação e resumos da fatura do cartão.
# Todos os valores são guardados em centavos (int) para as somas serem exatas.

import calendar
import csv
import io
import json
import os
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd


COMIDA = 'Comida e bebida'
TRANSPORTE = 'Transporte'
ASSINATURAS = 'Assinaturas'
COMPRAS = 'Compras'
JOGOS = 'Jogos'
VIAGEM = 'Viagem'
SAUDE = 'Saúde'
LAZER = 'Lazer'
CASA = 'Casa e contas'
ENCARGOS = 'Juros, multas e IOF'
ESTORNOS = 'Estornos e créditos'
OUTROS = 'Outros'
A_CLASSIFICAR = 'A classificar'
PAGAMENTO = 'Pagamento da fatura'
SALDO_ANTERIOR = 'Saldo da fatura anterior'

CATEGORIAS = [
      COMIDA
    , TRANSPORTE
    , ASSINATURAS
    , COMPRAS
    , JOGOS
    , VIAGEM
    , SAUDE
    , LAZER
    , CASA
    , ENCARGOS
    , ESTORNOS
    , OUTROS
    , A_CLASSIFICAR
    , PAGAMENTO
    , SALDO_ANTERIOR
]

# Movimentos da própria fatura: não são gasto do período.
CATEGORIAS_FORA_DO_GASTO = [PAGAMENTO, SALDO_ANTERIOR]

# O que o usuário pode escolher na tela. Uma compra não pode virar pagamento ou saldo anterior,
# senão ela sumiria do gasto sem aviso; um crédito sem regra pode ser marcado como pagamento.
CATEGORIAS_ESCOLHA = [categoria for categoria in CATEGORIAS if categoria not in CATEGORIAS_FORA_DO_GASTO]
CATEGORIAS_ESCOLHA_CREDITO = CATEGORIAS_ESCOLHA + [PAGAMENTO]

# Fora do ritmo diário da projeção: cobranças fixas ou que não se repetem por dia.
CATEGORIAS_FORA_DO_RITMO = [ASSINATURAS, ENCARGOS, ESTORNOS]

SUB_ATRASO = 'Multa, juros e IOF por atraso'
SUB_IOF_INTERNACIONAL = 'IOF de compra internacional'
SUB_DELIVERY = 'Delivery'
SUB_USUARIO = 'Classificado por você'

# Regras automáticas, aplicadas ao texto em minúsculas e sem acento.
# Prioritárias: a primeira que casar vale (ex.: Uber One antes de Uber, iFood antes de pizza).
REGRAS_PRIORITARIAS = [
      (r'^iof de compra internacional', ENCARGOS, SUB_IOF_INTERNACIONAL)
    , (r'^(multa|juros|iof|encargos?|mora)\b.*\b(atras|rotativ|fatura|mora)', ENCARGOS, SUB_ATRASO)
    , (r'^(multa|juros|iof|encargos?)\b', ENCARGOS, 'Outros encargos')
    , (r'uber\s*\*?\s*one\b', ASSINATURAS, 'Apps e streaming')
    , (r'ifood\s*club', ASSINATURAS, 'Apps e streaming')
    , (r'spotify|netflix|disney|hbo\s*max|\bmax\.com|prime\s*video|amazon\s*prime|youtube|deezer|globoplay|paramount|crunchyroll|apple\.com|icloud|google\s*one|anthropic|openai|chatgpt', ASSINATURAS, 'Apps e streaming')
    , (r'wellhub|gympass|smart\s*fit|bluefit|\bacademia\b', ASSINATURAS, 'Academia')
    , (r'^ifd\*|ifood|rappi|\bze\s*delivery|aiqfome|uber\s*\*?\s*eats|99\s*food', COMIDA, SUB_DELIVERY)
]

# Gerais: todas são testadas. Se o texto casar regras de categorias diferentes
# ("Supermercado Ipiranga", "Posto Carrefour", "Drogaria Ipiranga"), o app não escolhe: fica a classificar.
REGRAS = [
      (r'farma|drogaria|droga\s*raia|drogasil|pague\s*menos|panvel|hospital|clinica|laborat|odonto|dentista|unimed|psicolog', SAUDE, 'Saúde')
    , (r'\bposto\b|auto\s*posto|combustive|\bipiranga\b|petrobras|\bshell\b', TRANSPORTE, 'Combustível')
    , (r'supermerc|\bmercado\b(?!\s*(pago|livre))|hirota|carrefour|pao\s*de\s*acucar|\bassai\b|atacad|cerealista|hortifruti|sacolao|padaria|panificadora|emporio|st\s*marche|\bdia\s*brasil', COMIDA, 'Mercado e padaria')
    , (r'restaurante|\brest\b|lanchonete|\blanches?\b|burger|hamburg|pizza|churrasc|sushi|temaki|pastel|\bcafe\b|cafeteria|coffee|starbucks|mc\s*donald|subway|habib|outback|madero|spoleto|giraffas|\bbar\b|boteco|choperia|cervejaria|doceria|confeitaria|sorvete|\bacai\b|padoca', COMIDA, 'Restaurantes e lanches')
    # "estacion", não "estacio": "Universidade Estacio" não é estacionamento. Sem "park" solto ("Park Shopping").
    , (r'estacion|parking|zona\s*azul|estapar|multipark', TRANSPORTE, 'Estacionamento')
    , (r'pedagio|sem\s*parar|conectcar|veloe|taggy', TRANSPORTE, 'Pedágio e tag')
    , (r'\buber\b|^99\s*(app|pop|taxi)|^99\*|cabify|indrive|\btaxi\b', TRANSPORTE, 'Apps de corrida')
    , (r'\bmetro\b|\bcptm\b|sptrans|bilhete\s*unico|onibus', TRANSPORTE, 'Transporte público')
    , (r'\blocaliza\b|\bmovida\b|\bunidas\s*(rent|aluguel|locad)', TRANSPORTE, 'Aluguel de carro')
    , (r'airbnb|booking\.com|hotel|hostel|pousada|decolar|latam|voegol|gol\s*linhas|azul\s*linhas|voeazul|123\s*milhas|maxmilhas|smiles', VIAGEM, 'Viagem')
    , (r'steam|playstation|\bpsn\b|xbox|nintendo|epic\s*games|riot\s*games|blizzard|nuuvem', JOGOS, 'Jogos')
    , (r'amazon|mercado\s*livre|mercadolivre|shopee|aliexpress|shein|magalu|magazine\s*luiza|americanas|casas\s*bahia|centauro|netshoes|renner|riachuelo|\bzara\b|decathlon|kabum|leroy|ikea|tok\s*stok|boticario|sephora', COMPRAS, 'Compras')
    , (r'cinema|cinemark|kinoplex|ingresso|sympla|eventim|teatro', LAZER, 'Lazer')
    , (r'\bvivo\b|\bclaro\b|\btim\b|\benel\b|sabesp|comgas|cemig|copel|sanepar|condominio|aluguel', CASA, 'Casa e contas')
]

REGRA_PAGAMENTO = r'^pagamento\b'
REGRA_SALDO_ANTERIOR = r'valor pendente|saldo\s+(em\s+atraso|anterior|restante)|fatura\s+anterior'
REGRA_ESTORNO = r'^(estorno|credito|reembolso)\b'
REGRA_ENCARGO = r'^(multa|juros|iof|encargos?|mora)\b'
SUB_CONFLITO = 'Mais de uma categoria possível'

# Só o cabeçalho da fatura do cartão. O extrato da conta (Data, Valor, Descrição) tem o sinal
# invertido (gasto negativo) e não pode ser lido como se fosse fatura.
NOMES_COLUNAS = {
      'date': 'data'
    , 'title': 'descricao'
    , 'amount': 'valor'
}


def normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto))
    texto = ''.join(letra for letra in texto if not unicodedata.combining(letra))
    texto = re.sub(r'\s+', ' ', texto.lower())
    return texto.strip()


def remover_parcela(texto):
    return re.sub(r'\s*-?\s*parcela\s+\d+\s*/\s*\d+\s*$', '', texto, flags=re.IGNORECASE).strip()


def chave_estabelecimento(descricao):
    # Mesma chave para "Emv Metrô*155644835" e "Emv Metrô*155626502", e sem o "Parcela x/y".
    texto = normalizar(remover_parcela(descricao))
    texto = re.sub(r'[\s*#-]*\d{5,}$', '', texto)
    return texto.strip()


def nome_estabelecimento(descricao):
    texto = remover_parcela(str(descricao).strip())
    texto = re.sub(r'[\s*#-]*\d{5,}$', '', texto)
    return texto.strip()


def extrair_parcela(descricao):
    achado = re.search(r'parcela\s+(\d+)\s*/\s*(\d+)\s*$', str(descricao), flags=re.IGNORECASE)
    if achado is None:
        return None, None
    return int(achado.group(1)), int(achado.group(2))


def reais(centavos):
    sinal = '-' if centavos < 0 else ''
    centavos = abs(int(centavos))
    inteiro = f'{centavos // 100:,}'.replace(',', '.')
    return f'{sinal}R$ {inteiro},{centavos % 100:02d}'


def dividir_arredondando(numerador, denominador):
    resultado = (Decimal(numerador) / Decimal(denominador)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return int(resultado)


# ---------------------------------------------------------------- leitura

def limpar_valor(texto):
    texto = str(texto).strip().replace('R$', '').replace('−', '-')
    return re.sub(r'\s+', '', texto)


def valor_em_centavos(texto, formato_br):
    # formato_br: ponto separa milhar e vírgula separa centavos ("1.234,56").
    # Senão o ponto separa centavos ("1234.56"). Qualquer outra forma é erro.
    if formato_br:
        achado = re.fullmatch(r'([+-]?)(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?', texto)
    else:
        achado = re.fullmatch(r'([+-]?)(\d+)(?:\.(\d{1,2}))?', texto)
    if achado is None:
        return None
    inteiro = int(achado.group(2).replace('.', ''))
    decimais = (achado.group(3) or '') + '00'
    centavos = inteiro * 100 + int(decimais[:2])
    if achado.group(1) == '-':
        centavos = -centavos
    return centavos


def ler_data(texto):
    texto = str(texto).strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', texto):
        return date.fromisoformat(texto)
    achado = re.fullmatch(r'(\d{2})/(\d{2})/(\d{4})', texto)
    if achado:
        return date(int(achado.group(3)), int(achado.group(2)), int(achado.group(1)))
    raise ValueError(texto)


def decodificar(conteudo):
    if isinstance(conteudo, str):
        return conteudo.lstrip('﻿')
    try:
        return conteudo.decode('utf-8-sig')
    except UnicodeDecodeError:
        pass
    try:
        return conteudo.decode('cp1252')
    except UnicodeDecodeError:
        raise ValueError(
            'Não consegui ler o texto do arquivo (ele não está em UTF-8 nem em Windows-1252). '
            + 'Exporte o CSV de novo pelo Nubank, sem abrir e salvar em outro programa.'
        ) from None


def ler_csv(conteudo):
    texto = decodificar(conteudo)
    linhas_texto = texto.splitlines()
    if not linhas_texto or not linhas_texto[0].strip():
        raise ValueError('O arquivo está vazio.')

    cabecalho = linhas_texto[0]
    separador = ','
    if cabecalho.count(';') > cabecalho.count(','):
        separador = ';'

    leitor = csv.reader(io.StringIO(texto), delimiter=separador)
    try:
        linhas = list(leitor)
    except csv.Error as erro:
        # csv.Error não é ValueError: sem isto, uma aspa sem fechar derrubaria o app.
        raise ValueError(f'O arquivo não é um CSV válido ({erro}).') from None

    colunas = []
    for nome in linhas[0]:
        colunas.append(NOMES_COLUNAS.get(normalizar(nome), None))
    faltando = []
    for necessaria in ['data', 'descricao', 'valor']:
        if colunas.count(necessaria) == 0:
            faltando.append(necessaria)
    if faltando:
        raise ValueError(
            'Este CSV não parece uma fatura de cartão do Nubank: '
            + 'esperava as colunas date, title e amount, mas o cabeçalho é: '
            + ', '.join(linhas[0])
        )
    for necessaria in ['data', 'descricao', 'valor']:
        if colunas.count(necessaria) > 1:
            raise ValueError(f'O cabeçalho tem mais de uma coluna para {necessaria}: ' + ', '.join(linhas[0]))
    posicao_data = colunas.index('data')
    posicao_descricao = colunas.index('descricao')
    posicao_valor = colunas.index('valor')

    registros = []
    for numero, campos in enumerate(linhas[1:], start=2):
        if len(campos) == 0 or all(campo.strip() == '' for campo in campos):
            continue
        if len(campos) != len(linhas[0]):
            raise ValueError(f'linha {numero}: esperava {len(linhas[0])} campos e veio {len(campos)}.')
        registros.append([numero, campos[posicao_data], campos[posicao_descricao], limpar_valor(campos[posicao_valor])])

    if not registros:
        raise ValueError('O arquivo não tem lançamentos.')

    formato_br = False
    for registro in registros:
        if ',' in registro[3]:
            formato_br = True

    erros = []
    dados = []
    for numero, texto_data, descricao, texto_valor in registros:
        try:
            data = ler_data(texto_data)
        except ValueError:
            erros.append(f'linha {numero}: data "{texto_data}" não reconhecida')
            continue
        centavos = valor_em_centavos(texto_valor, formato_br)
        if centavos is None:
            erros.append(f'linha {numero}: valor "{texto_valor}" não reconhecido')
            continue
        if descricao.strip() == '':
            erros.append(f'linha {numero}: lançamento sem descrição')
            continue
        dados.append([numero, pd.Timestamp(data), descricao.strip(), centavos])

    if erros:
        raise ValueError('Não consegui ler o arquivo sem risco de errar valores. ' + '; '.join(erros[:10]))

    df = pd.DataFrame(dados, columns=['linha', 'data', 'descricao', 'centavos'])
    df['centavos'] = df['centavos'].astype('int64')
    return df


def vencimento_do_nome(nome_arquivo):
    achado = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(nome_arquivo))
    if achado is None:
        return None
    try:
        return date(int(achado.group(1)), int(achado.group(2)), int(achado.group(3)))
    except ValueError:
        return None


# ---------------------------------------------------------------- classificação

def classificar_por_regras(texto):
    # Devolve (categoria, subcategoria); (None, None) sem regra; A classificar se as regras discordam.
    for padrao, categoria, subcategoria in REGRAS_PRIORITARIAS:
        if re.search(padrao, texto):
            return categoria, subcategoria
    achados = []
    categorias = []
    for padrao, categoria, subcategoria in REGRAS:
        if re.search(padrao, texto):
            achados.append((categoria, subcategoria))
            if categoria not in categorias:
                categorias.append(categoria)
    if len(achados) == 0:
        return None, None
    if len(categorias) > 1:
        return A_CLASSIFICAR, SUB_CONFLITO
    return achados[0]


def e_estorno(descricao, centavos):
    return centavos < 0 and re.search(REGRA_ESTORNO, normalizar(descricao)) is not None


def texto_original_do_estorno(texto):
    achado = re.search(r'\(([^)]*)\)', texto)
    if achado:
        return achado.group(1).strip()
    texto = re.sub(r'^(estorno|credito|reembolso)\b(\s+de\s+compra)?(\s+(de|do|da))?[\s:-]*', '', texto)
    return texto.strip()


def classificar(descricao, centavos, regras_usuario=None):
    # Devolve (categoria, subcategoria, origem). origem: 'você', 'regra' ou 'sem regra'.
    chave = chave_estabelecimento(descricao)
    if regras_usuario and chave in regras_usuario:
        escolhida = regras_usuario[chave]
        # "Pagamento" escolhido para um crédito não pode tirar do gasto uma compra do mesmo estabelecimento.
        if escolhida not in CATEGORIAS_FORA_DO_GASTO or centavos < 0:
            return escolhida, SUB_USUARIO, 'você'

    texto = normalizar(descricao)
    if centavos < 0 and re.search(REGRA_PAGAMENTO, texto):
        return PAGAMENTO, PAGAMENTO, 'regra'

    if e_estorno(descricao, centavos):
        # "Estorno de compra (iFood)", "Estorno de juros por fatura atrasada":
        # volta para a categoria da cobrança original, inclusive escolhida por você.
        origem_estorno = texto_original_do_estorno(texto)
        if re.search(REGRA_SALDO_ANTERIOR, origem_estorno) and not re.search(REGRA_ENCARGO, origem_estorno):
            return SALDO_ANTERIOR, SALDO_ANTERIOR, 'regra'
        if regras_usuario and chave_estabelecimento(origem_estorno) in regras_usuario:
            return regras_usuario[chave_estabelecimento(origem_estorno)], SUB_USUARIO, 'você'
        categoria, subcategoria = classificar_por_regras(origem_estorno)
        if categoria is None:
            return ESTORNOS, 'Estornos e créditos', 'regra'
        if categoria == A_CLASSIFICAR:
            return A_CLASSIFICAR, subcategoria, 'sem regra'
        return categoria, subcategoria, 'regra'

    # Saldo anterior pode ser devedor (positivo) ou credor (negativo): nos dois casos não é gasto.
    # "Juros da fatura anterior" é encargo, não saldo.
    if re.search(REGRA_SALDO_ANTERIOR, texto) and not re.search(REGRA_ENCARGO, texto):
        return SALDO_ANTERIOR, SALDO_ANTERIOR, 'regra'

    categoria, subcategoria = classificar_por_regras(texto)
    if categoria is None:
        return A_CLASSIFICAR, A_CLASSIFICAR, 'sem regra'
    if categoria == A_CLASSIFICAR:
        return A_CLASSIFICAR, subcategoria, 'sem regra'
    return categoria, subcategoria, 'regra'


def montar_fatura(df, regras_usuario=None):
    linhas = []
    for item in df.itertuples(index=False):
        categoria, subcategoria, origem = classificar(item.descricao, item.centavos, regras_usuario)
        parcela_atual, parcela_total = extrair_parcela(item.descricao)
        linhas.append([
              item.linha
            , item.data
            , item.descricao
            , item.centavos
            , categoria
            , subcategoria
            , origem
            , parcela_atual
            , parcela_total
            , chave_estabelecimento(item.descricao)
            , nome_estabelecimento(item.descricao)
        ])
    fatura = pd.DataFrame(
          linhas
        , columns=[
              'linha', 'data', 'descricao', 'centavos', 'categoria', 'subcategoria', 'origem'
            , 'parcela_atual', 'parcela_total', 'chave', 'estabelecimento'
        ]
    )
    fatura['parcela_atual'] = fatura['parcela_atual'].astype('Int64')
    fatura['parcela_total'] = fatura['parcela_total'].astype('Int64')
    fatura['conta_no_gasto'] = ~fatura['categoria'].isin(CATEGORIAS_FORA_DO_GASTO)
    estornos = []
    for item in fatura.itertuples(index=False):
        estornos.append(e_estorno(item.descricao, item.centavos) or item.categoria == ESTORNOS)
    fatura['estorno'] = estornos
    fatura = fatura.sort_values(['data', 'linha']).reset_index(drop=True)
    return fatura


# ---------------------------------------------------------------- regras do usuário

def carregar_regras_usuario(caminho):
    # Devolve (regras, erro). Com erro, as regras do arquivo não são usadas e o app não grava por cima.
    if not os.path.exists(caminho):
        return {}, None
    try:
        with open(caminho, encoding='utf-8') as arquivo:
            conteudo = json.load(arquivo)
    except (OSError, ValueError) as erro:
        return {}, f'Não consegui ler {caminho}: {erro}'
    if not isinstance(conteudo, dict):
        return {}, f'{caminho} deveria conter um objeto JSON {{"estabelecimento": "categoria"}}.'
    regras = {}
    invalidas = []
    for chave, categoria in conteudo.items():
        if not isinstance(chave, str) or categoria not in CATEGORIAS:
            invalidas.append(str(chave))
            continue
        # A chave já foi gravada pronta; só normalizar (idempotente), sem recalcular a chave.
        regras[normalizar(chave)] = categoria
    if invalidas:
        return {}, f'{caminho} tem categorias desconhecidas em: ' + ', '.join(invalidas[:10])
    return regras, None


def salvar_regras_usuario(caminho, regras):
    pasta = os.path.dirname(os.path.abspath(caminho))
    os.makedirs(pasta, exist_ok=True)
    temporario = caminho + '.tmp'
    with open(temporario, 'w', encoding='utf-8') as arquivo:
        json.dump(dict(sorted(regras.items())), arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


def aplicar_escolha(regras, descricao, centavos, categoria):
    # Grava a escolha do usuário; se ela é igual ao que o app daria sem essa escolha, remove a exceção.
    # "Sem essa escolha" inclui as outras regras do usuário (ex.: estorno de um estabelecimento classificado).
    novas = dict(regras)
    chave = chave_estabelecimento(descricao)
    sem_esta = dict(regras)
    sem_esta.pop(chave, None)
    automatica = classificar(descricao, centavos, sem_esta)[0]
    if categoria == automatica:
        novas.pop(chave, None)
    else:
        novas[chave] = categoria
    return novas


# ---------------------------------------------------------------- resumos

def totais(fatura):
    gasto = int(fatura.loc[fatura['conta_no_gasto'], 'centavos'].sum())
    saldo_anterior = int(fatura.loc[fatura['categoria'] == SALDO_ANTERIOR, 'centavos'].sum())
    pagamentos = int(fatura.loc[fatura['categoria'] == PAGAMENTO, 'centavos'].sum())
    return {
          'gasto': gasto
        , 'saldo_anterior': saldo_anterior
        , 'pagamentos': pagamentos
        , 'total_csv': int(fatura['centavos'].sum())
    }


def resumir(gastos, coluna):
    linhas = []
    total_geral = int(gastos['centavos'].sum())
    for nome, grupo in gastos.groupby(coluna, sort=False):
        total = int(grupo['centavos'].sum())
        compras = grupo.loc[grupo['centavos'] > 0, 'centavos']
        quantidade = int(len(compras))
        media = None
        if quantidade > 0:
            media = dividir_arredondando(int(compras.sum()), quantidade)
        percentual = None
        if total_geral > 0:
            percentual = total * 100 / total_geral
        linhas.append([nome, total, percentual, quantidade, media])
    resumo = pd.DataFrame(linhas, columns=[coluna, 'centavos', 'percentual', 'compras', 'media_centavos'])
    return resumo.sort_values('centavos', ascending=False).reset_index(drop=True)


def resumo_categorias(fatura):
    return resumir(fatura[fatura['conta_no_gasto']], 'categoria')


def resumo_subcategorias(fatura, categoria):
    return resumir(fatura[fatura['conta_no_gasto'] & (fatura['categoria'] == categoria)], 'subcategoria')


def top_estabelecimentos(fatura, quantidade=10):
    gastos = fatura[fatura['conta_no_gasto']]
    linhas = []
    for chave, grupo in gastos.groupby('chave', sort=False):
        linhas.append([
              grupo['estabelecimento'].iloc[0]
            , grupo['categoria'].iloc[0]
            , int(grupo['centavos'].sum())
            , int((grupo['centavos'] > 0).sum())
        ])
    resumo = pd.DataFrame(linhas, columns=['estabelecimento', 'categoria', 'centavos', 'compras'])
    resumo = resumo.sort_values(['centavos', 'estabelecimento'], ascending=[False, True])
    return resumo.head(quantidade).reset_index(drop=True)


def parcelas_futuras(fatura):
    # Supõe parcelas iguais (a última pode diferir por centavos).
    parceladas = fatura[
          fatura['conta_no_gasto']
        & fatura['parcela_total'].notna()
        & (fatura['centavos'] > 0)
    ].copy()
    parceladas = parceladas[parceladas['parcela_atual'] < parceladas['parcela_total']]
    parceladas['restantes'] = (parceladas['parcela_total'] - parceladas['parcela_atual']).astype('int64')
    parceladas['centavos_futuros'] = parceladas['restantes'] * parceladas['centavos']
    return parceladas[['data', 'estabelecimento', 'categoria', 'parcela_atual', 'parcela_total', 'centavos', 'restantes', 'centavos_futuros']].reset_index(drop=True)


def somar_meses(dia, meses):
    # Mesmo dia do mês, N meses depois (ou antes, se negativo); 31/01 + 1 mês = 28/02 ou 29/02.
    indice = dia.year * 12 + (dia.month - 1) + meses
    ano = indice // 12
    mes = indice % 12 + 1
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia.day, ultimo))


def subtrair_um_mes(dia):
    return somar_meses(dia, -1)


MESES_ABREVIADOS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']


def nome_mes(dia):
    return f'{MESES_ABREVIADOS[dia.month - 1]}/{dia.year}'


def parcelas_por_mes(fatura, vencimento=None):
    # Quanto das próximas faturas já está comprometido com as parcelas desta.
    # Uma compra na parcela 3/10 cai nas 7 faturas seguintes; supõe parcelas de mesmo valor.
    futuras = parcelas_futuras(fatura)
    por_ordem = {}
    for item in futuras.itertuples(index=False):
        for ordem in range(1, int(item.restantes) + 1):
            centavos, compras = por_ordem.get(ordem, (0, 0))
            por_ordem[ordem] = (centavos + int(item.centavos), compras + 1)
    linhas = []
    for ordem in sorted(por_ordem):
        centavos, compras = por_ordem[ordem]
        vence = None
        rotulo = f'Daqui a {ordem} fatura(s)'
        if vencimento is not None:
            vence = somar_meses(vencimento, ordem)
            rotulo = nome_mes(vence)
        linhas.append([ordem, vence, rotulo, centavos, compras])
    return pd.DataFrame(linhas, columns=['ordem', 'vencimento', 'fatura', 'centavos', 'compras'])


def melhor_dia_de_compra(vencimento, fechamento, hoje):
    # Nubank: compra feita no dia do fechamento já vai para a fatura seguinte, então esse é o melhor dia.
    # Devolve o próximo fechamento a partir de hoje, o vencimento em que essa compra cai e o prazo,
    # comparados com comprar na véspera. O fechamento de cada mês fica à mesma distância do vencimento
    # daquele mês (como em ciclo()): com vencimento dia 5, o fechamento cai no mês anterior.
    antecedencia = vencimento - fechamento

    def fechamento_do_mes(meses):
        return somar_meses(vencimento, meses) - antecedencia

    meses = 0
    while fechamento_do_mes(meses) < hoje:
        meses = meses + 1
    while fechamento_do_mes(meses - 1) >= hoje:
        meses = meses - 1
    dia = fechamento_do_mes(meses)
    vence = somar_meses(vencimento, meses + 1)
    vespera = dia - timedelta(days=1)
    vence_vespera = somar_meses(vencimento, meses)
    return {
          'dia': dia
        , 'vencimento': vence
        , 'prazo_dias': (vence - dia).days
        , 'vespera': vespera
        , 'vencimento_vespera': vence_vespera
        , 'prazo_vespera_dias': (vence_vespera - vespera).days
    }


MOVIMENTO = 'Movimento da fatura'
ESTORNO = 'Estorno'
ENCARGO = 'Encargo'
PARCELADO = 'Parcelado'
RECORRENTE = 'Recorrente'
OCASIONAL = 'Ocasional'
COMPORTAMENTOS = [RECORRENTE, PARCELADO, OCASIONAL, ENCARGO, ESTORNO, MOVIMENTO]


def comportamentos(fatura, pares_recorrentes):
    # Tipo de comportamento de cada lançamento, separado da categoria (o "o quê" x o "como").
    # pares_recorrentes: {(chave, centavos)} das cobranças fixas detectadas (tabela de fixos).
    tipos = []
    for item in fatura.itertuples(index=False):
        if not item.conta_no_gasto:
            tipos.append(MOVIMENTO)
        elif item.estorno:
            tipos.append(ESTORNO)
        elif item.categoria == ENCARGOS:
            tipos.append(ENCARGO)
        elif pd.notna(item.parcela_total):
            tipos.append(PARCELADO)
        elif (item.chave, int(item.centavos)) in pares_recorrentes:
            tipos.append(RECORRENTE)
        else:
            tipos.append(OCASIONAL)
    return pd.Series(tipos, index=fatura.index, name='comportamento')


def resumo_comportamentos(fatura, tipos):
    # Total por comportamento no gasto do período (movimentos da fatura não são gasto).
    gasto = totais(fatura)['gasto']
    linhas = []
    for tipo in COMPORTAMENTOS:
        if tipo == MOVIMENTO:
            continue
        do_tipo = fatura[fatura['conta_no_gasto'] & (tipos == tipo)]
        if len(do_tipo) == 0:
            continue
        total = int(do_tipo['centavos'].sum())
        percentual = None
        if gasto > 0:
            percentual = total * 100 / gasto
        linhas.append([tipo, total, percentual, int(len(do_tipo))])
    return pd.DataFrame(linhas, columns=['comportamento', 'centavos', 'percentual', 'lancamentos'])


def gastinhos(fatura):
    # Compras do dia a dia (o mesmo conjunto do ritmo: sem parcelas, assinaturas, encargos e estornos).
    # "Pequena" = até a mediana dos próprios valores (a mediana inferior, que é o valor de uma compra real).
    compras = fatura[no_ritmo(fatura) & (fatura['centavos'] > 0)]
    if len(compras) < 2:
        return None
    valores = sorted(int(valor) for valor in compras['centavos'])
    corte = valores[(len(valores) - 1) // 2]
    pequenas = compras[compras['centavos'] <= corte]
    total = int(pequenas['centavos'].sum())
    gasto = totais(fatura)['gasto']
    percentual = None
    if gasto > 0:
        percentual = total * 100 / gasto
    linhas = []
    for chave, grupo in pequenas.groupby('chave', sort=False):
        linhas.append([grupo['estabelecimento'].iloc[0], grupo['categoria'].iloc[0], int(len(grupo)), int(grupo['centavos'].sum())])
    lugares = pd.DataFrame(linhas, columns=['estabelecimento', 'categoria', 'compras', 'centavos'])
    lugares = lugares.sort_values(['centavos', 'compras', 'estabelecimento'], ascending=[False, False, True]).reset_index(drop=True)
    return {
          'corte': corte
        , 'quantidade': int(len(pequenas))
        , 'total_compras': int(len(compras))
        , 'centavos': total
        , 'percentual_do_gasto': percentual
        , 'lugares': lugares
    }


def ciclo(vencimento, fechamento=None):
    # Nubank: fecha 7 dias antes do vencimento; compras do dia do fechamento já vão para a próxima.
    # O ciclo começa no fechamento anterior, que fica à mesma distância do vencimento anterior.
    if fechamento is None:
        fechamento = vencimento - timedelta(days=7)
    inicio = subtrair_um_mes(vencimento) - (vencimento - fechamento)
    ultimo_dia = fechamento - timedelta(days=1)
    return {'inicio': inicio, 'ultimo_dia': ultimo_dia, 'fechamento': fechamento, 'vencimento': vencimento}


def no_ritmo(fatura):
    return (
          fatura['conta_no_gasto']
        & fatura['parcela_total'].isna()
        & ~fatura['estorno']
        & ~fatura['categoria'].isin(CATEGORIAS_FORA_DO_RITMO)
    )


def repartir(total, partes, denominador):
    # Divide numerador/denominador de cada parte, com a soma igual a total (maiores restos ganham o centavo).
    inteiros = []
    restos = []
    for numerador in partes:
        inteiros.append(numerador // denominador)
        restos.append(numerador % denominador)
    falta = total - sum(inteiros)
    ordem = sorted(range(len(partes)), key=restos.__getitem__, reverse=True)
    for posicao in ordem[:max(falta, 0)]:
        inteiros[posicao] = inteiros[posicao] + 1
    return inteiros


def projecao(fatura, inicio, ultimo_dia, hoje):
    # Projeção linear: gasto do dia a dia por dia decorrido, vezes os dias que faltam.
    if ultimo_dia < inicio:
        raise ValueError('O último dia de compras é anterior ao início do ciclo.')
    dias_total = (ultimo_dia - inicio).days + 1
    referencia = min(hoje, ultimo_dia)
    if referencia < inicio:
        return None
    dias_decorridos = (referencia - inicio).days + 1
    dias_restantes = dias_total - dias_decorridos

    # Só entra o que aconteceu até "hoje": lançamentos depois dessa data não são contados duas vezes.
    datas = fatura['data'].dt.date
    ate_hoje = datas <= hoje
    janela = no_ritmo(fatura) & (datas >= inicio) & (datas <= referencia)
    gasto_ate_hoje = fatura['conta_no_gasto'] & ate_hoje
    ritmo_total = int(fatura.loc[janela, 'centavos'].sum())
    atual_total = int(fatura.loc[gasto_ate_hoje, 'centavos'].sum())
    fatura_atual = int(fatura.loc[ate_hoje, 'centavos'].sum())
    # O pagamento quita a fatura anterior. Ele só entra na conta desta fatura quando o saldo que ele quita
    # também está no arquivo (linha de saldo anterior, que o banco lança quando a fatura não foi paga em dia).
    # Sem essa linha, descontar o pagamento deixaria a fatura estimada menor do que o gasto, até negativa.
    tem_saldo_anterior = bool((ate_hoje & (fatura['categoria'] == SALDO_ANTERIOR)).any())
    pagamentos_fora = 0
    if not tem_saldo_anterior:
        pagamentos_fora = int(fatura.loc[ate_hoje & (fatura['categoria'] == PAGAMENTO), 'centavos'].sum())
        fatura_atual = fatura_atual - pagamentos_fora
    a_mais_total = dividir_arredondando(ritmo_total * dias_restantes, dias_decorridos)

    nomes = []
    atuais = []
    numeradores = []
    for categoria in CATEGORIAS:
        if categoria in CATEGORIAS_FORA_DO_GASTO:
            continue
        da_categoria = gasto_ate_hoje & (fatura['categoria'] == categoria)
        if not da_categoria.any():
            continue
        nomes.append(categoria)
        atuais.append(int(fatura.loc[da_categoria, 'centavos'].sum()))
        numeradores.append(int(fatura.loc[janela & da_categoria, 'centavos'].sum()) * dias_restantes)
    a_mais_categorias = repartir(a_mais_total, numeradores, dias_decorridos)

    linhas = []
    for posicao in range(len(nomes)):
        linhas.append([nomes[posicao], atuais[posicao], a_mais_categorias[posicao], atuais[posicao] + a_mais_categorias[posicao]])
    por_categoria = pd.DataFrame(linhas, columns=['categoria', 'centavos_atual', 'centavos_a_mais', 'centavos_projetado'])
    por_categoria = por_categoria.sort_values('centavos_projetado', ascending=False, kind='stable').reset_index(drop=True)

    return {
          'dias_total': dias_total
        , 'dias_decorridos': dias_decorridos
        , 'dias_restantes': dias_restantes
        , 'ritmo_diario': dividir_arredondando(ritmo_total, dias_decorridos)
        , 'atual': atual_total
        , 'a_mais': a_mais_total
        , 'projetado': atual_total + a_mais_total
        , 'fatura_atual': fatura_atual
        , 'fatura_estimada': fatura_atual + a_mais_total
        , 'pagamentos_fora': pagamentos_fora
        , 'depois_de_hoje': int((~ate_hoje).sum())
        , 'por_categoria': por_categoria
    }


BARRA = chr(92)
CARACTERES_MARKDOWN = BARRA + '`*_{}[]<>()#+!|~$'


def escapar_markdown(texto):
    # Texto que vai para st.markdown: "$" viraria fórmula e "*" viraria negrito.
    resultado = ''
    for letra in str(texto):
        if letra in CARACTERES_MARKDOWN:
            resultado = resultado + BARRA + letra
        else:
            resultado = resultado + letra
    return resultado


def reais_md(centavos):
    return escapar_markdown(reais(centavos))


def destaques(fatura):
    frases = []
    valores = totais(fatura)
    gasto = valores['gasto']
    categorias = resumo_categorias(fatura)
    categorias_conhecidas = categorias[~categorias['categoria'].isin([A_CLASSIFICAR, ESTORNOS, OUTROS])]

    if gasto > 0 and len(categorias_conhecidas) > 0:
        maior = categorias_conhecidas.iloc[0]
        frases.append(
            f'**{escapar_markdown(maior["categoria"])}** é onde mais vai dinheiro: {reais_md(maior["centavos"])} '
            + f'({maior["percentual"]:.0f}% do gasto do período).'
        )
        a_classificar = int(fatura.loc[fatura['categoria'] == A_CLASSIFICAR, 'centavos'].sum())
        if a_classificar > int(maior['centavos']):
            frases[-1] = frases[-1] + f' Mas há {reais_md(a_classificar)} a classificar, o que pode mudar isso.'

    for categoria in [TRANSPORTE, COMIDA]:
        sub = resumo_subcategorias(fatura, categoria)
        if len(sub) > 1:
            principal = sub.iloc[0]
            frases.append(
                f'Em {categoria.lower()}, o que mais pesa é **{principal["subcategoria"].lower()}**: '
                + f'{reais_md(principal["centavos"])} de {reais_md(int(sub["centavos"].sum()))}.'
            )

    delivery = fatura[fatura['conta_no_gasto'] & (fatura['subcategoria'] == SUB_DELIVERY)]
    pedidos = delivery[delivery['centavos'] > 0]
    if len(pedidos) > 0:
        frases.append(
            f'**{len(pedidos)} pedidos de delivery** somam {reais_md(int(pedidos["centavos"].sum()))} '
            + f'(média de {reais_md(dividir_arredondando(int(pedidos["centavos"].sum()), len(pedidos)))} por pedido).'
        )

    atraso = int(fatura.loc[fatura['subcategoria'] == SUB_ATRASO, 'centavos'].sum())
    if atraso > 0:
        frases.append(f'Você pagou **{reais_md(atraso)} de multa, juros e IOF por atraso**: é gasto que some pagando a fatura em dia.')

    iof = int(fatura.loc[fatura['subcategoria'] == SUB_IOF_INTERNACIONAL, 'centavos'].sum())
    if iof > 0:
        frases.append(f'{reais_md(iof)} de IOF em compras internacionais.')

    assinaturas = fatura[fatura['conta_no_gasto'] & (fatura['categoria'] == ASSINATURAS)]
    if len(assinaturas) > 0:
        frases.append(f'Assinaturas somam {reais_md(int(assinaturas["centavos"].sum()))} em {len(assinaturas)} cobranças.')

    futuras = parcelas_futuras(fatura)
    if len(futuras) > 0:
        frases.append(
            f'**{reais_md(int(futuras["centavos_futuros"].sum()))} já estão comprometidos** '
            + f'em parcelas das próximas faturas ({len(futuras)} compras parceladas).'
        )

    top = top_estabelecimentos(fatura, 1)
    if len(top) > 0 and top['centavos'].iloc[0] > 0:
        frases.append(
            f'O lugar onde você mais gastou foi **{escapar_markdown(top["estabelecimento"].iloc[0])}**: '
            + f'{reais_md(int(top["centavos"].iloc[0]))} em {int(top["compras"].iloc[0])} compra(s).'
        )

    sem_categoria = fatura[fatura['categoria'] == A_CLASSIFICAR]
    if len(sem_categoria) > 0:
        frases.append(
            f'{reais_md(int(sem_categoria["centavos"].sum()))} em {len(sem_categoria)} lançamentos ainda estão '
            + '**a classificar**; classifique-os para os totais por categoria ficarem completos.'
        )
    return frases
