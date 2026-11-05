# Gera faturas de cartão 100% fictícias no formato do CSV do Nubank, com um gabarito da categoria certa.
# O perfil (quanto e em quê se gasta) imita uma pessoa real, mas nenhum estabelecimento ou valor é copiado:
# só os textos que o próprio Nubank gera para todo mundo ("Pagamento recebido", "IOF de compra internacional"...).
#
# Uso: py ferramentas/gerar_faturas_sinteticas.py [--meses 13] [--semente 2026] [--saida faturas_sinteticas]
# Mesma semente = mesmas faturas (reprodutível para o trabalho).

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path


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
PAGAMENTO = 'Pagamento da fatura'
SALDO_ANTERIOR = 'Saldo da fatura anterior'

RECORRENTE = 'recorrente'
PARCELADO = 'parcelado'
OCASIONAL = 'ocasional'
ENCARGO = 'encargo'
ESTORNO = 'estorno'
MOVIMENTO = 'movimento da fatura'

# Estabelecimentos fictícios (ou marcas comuns a qualquer pessoa), por categoria: (nome como aparece no Nubank, mínimo, máximo).
# Cerca de um terço tem nome que não entrega a categoria, como acontece na fatura real (pessoa física, "Mp *", "Pag*", "Ec *").
DELIVERY = [
      ('Ifd*Sabor da Vila', 32, 78)
    , ('Ifd*Pizzaria Bella Nap', 45, 95)
    , ('Ifd*Temaki Express', 38, 82)
    , ('Ifd*Marmitaria da Ju', 22, 41)
    , ('Ifd*R. Castanho Lanch', 28, 55)
    , ('Ifd*Doce Encanto Conf', 18, 46)
    , ('Ifd*Burger Station', 34, 69)
    , ('Ifd*M. Oliveira Refei', 24, 48)
]
MERCADO = [
      ('Mercado Bom Preco', 35, 180)
    , ('Carrefour Hiper', 60, 240)
    , ('Hortifruti Verde Vale', 18, 75)
    , ('Padaria Nova Aurora', 9, 38)
    , ('Mercadinho Sao Jorge', 12, 66)
    , ('Emporio Santa Clara', 25, 90)
]
RESTAURANTE = [
      ('Restaurante Tempero Min', 28, 72)
    , ('Cafe Grao Fino', 9, 26)
    , ('Bistro Tres Irmaos', 42, 110)
    , ('Mp *Lanchesdojoca', 14, 35)
    , ('Ec *Cantinadamaria', 19, 48)
    , ('Pag*Paulinhoespetos', 15, 40)
    , ('Jr Alimentos Ltda', 22, 55)
]
POSTO = [
      ('Auto Posto Bandeirante', 120, 235)
    , ('Posto Shell Jardins', 110, 220)
    , ('Rede Duque Combustivei', 115, 230)
    , ('Pag*Abastecebem', 100, 210)
    , ('Ec *Postomorumbi', 105, 215)
]
ESTACIONAMENTO = [
      ('Estapar Shopping Norte', 14, 38)
    , ('Zona Azul Digital', 6, 18)
    , ('Mp *Vagafacil', 15, 45)
    , ('Park Center Estac', 18, 50)
]
CORRIDA = [
      ('Uber Uber *Trip Help.U', 9, 42)
    , ('99app *99app', 8, 36)
    , ('Mp *Corridajoao', 20, 60)
]
OUTRO_TRANSPORTE = [
      ('Sem Parar', 18, 65)
    , ('Lava Rapido Brilho', 35, 70)
    , ('Mp *Mecanicadoze', 120, 420)
]
COMPRAS_LISTA = [
      ('Amazon Marketplace', 35, 260)
    , ('Mercadolivre*Vendedor', 30, 240)
    , ('Shopee *Lojaluz', 18, 120)
    , ('Magalu *Magazine', 60, 320)
    , ('Renner Shopping', 70, 260)
    , ('Decathlon', 60, 300)
    , ('Pag*Lojadosimports', 25, 160)
    , ('Ec *Calcadosvitoria', 90, 280)
    , ('Mp *Bazardaana', 20, 85)
    , ('Comercial Ferreira Ltd', 30, 140)
    , ('Papelaria Alfa', 12, 60)
    , ('Pag*Eletroshop', 80, 350)
]
JOGOS_LISTA = [
      ('Playstation Network', 25, 250)
    , ('Nintendo Eshop', 30, 300)
    , ('Pag*Nuuvem', 20, 120)
    , ('Epic Games Store', 15, 90)
    , ('Riot Games', 20, 80)
    , ('Ec *Gamecentrallan', 15, 45)
    , ('Mp *Lojadegames', 40, 180)
    , ('Pag*Cartasmagicas', 25, 110)
    , ('Google Play Jogos', 9, 50)
]
FARMACIA = [
      ('Drogasil', 15, 90)
    , ('Droga Raia', 12, 80)
    , ('Farmacia Pague Menos', 10, 70)
    , ('Pag*Drogariasaobento', 12, 75)
]
SAUDE_LISTA = [
      ('Clinica Sorriso Odonto', 120, 350)
    , ('Laboratorio Vida', 60, 220)
    , ('Ec *Drricardoalves', 180, 400)
    , ('Mp *Fisiocentro', 90, 180)
    , ('Pag*Psicologaana', 150, 250)
    , ('Otica Visao Clara', 80, 450)
    , ('Pag*Dermacenter', 120, 300)
]
LAZER_LISTA = [
      ('Cinemark', 28, 80)
    , ('Ingresso.Com', 40, 180)
    , ('Sympla *Festival', 60, 220)
    , ('Teatro Municipal', 50, 150)
    , ('Kinoplex', 25, 70)
    , ('Mp *Boliche Strike', 40, 110)
    , ('Pag*Escapemaster', 60, 140)
    , ('Ec *Parquedasaguas', 70, 160)
    , ('Clube Paineiras', 45, 120)
    , ('Pag*Karteindoor', 55, 130)
]
CASA_EXTRA = [
      ('Sabesp Conta', 60, 140)
    , ('Comgas', 35, 95)
    , ('Pag*Condominioipe', 90, 180)
    , ('Mp *Diaristarosa', 120, 180)
    , ('Ec *Chaveirocentral', 25, 90)
    , ('Telhanorte', 30, 220)
    , ('Pag*Gasdojoao', 105, 130)
]
VIAGEM_LISTA = [
      ('Booking.Com', 250, 700)
    , ('Decolar Com', 300, 900)
    , ('Hotel Mar Azul', 220, 600)
    , ('Mp *Pousadaserrana', 180, 520)
    , ('Pag*Turismorota', 90, 300)
    , ('Ec *Rodoviariatiete', 60, 180)
    , ('Buser *Viagem', 70, 190)
    , ('Clickbus', 80, 210)
]

