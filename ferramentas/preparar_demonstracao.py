# Prepara a base "Faturas simuladas" do app para uma demonstração, só com faturas 100% fictícias do gerador.
#
# - Guarda no histórico da base simulada as 13 faturas do gerador (13 meses, semente 2026): as 12 primeiras como
#   completas e a última como parcial (guardada antes do fechamento). A última é a que se abre ao vivo no app (ver
#   docs/DEMONSTRACAO.md); por já estar guardada na base simulada, o app a recusa se ela for aberta por engano na
#   base "Minhas faturas".
# - Com --com-rotulos, confere as categorias dos estabelecimentos das primeiras faturas usando o gabarito do
#   gerador (como se a pessoa já tivesse conferido), para a aba Classificar ter sugestões do modelo para mostrar.
# - Nunca sobrescreve nada da base simulada: fatura já guardada com o mesmo vencimento e outro conteúdo, rótulo ou
#   categoria já escolhidos pela pessoa ficam como estão; só o que falta é acrescentado.
# - Nunca toca a base "Minhas faturas": antes de gravar qualquer coisa, recusa se algum arquivo da base simulada for
#   o mesmo de "Minhas faturas" (pelas mesmas regras de caminho do app), e recusa uma fatura que já esteja lá.
#
# Uso: py ferramentas/preparar_demonstracao.py [--com-rotulos] [--pasta PASTA_DA_BASE_SIMULADA]
# Para apresentar sem nenhum risco para os dados reais, use abrir_demonstracao.bat (pasta só da demonstração).

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

PASTA_APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA_APP / 'src'))

import fatura as ft
import historico as hist
import rotulos as rt


ORIGEM_DEMONSTRACAO = 'demonstração: gabarito do gerador'
PRIMEIRO_VENCIMENTO = date(2025, 10, 25)
MESES = 13
SEMENTE = 2026
FATURAS_ROTULADAS = 3
MANTIDA = 'mantida: a base simulada já tem outra fatura com este vencimento'
RECUSADA = 'recusada: já está na base "Minhas faturas"'


def pasta_dados():
    # A mesma pasta que o app usa (%LOCALAPPDATA%\fatura_cartao; fora do Windows, ~/.fatura_cartao).
    if os.environ.get('LOCALAPPDATA'):
        return Path(os.environ['LOCALAPPDATA']) / 'fatura_cartao'
    return Path.home() / '.fatura_cartao'


def caminhos_da_base_minhas():
    # Os arquivos de "Minhas faturas", pelas mesmas regras do app (src/app.py, CAMINHOS).
    dados = pasta_dados()
    rotulos = os.environ.get('FATURA_ROTULOS', str(dados / 'rotulos.json'))
    return {
          'histórico': os.environ.get('FATURA_HISTORICO', str(dados / 'historico'))
        , 'categorias escolhidas': os.environ.get('FATURA_REGRAS', str(PASTA_APP / 'regras_usuario.json'))
        , 'metas': os.environ.get('FATURA_METAS', str(dados / 'metas_usuario.json'))
        , 'rótulos': rotulos
        , 'origem dos rótulos': rt.caminho_origens(rotulos)
        , 'sugestões rejeitadas': os.environ.get('FATURA_REJEITADAS', str(dados / 'sugestoes_rejeitadas.json'))
    }


def caminhos_da_base_simulada(pasta_simuladas):
    # Os arquivos da base simulada, como o app os monta a partir de FATURA_SIMULADAS.
    pasta = Path(pasta_simuladas)
    return {
          'histórico': str(pasta / 'historico')
        , 'categorias escolhidas': str(pasta / 'regras_usuario.json')
        , 'metas': str(pasta / 'metas_usuario.json')
        , 'rótulos': str(pasta / 'rotulos.json')
        , 'origem dos rótulos': rt.caminho_origens(str(pasta / 'rotulos.json'))
        , 'sugestões rejeitadas': str(pasta / 'sugestoes_rejeitadas.json')
    }


def carregar_gerador():
    import importlib.util
    especificacao = importlib.util.spec_from_file_location('gerador', PASTA_APP / 'ferramentas' / 'gerar_faturas_sinteticas.py')
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