# Assinaturas com valor fixo: (nome, categoria, valor em centavos, dia do mês da cobrança, primeiro mês, último mês).
# Uma tem reajuste no meio do período (mesmo estabelecimento, valor novo); algumas começam ou terminam no período.
ASSINATURAS_FIXAS = [
      ('Netflix.Com', ASSINATURAS, 4490, 6, 0, 99)
    , ('Dl*Deezer Premium', ASSINATURAS, 2290, 11, 0, 6)
    , ('Dl*Deezer Premium', ASSINATURAS, 2490, 11, 7, 99)
    , ('Google One', ASSINATURAS, 999, 14, 0, 99)
    , ('Academia Corpo Ativo', ASSINATURAS, 9990, 2, 0, 99)
    , ('Globoplay', ASSINATURAS, 2790, 20, 0, 4)
    , ('Max.Com', ASSINATURAS, 2990, 22, 5, 99)
    , ('Pag*Clubedovinho', ASSINATURAS, 6900, 9, 3, 10)
    , ('Ec *Revistadigital', ASSINATURAS, 1490, 27, 2, 99)
    , ('Kindle Unltd', ASSINATURAS, 1990, 16, 6, 99)
    , ('Vivo Fibra', CASA, 10990, 8, 0, 99)
]
# Assinatura cobrada em dólar: o valor em reais muda com o câmbio e vem com uma linha de IOF.
ASSINATURA_DOLAR = ('Openai *Chatgpt Subscr', ASSINATURAS, 2000, 3)
IOF_INTERNACIONAL = 0.035
# Conta de consumo: cobrança mensal com valor variável.
ENERGIA = ('Enel Sp Energia', CASA, 9000, 16000, 26)

# Padrão de dia da semana (segunda a domingo), colocado de propósito pelo gerador para o experimento de contexto
# temporal ter o que encontrar: delivery e lazer pesam mais no fim de semana, mercado no sábado, e estacionamento,
# metrô, corridas e restaurante (almoço) nos dias úteis. Numa fatura real esse padrão pode não existir.
PESOS_FIM_DE_SEMANA = [1, 1, 1, 1, 2, 4, 4]
PESOS_SABADO = [1, 1, 1, 1, 1, 3, 2]
PESOS_DIA_UTIL = [3, 3, 3, 3, 3, 1, 0.5]

MESES_ATRASO = {4, 10}
MESES_VIAGEM = {1, 5, 9}
MESES_ESTORNO = {2, 6, 11}


def somar_meses(dia, meses):
    indice = dia.year * 12 + dia.month - 1 + meses
    ano, mes = divmod(indice, 12)
    return date(ano, mes + 1, min(dia.day, 28))


def reais(centavos):
    # Formato do CSV do Nubank: "12,90", "1.234,56", "- 1.234,56".
    sinal = '- ' if centavos < 0 else ''
    centavos = abs(int(centavos))
    inteiro = f'{centavos // 100:,}'.replace(',', '.')
    return f'{sinal}{inteiro},{centavos % 100:02d}'


class Gerador:
    def __init__(self, semente):
        self.sorteio = random.Random(semente)

    def valor(self, minimo, maximo):
        return int(round(self.sorteio.uniform(minimo, maximo) * 100))

    def dia_no_ciclo(self, inicio, fim, pesos=None):
        # pesos: peso de cada dia da semana (segunda = 0). Sem pesos, qualquer dia do ciclo tem a mesma chance.
        dias = []
        for deslocamento in range((fim - inicio).days + 1):
            dias.append(inicio + timedelta(days=deslocamento))
        if pesos is None:
            return self.sorteio.choice(dias)
        return self.sorteio.choices(dias, weights=[pesos[dia.weekday()] for dia in dias])[0]

    def escolher(self, lista, quantidade):
        return [self.sorteio.choice(lista) for _ in range(quantidade)]


def dia_fixo(inicio, fim, dia_do_mes):
    # O dia "d" do mês dentro do ciclo [inicio, fim]: no mês do início se d >= dia do início, senão no mês do fim.
    if dia_do_mes >= inicio.day:
        return date(inicio.year, inicio.month, dia_do_mes)
    return date(fim.year, fim.month, dia_do_mes)