def texto_csv(gerador, linhas):
    # O mesmo formato que o gerador grava (CSV do Nubank).
    import csv
    import io
    saida = io.StringIO()
    escritor = csv.writer(saida, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    escritor.writerow(['date', 'title', 'amount'])
    for dia, titulo, centavos, categoria, comportamento in linhas:
        escritor.writerow([dia.isoformat(), titulo, gerador.reais(centavos)])
    return saida.getvalue()


def conferir_caminhos(pasta_simuladas, pasta_minhas, caminhos_minhas):
    # Recusa (antes de gravar qualquer coisa) se algum arquivo da base simulada for o mesmo de "Minhas faturas".
    minhas = dict(caminhos_minhas or {})
    minhas['histórico'] = str(pasta_minhas)
    proibidos = {}
    for nome, caminho in minhas.items():
        proibidos[os.path.normcase(str(Path(caminho).resolve()))] = nome
    for nome, caminho in caminhos_da_base_simulada(pasta_simuladas).items():
        chave = os.path.normcase(str(Path(caminho).resolve()))
        if chave in proibidos:
            raise SystemExit(
                f'Recusado: o arquivo de {nome} da base simulada ({caminho}) é o mesmo de {proibidos[chave]} da base '
                + '"Minhas faturas". Escolha outra pasta para a base simulada; nada foi gravado.'
            )


def preparar(pasta_simuladas, pasta_minhas, com_rotulos, hoje, caminhos_minhas=None):
    conferir_caminhos(pasta_simuladas, pasta_minhas, caminhos_minhas)
    pasta_simuladas = Path(pasta_simuladas)
    pasta_historico = pasta_simuladas / 'historico'
    gerador = carregar_gerador()
    faturas = gerador.gerar(MESES, SEMENTE, PRIMEIRO_VENCIMENTO)
    entradas, erros = hist.carregar_historico(str(pasta_historico))
    guardadas = {entrada['vencimento']: entrada for entrada in entradas}
    resultado = []
    for posicao, (vencimento, linhas) in enumerate(faturas):
        conteudo = texto_csv(gerador, linhas).encode('utf-8')
        if hist.guardada_em(str(pasta_minhas), conteudo) is not None:
            resultado.append((vencimento, RECUSADA))
            continue
        existente = guardadas.get(vencimento)
        if existente is not None and hist.lancamentos(existente['df']) != hist.lancamentos(ft.ler_csv(conteudo)):
            resultado.append((vencimento, MANTIDA))
            continue
        fechamento = vencimento - timedelta(days=7)
        # A última fica parcial: "guardada" no último dia de compras, antes do fechamento.
        quando = hoje if posicao < len(faturas) - 1 else fechamento - timedelta(days=1)
        situacao, mensagem = hist.guardar(str(pasta_historico), conteudo, f'Nubank_{vencimento.isoformat()}.csv', vencimento, fechamento, quando)
        resultado.append((vencimento, situacao))

    if com_rotulos:
        caminho_rotulos = str(pasta_simuladas / 'rotulos.json')
        caminho_regras = str(pasta_simuladas / 'regras_usuario.json')
        rotulos, erro_rotulos = rt.carregar_rotulos(caminho_rotulos)
        regras, erro_regras = ft.carregar_regras_usuario(caminho_regras)
        origens, erro_origens = rt.carregar_origens(rt.caminho_origens(caminho_rotulos))
        if erro_rotulos or erro_regras or erro_origens:
            raise SystemExit('Os arquivos de rótulos ou de categorias da base simulada estão com problema; não gravei nada neles.')
        novos = dict(rotulos)
        novas_regras = dict(regras)
        for vencimento, linhas in faturas[:FATURAS_ROTULADAS]:
            for dia, titulo, centavos, categoria, comportamento in linhas:
                if categoria not in rt.CATEGORIAS_ROTULO or centavos <= 0 or ft.e_estorno(titulo, centavos):
                    continue
                chave = ft.chave_estabelecimento(titulo)
                # O que a pessoa já conferiu ou escolheu nesta base fica como está.
                if chave in novos or chave in regras:
                    continue
                novos[chave] = categoria
                novas_regras = ft.aplicar_escolha(novas_regras, titulo, centavos, categoria)
        acrescentados = [chave for chave in novos if chave not in rotulos]
        origem_por_chave = {chave: ORIGEM_DEMONSTRACAO for chave in acrescentados}
        rt.salvar_rotulos(caminho_rotulos, novos)
        ft.salvar_regras_usuario(caminho_regras, novas_regras)
        rt.salvar_origens(rt.caminho_origens(caminho_rotulos), rt.atualizar_origens(origens, rotulos, novos, origem_por_chave, hoje))
        resultado.append(('rótulos', f'{len(acrescentados)} estabelecimento(s) conferido(s) pelo gabarito; os que já existiam ficaram como estavam'))
    return resultado


def main():
    parser = argparse.ArgumentParser(description='Prepara a base "Faturas simuladas" para uma demonstração (só dados fictícios).')
    parser.add_argument('--com-rotulos', action='store_true', help='Confere as categorias das primeiras faturas pelo gabarito do gerador.')
    parser.add_argument('--pasta', default=os.environ.get('FATURA_SIMULADAS', str(pasta_dados() / 'simuladas')), help='Pasta da base simulada.')
    argumentos = parser.parse_args()
    caminhos_minhas = caminhos_da_base_minhas()
    for item, situacao in preparar(argumentos.pasta, caminhos_minhas['histórico'], argumentos.com_rotulos, date.today(), caminhos_minhas):
        print(item, situacao)
    print('Base simulada pronta em', argumentos.pasta)
    print('Para a demonstração, abra no app (base "Faturas simuladas") o arquivo gerado por')
    print('  py ferramentas/gerar_faturas_sinteticas.py')
    print(f'  faturas_sinteticas/faturas/Nubank_{gerador_ultimo_vencimento().isoformat()}.csv')


def gerador_ultimo_vencimento():
    return ft.somar_meses(PRIMEIRO_VENCIMENTO, MESES - 1)


if __name__ == '__main__':
    main()