def gerar(meses, semente, primeiro_vencimento):
    gerador = Gerador(semente)
    faturas = []
    parcelas_pendentes = []
    gasto_anterior = 240000
    for posicao in range(meses):
        vencimento = somar_meses(primeiro_vencimento, posicao).replace(day=25)
        inicio = somar_meses(vencimento, -1).replace(day=18)
        fim = vencimento.replace(day=17)
        linhas = []

        def lancar(dia, titulo, centavos, categoria, comportamento):
            linhas.append([dia, titulo, int(centavos), categoria, comportamento])

        def sortear(lista, categoria, quantidade, pesos=None):
            for nome, minimo, maximo in gerador.escolher(lista, quantidade):
                lancar(gerador.dia_no_ciclo(inicio, fim, pesos), nome, gerador.valor(minimo, maximo), categoria, OCASIONAL)

        # Assinaturas e contas fixas.
        for nome, categoria, centavos, dia_do_mes, primeiro, ultimo in ASSINATURAS_FIXAS:
            if primeiro <= posicao <= ultimo:
                lancar(dia_fixo(inicio, fim, dia_do_mes), nome, centavos, categoria, RECORRENTE)
        nome, categoria, dolares, dia_do_mes = ASSINATURA_DOLAR
        cambio = gerador.sorteio.uniform(5.15, 5.75)
        em_reais = int(round(dolares * cambio))
        dia = dia_fixo(inicio, fim, dia_do_mes)
        lancar(dia, nome, em_reais, categoria, RECORRENTE)
        lancar(dia, 'IOF de compra internacional', int(round(em_reais * IOF_INTERNACIONAL)), ENCARGOS, ENCARGO)
        nome, categoria, minimo, maximo, dia_do_mes = ENERGIA
        lancar(dia_fixo(inicio, fim, dia_do_mes), nome, gerador.sorteio.randint(minimo, maximo), categoria, RECORRENTE)

        # Comida e bebida: muito delivery, mercado, padaria e lanches.
        deliveries = []
        for nome, minimo, maximo in gerador.escolher(DELIVERY, gerador.sorteio.randint(4, 7)):
            dia = gerador.dia_no_ciclo(inicio, fim, PESOS_FIM_DE_SEMANA)
            centavos = gerador.valor(minimo, maximo)
            lancar(dia, nome, centavos, COMIDA, OCASIONAL)
            deliveries.append((dia, centavos))
        sortear(MERCADO, COMIDA, gerador.sorteio.randint(2, 4), PESOS_SABADO)
        sortear(RESTAURANTE, COMIDA, gerador.sorteio.randint(1, 3), PESOS_DIA_UTIL)

        # Transporte: combustível (o maior peso), estacionamento, metrô, corridas e um ou outro gasto com o carro.
        sortear(POSTO, TRANSPORTE, gerador.sorteio.choice([2, 3, 3, 3, 4]))
        sortear(ESTACIONAMENTO, TRANSPORTE, gerador.sorteio.randint(2, 4), PESOS_DIA_UTIL)
        for _ in range(gerador.sorteio.randint(2, 6)):
            numero = gerador.sorteio.randint(100000000, 199999999)
            lancar(gerador.dia_no_ciclo(inicio, fim, PESOS_DIA_UTIL), f'Emv Metrô*{numero}', 540, TRANSPORTE, OCASIONAL)
        sortear(CORRIDA, TRANSPORTE, gerador.sorteio.randint(1, 4), PESOS_DIA_UTIL)
        if gerador.sorteio.random() < 0.3:
            sortear(OUTRO_TRANSPORTE, TRANSPORTE, 1)

        # Compras, de vez em quando parceladas.
        sortear(COMPRAS_LISTA, COMPRAS, gerador.sorteio.randint(0, 2))
        if gerador.sorteio.random() < 0.35:
            nome, minimo, maximo = gerador.sorteio.choice(COMPRAS_LISTA)
            vezes = gerador.sorteio.choice([3, 4, 6, 10])
            total = gerador.valor(minimo * 3, maximo * 4)
            parcelas_pendentes.append([nome, COMPRAS, total // vezes, vezes, 1, gerador.dia_no_ciclo(inicio, fim)])

        # Viagem em dois meses: passagem e hospedagem parceladas, mais gastos no destino.
        if posicao % 12 in MESES_VIAGEM:
            for nome, minimo, maximo, vezes in [('Latam Air', 600, 1400, 3), ('Airbnb * Hm' + str(gerador.sorteio.randint(10000, 99999)), 400, 900, 2)]:
                total = gerador.valor(minimo, maximo)
                parcelas_pendentes.append([nome, VIAGEM, total // vezes, vezes, 1, gerador.dia_no_ciclo(inicio, fim)])
            sortear(VIAGEM_LISTA, VIAGEM, gerador.sorteio.randint(2, 4))

        sortear(JOGOS_LISTA, JOGOS, gerador.sorteio.choice([0, 0, 1, 1, 2]))
        sortear(FARMACIA, SAUDE, gerador.sorteio.randint(1, 2))
        if gerador.sorteio.random() < 0.3:
            sortear(SAUDE_LISTA, SAUDE, 1)
        sortear(LAZER_LISTA, LAZER, gerador.sorteio.choice([0, 1, 1, 2]), PESOS_FIM_DE_SEMANA)
        sortear(CASA_EXTRA, CASA, gerador.sorteio.choice([0, 0, 1]))

        # Parcelas: a primeira no dia da compra, as seguintes no primeiro dia do ciclo (como no Nubank).
        restantes = []
        for parcela in parcelas_pendentes:
            nome, categoria, centavos, vezes, atual, dia_compra = parcela
            dia = dia_compra if atual == 1 else inicio
            lancar(dia, f'{nome} - Parcela {atual}/{vezes}', centavos, categoria, PARCELADO)
            if atual < vezes:
                restantes.append([nome, categoria, centavos, vezes, atual + 1, dia_compra])
        parcelas_pendentes = restantes

        # Estorno de um delivery do próprio mês.
        if posicao % 12 in MESES_ESTORNO and deliveries:
            dia, centavos = gerador.sorteio.choice(deliveries)
            lancar(min(dia + timedelta(days=1), fim), 'Estorno de compra (iFood)', -centavos, COMIDA, ESTORNO)

        # Pagamento da fatura anterior; em dois meses, pago com atraso (saldo pendente, multa, juros e IOF).
        dia_pagamento = somar_meses(vencimento, -1).replace(day=25)
        if posicao % 12 in MESES_ATRASO:
            dia_pagamento = dia_pagamento + timedelta(days=gerador.sorteio.randint(2, 5))
            lancar(dia_pagamento - timedelta(days=2), 'Valor pendente do mês anterior', gasto_anterior, SALDO_ANTERIOR, MOVIMENTO)
            lancar(dia_pagamento, 'Multa por fatura atrasada', int(round(gasto_anterior * 0.02)), ENCARGOS, ENCARGO)
            lancar(dia_pagamento, 'Juros por fatura atrasada', int(round(gasto_anterior * 0.0105)), ENCARGOS, ENCARGO)
            lancar(dia_pagamento, 'IOF por fatura atrasada', int(round(gasto_anterior * 0.004)), ENCARGOS, ENCARGO)
        lancar(dia_pagamento, 'Pagamento recebido', -gasto_anterior, PAGAMENTO, MOVIMENTO)

        gasto_anterior = sum(linha[2] for linha in linhas if linha[3] not in [PAGAMENTO, SALDO_ANTERIOR])
        # Ordem do CSV do Nubank: do mais recente para o mais antigo.
        linhas.sort(key=lambda linha: linha[0], reverse=True)
        faturas.append((vencimento, linhas))
    return faturas


def gravar(faturas, saida):
    pasta = Path(saida)
    (pasta / 'faturas').mkdir(parents=True, exist_ok=True)
    gabarito = []
    for vencimento, linhas in faturas:
        nome = f'Nubank_{vencimento.isoformat()}.csv'
        with open(pasta / 'faturas' / nome, 'w', encoding='utf-8', newline='') as arquivo:
            escritor = csv.writer(arquivo, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            escritor.writerow(['date', 'title', 'amount'])
            for dia, titulo, centavos, categoria, comportamento in linhas:
                # O Nubank põe o valor entre aspas por causa da vírgula decimal.
                escritor.writerow([dia.isoformat(), titulo, reais(centavos)])
        for dia, titulo, centavos, categoria, comportamento in linhas:
            gabarito.append([nome, dia.isoformat(), titulo, reais(centavos), categoria, comportamento])
    with open(pasta / 'gabarito.csv', 'w', encoding='utf-8', newline='') as arquivo:
        escritor = csv.writer(arquivo, lineterminator='\n')
        escritor.writerow(['fatura', 'date', 'title', 'amount', 'categoria_certa', 'comportamento'])
        escritor.writerows(gabarito)
    (pasta / 'LEIA-ME.txt').write_text(LEIA_ME, encoding='utf-8')


LEIA_ME = '''FATURAS SINTÉTICAS (100% FICTÍCIAS)

Geradas por ferramentas/gerar_faturas_sinteticas.py, com semente fixa: rodar de novo gera os mesmos arquivos.

faturas/Nubank_AAAA-MM-25.csv
  Mesmo formato do CSV do Nubank (date,title,amount; valores "12,90" e "- 1.234,56"; do mais recente
  para o mais antigo). Abra no app com a base "Faturas simuladas" selecionada.

gabarito.csv
  A categoria certa de cada lançamento (categoria_certa) e o tipo de gasto (comportamento), definidos
  pelo gerador. Serve para avaliar o modelo de classificação sem precisar rotular tudo à mão.

Como foram feitas
  - Perfil de quem gasta mais com comida e transporte (muito delivery, combustível, estacionamento e
    metrô). Nenhum estabelecimento ou valor foi copiado de faturas reais.
    Só se repetem textos que o próprio Nubank gera para todo mundo ("Pagamento recebido", "IOF de compra
    internacional", "Multa por fatura atrasada"...) e o formato das cobranças do Uber e do metrô.
  - Assinaturas com valor fixo (uma com reajuste, algumas canceladas ou contratadas no período), uma
    assinatura em dólar com IOF, conta de energia variável, parcelas, três viagens, três estornos e dois
    meses com pagamento atrasado (multa, juros e IOF).
  - Cerca de um terço dos estabelecimentos tem nome que não entrega a categoria ("Mp *", "Pag*", "Ec *").
  - Padrão de dia da semana COLOCADO PELO GERADOR (por construção): delivery e lazer mais no fim de semana,
    mercado no sábado, estacionamento/metrô/corridas/restaurante nos dias úteis. Serve para testar se o método
    consegue usar o contexto temporal quando ele existe; não é evidência de que pessoas reais tenham esse padrão.

Limitações (para o trabalho)
  - É um único perfil inventado: o modelo pode aprender o jeito do gerador, não o de pessoas reais.
  - As regras do app nunca contradizem o gabarito por construção dos nomes; numa fatura real podem errar.
  - O rótulo é por estabelecimento (cada um sempre na mesma categoria).
  - 13 faturas são poucas para avaliar previsão do fechamento; o gerador aceita --meses para gerar mais.
'''


def main():
    parser = argparse.ArgumentParser(description='Gera faturas Nubank 100% fictícias.')
    parser.add_argument('--meses', type=int, default=13)
    parser.add_argument('--semente', type=int, default=2026)
    parser.add_argument('--saida', default=str(Path(__file__).resolve().parent.parent / 'faturas_sinteticas'))
    parser.add_argument('--primeiro-vencimento', default='2025-10-25')
    argumentos = parser.parse_args()
    faturas = gerar(argumentos.meses, argumentos.semente, date.fromisoformat(argumentos.primeiro_vencimento))
    gravar(faturas, argumentos.saida)
    print(f'{len(faturas)} faturas em {argumentos.saida}')


if __name__ == '__main__':
    main()
