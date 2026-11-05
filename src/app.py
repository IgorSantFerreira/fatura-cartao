# Tela do app. Rodar com abrir_app.bat (ou: py -m streamlit run src/app.py).

import hashlib
import os
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import fatura as ft
import historico as hist
import metas as mt
import rotulos as rt


PASTA_APP = Path(__file__).resolve().parent.parent
# Histórico, metas e rótulos ficam numa pasta local que não sincroniza com a nuvem: a pasta do app está no OneDrive.
# (%LOCALAPPDATA% no Windows; fora dele, ~/.fatura_cartao.)
PASTA_DADOS = Path(os.environ['LOCALAPPDATA']) / 'fatura_cartao' if os.environ.get('LOCALAPPDATA') else Path.home() / '.fatura_cartao'
MINHAS = 'Minhas faturas'
SIMULADAS = 'Faturas simuladas'
# Cada base tem seus próprios arquivos: faturas simuladas (demonstração, treino do ML) nunca se misturam com as reais.
# "Minhas faturas" mantém os caminhos de antes (as categorias escolhidas continuam na pasta do app).
PASTA_SIMULADAS = Path(os.environ.get('FATURA_SIMULADAS', str(PASTA_DADOS / 'simuladas')))
CAMINHOS = {
      MINHAS: {
          'regras': os.environ.get('FATURA_REGRAS', str(PASTA_APP / 'regras_usuario.json'))
        , 'metas': os.environ.get('FATURA_METAS', str(PASTA_DADOS / 'metas_usuario.json'))
        , 'historico': os.environ.get('FATURA_HISTORICO', str(PASTA_DADOS / 'historico'))
        , 'rotulos': os.environ.get('FATURA_ROTULOS', str(PASTA_DADOS / 'rotulos.json'))
      }
    , SIMULADAS: {
          'regras': str(PASTA_SIMULADAS / 'regras_usuario.json')
        , 'metas': str(PASTA_SIMULADAS / 'metas_usuario.json')
        , 'historico': str(PASTA_SIMULADAS / 'historico')
        , 'rotulos': str(PASTA_SIMULADAS / 'rotulos.json')
      }
}
COR_BARRA = '#2a78d6'
VOLTAR_AUTOMATICA = 'Voltar para a categoria automática'
COMIDA_E_TRANSPORTE = [ft.COMIDA, ft.TRANSPORTE]


def tabela_resumo(resumo, coluna, titulo):
    linhas = []
    for item in resumo.itertuples(index=False):
        percentual = '-'
        if pd.notna(item.percentual):
            percentual = f'{item.percentual:.1f}%'.replace('.', ',')
        media = '-'
        if item.media_centavos is not None and pd.notna(item.media_centavos):
            media = ft.reais(int(item.media_centavos))
        linhas.append([getattr(item, coluna), ft.reais(item.centavos), percentual, item.compras, media])
    return pd.DataFrame(linhas, columns=[titulo, 'Total', '% do gasto', 'Compras', 'Valor médio'])


def grafico_barras(resumo, coluna):
    positivos = resumo[resumo['centavos'] > 0].sort_values('centavos')
    dados = pd.DataFrame({
          'nome': positivos[coluna]
        , 'valor': positivos['centavos'] / 100
        , 'texto': [ft.reais(valor) for valor in positivos['centavos']]
    })
    figura = px.bar(
          dados
        , x='valor'
        , y='nome'
        , orientation='h'
        , text='texto'
        , color_discrete_sequence=[COR_BARRA]
        , custom_data=['texto']
    )
    figura.update_traces(
          textposition='outside'
        , cliponaxis=False
        , hovertemplate='%{y}: %{customdata[0]}<extra></extra>'
    )
    figura.update_layout(
          xaxis_title=None
        , yaxis_title=None
        , xaxis_showticklabels=False
        , xaxis_showgrid=False
        , height=max(220, 38 * len(dados) + 60)
        , margin={'l': 10, 'r': 90, 't': 10, 'b': 10}
        , bargap=0.35
    )
    return figura


def grafico_colunas(rotulos, centavos, apagadas=None):
    # Uma série no tempo (faturas): colunas na cor única; "apagadas" (faturas parciais) ficam claras
    # e o rótulo do eixo já diz "(parcial)", então a diferença não depende só da cor.
    if apagadas is None:
        apagadas = [False] * len(rotulos)
    textos = [ft.reais(valor) for valor in centavos]
    figura = go.Figure(go.Bar(
          x=list(rotulos)
        , y=[valor / 100 for valor in centavos]
        , text=textos
        , customdata=textos
        , textposition='outside'
        , cliponaxis=False
        , marker_color=COR_BARRA
        , marker_opacity=[0.4 if apagada else 1.0 for apagada in apagadas]
        , hovertemplate='%{x}: %{customdata}<extra></extra>'
    ))
    figura.update_layout(
          xaxis_title=None
        , yaxis_title=None
        , yaxis_showticklabels=False
        , yaxis_showgrid=False
        , xaxis_type='category'
        , height=300
        , margin={'l': 10, 'r': 10, 't': 30, 'b': 10}
        , bargap=0.45
    )
    return figura


def centavos_do_campo(valor):
    return int((Decimal(str(valor)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def soma_categorias(valores, categorias):
    return sum(int(valores.get(categoria, 0)) for categoria in categorias)


st.set_page_config(page_title='Raio-X da fatura', page_icon='💳', layout='wide')
st.title('Raio-X da fatura do cartão')
st.caption('O arquivo é lido aqui no seu computador e não é enviado para lugar nenhum.')

# Sem o config.toml (app aberto de outro jeito) o Streamlit atende a rede toda e manda estatísticas.
# Nesse caso o app se recusa a abrir a fatura.
if st.get_option('server.address') not in ['localhost', '127.0.0.1'] or st.get_option('browser.gatherUsageStats'):
    st.error(
        'Por privacidade, abra o app pelo abrir_app.bat (ou rode "py -m streamlit run src/app.py" '
        + 'de dentro da pasta fatura\\_cartao). Do jeito que foi aberto, ele ficaria visível para a rede '
        + 'e enviaria estatísticas de uso.'
    )
    st.stop()

with st.sidebar:
    base = st.radio(
          'Base de dados'
        , [MINHAS, SIMULADAS]
        , key='base'
        , help='Cada base tem seu próprio histórico, metas, categorias escolhidas e rótulos. Use "Faturas simuladas" para dados de demonstração.'
    )
ARQUIVO_REGRAS = CAMINHOS[base]['regras']
ARQUIVO_METAS = CAMINHOS[base]['metas']
PASTA_HISTORICO = CAMINHOS[base]['historico']
ARQUIVO_ROTULOS = CAMINHOS[base]['rotulos']
if base == SIMULADAS:
    st.markdown('**Base de dados: Faturas simuladas.** Tudo o que for guardado aqui fica separado das suas faturas reais.')
else:
    st.markdown('**Base de dados: Minhas faturas.**')

if 'mensagem' in st.session_state:
    st.success(st.session_state.pop('mensagem'))

# Um campo de arquivo por base: trocar de base não leva a fatura aberta junto (senão ela seria guardada
# no histórico da outra base sem ninguém pedir, misturando faturas reais e simuladas).
arquivo = st.file_uploader('Escolha o CSV da fatura do cartão Nubank', type=['csv'], key='fatura_' + base)
if arquivo is None:
    st.info('Exporte a fatura em CSV pelo Nubank e selecione o arquivo acima.')
    st.stop()

try:
    df = ft.ler_csv(arquivo.getvalue())
except ValueError as erro:
    st.error(ft.escapar_markdown(str(erro)))
    st.stop()

regras_usuario, erro_regras = ft.carregar_regras_usuario(ARQUIVO_REGRAS)
if erro_regras:
    st.error(
        ft.escapar_markdown(erro_regras)
        + ' As categorias que você escolheu não estão sendo usadas, e o app não grava nada'
        + ' por cima desse arquivo até ele ser corrigido.'
    )

fatura = ft.montar_fatura(df, regras_usuario)
valores = ft.totais(fatura)
resumo = ft.resumo_categorias(fatura)


def total_categoria(categoria):
    linha = resumo[resumo['categoria'] == categoria]
    if len(linha) == 0:
        return 0
    return int(linha['centavos'].iloc[0])


# ---------------------------------------------------------------- barra lateral: ciclo

with st.sidebar:
    st.header('Ciclo da fatura')
    vencimento = st.date_input(
          'Vencimento'
        , value=ft.vencimento_do_nome(arquivo.name)
        , format='DD/MM/YYYY'
        , key='vencimento_' + arquivo.name
        , help='Vem do nome do arquivo (Nubank_AAAA-MM-DD.csv). Corrija se estiver errado.'
    )
    fechamento = None
    if vencimento is not None:
        fechamento = st.date_input(
              'Fechamento'
            , value=vencimento - timedelta(days=7)
            , format='DD/MM/YYYY'
            , key=f'fechamento_{vencimento}'
            , help='No Nubank a fatura fecha 7 dias antes do vencimento. Compras feitas no dia do fechamento já vão para a fatura seguinte.'
        )
    hoje = st.date_input('Considerar compras até', value=date.today(), format='DD/MM/YYYY', key='hoje')

datas_validas = vencimento is not None and fechamento is not None and fechamento < vencimento
datas = None
resultado = None
if datas_validas:
    datas = ft.ciclo(vencimento, fechamento)
    resultado = ft.projecao(fatura, datas['inicio'], datas['ultimo_dia'], hoje)


# ---------------------------------------------------------------- histórico: guardar esta fatura

# Guarda uma vez por arquivo/vencimento/fechamento nesta sessão. Assim uma fatura removida do histórico
# não volta sozinha no próximo clique, e corrigir o fechamento na barra lateral atualiza a guardada.
situacao_historico = None
if vencimento is None:
    mensagem_historico = 'Sem a data de vencimento a fatura não é guardada no histórico.'
else:
    mensagem_historico = 'Com o fechamento igual ou depois do vencimento a fatura não é guardada no histórico.'
if datas_validas:
    marca = (hashlib.sha256(arquivo.getvalue()).hexdigest(), vencimento.isoformat(), fechamento.isoformat(), base)
    processadas = st.session_state.setdefault('historico_processado', {})
    if marca not in processadas:
        try:
            processadas[marca] = hist.guardar(PASTA_HISTORICO, arquivo.getvalue(), arquivo.name, vencimento, fechamento, hist.data_de_hoje())
        except (OSError, ValueError) as erro:
            processadas[marca] = (hist.ERRO, f'Não consegui guardar a fatura no histórico: {erro}')
    situacao_historico, mensagem_historico = processadas[marca]

entradas, erros_historico = hist.carregar_historico(PASTA_HISTORICO)
montadas = hist.montar(entradas, regras_usuario)
medias, anteriores = hist.media_anterior(montadas, vencimento if vencimento is not None else date.max)

# Cobranças fixas: do histórico; sem histórico, só a fatura aberta (assinaturas pelo nome).
bases_fixos = montadas
if len(bases_fixos) == 0:
    bases_fixos = [{'vencimento': None, 'rotulo': '', 'completa': False, 'fatura': fatura}]
fixos = hist.recorrentes(bases_fixos)
tipos = ft.comportamentos(fatura, set(zip(fixos['chave'], fixos['centavos'])))

rotulos_usuario, erro_rotulos = rt.carregar_rotulos(ARQUIVO_ROTULOS)
if erro_rotulos:
    st.error(
        ft.escapar_markdown(erro_rotulos)
        + ' Os rótulos não estão sendo usados, e o app não grava nada por cima desse arquivo até ele ser corrigido.'
    )
ARQUIVO_ORIGENS = rt.caminho_origens(ARQUIVO_ROTULOS)
origens_rotulos, erro_origens = rt.carregar_origens(ARQUIVO_ORIGENS)
if erro_origens:
    st.warning(
        ft.escapar_markdown(erro_origens)
        + ' A origem dos rótulos não será registrada até esse arquivo ser corrigido; os rótulos continuam valendo.'
    )


def gravar_rotulos(novos, origem_por_chave):
    # Grava os rótulos e, se o arquivo de origens estiver bom, de onde veio cada rótulo novo ou trocado.
    if erro_rotulos:
        return
    rt.salvar_rotulos(ARQUIVO_ROTULOS, novos)
    if not erro_origens:
        rt.salvar_origens(
              ARQUIVO_ORIGENS
            , rt.atualizar_origens(origens_rotulos, rotulos_usuario, novos, origem_por_chave, date.today())
        )


# ---------------------------------------------------------------- metas

gasto_atual = {}
for linha in resumo.itertuples(index=False):
    gasto_atual[linha.categoria] = int(linha.centavos)
metas_usuario, erro_metas = mt.carregar_metas(ARQUIVO_METAS)
if resultado is not None:
    tabela_projecao = resultado['por_categoria']
    situacao_metas = mt.situacao(
          metas_usuario
        , dict(zip(tabela_projecao['categoria'], tabela_projecao['centavos_atual']))
        , dict(zip(tabela_projecao['categoria'], tabela_projecao['centavos_projetado']))
        , resultado['dias_restantes']
    )
else:
    situacao_metas = mt.situacao(metas_usuario, gasto_atual)


# ---------------------------------------------------------------- números principais

coluna1, coluna2, coluna3, coluna4 = st.columns(4)
coluna1.metric('Gasto no período', ft.reais(valores['gasto']))
coluna2.metric('Comida e bebida', ft.reais(total_categoria(ft.COMIDA)))
coluna3.metric('Transporte', ft.reais(total_categoria(ft.TRANSPORTE)))
coluna4.metric('Multa e juros por atraso', ft.reais(int(fatura.loc[fatura['subcategoria'] == ft.SUB_ATRASO, 'centavos'].sum())))

st.caption(
    f'Conferência: a soma de todas as linhas do CSV é {ft.reais_md(valores["total_csv"])} = '
    + f'gasto do período {ft.reais_md(valores["gasto"])} + saldo da fatura anterior {ft.reais_md(valores["saldo_anterior"])} '
    + f'+ pagamentos ({ft.reais_md(valores["pagamentos"])}). Pagamento e saldo anterior não entram no gasto.'
)

pendentes = fatura[fatura['categoria'] == ft.A_CLASSIFICAR]
if len(pendentes) > 0:
    st.warning(
        f'{len(pendentes)} lançamentos ({ft.reais_md(int(pendentes["centavos"].sum()))}) ainda não têm categoria. '
        + 'Os totais por categoria podem mudar quando você classificá-los na aba **Classificar**.'
    )

for linha in situacao_metas:
    if linha['estado'] != 'dentro':
        st.warning('Meta: ' + mt.frase_situacao(linha))

if situacao_historico in [hist.ERRO, hist.DUPLICADA, hist.CONFLITO]:
    st.warning('Histórico: ' + ft.escapar_markdown(mensagem_historico))
else:
    st.caption('Histórico: ' + ft.escapar_markdown(mensagem_historico))

aba_resumo, aba_ciclo, aba_meses, aba_classificar, aba_lancamentos = st.tabs(
    ['Onde foi o dinheiro', 'Até o fechamento', 'Mês a mês', 'Classificar', 'Lançamentos']
)


# ---------------------------------------------------------------- aba: onde foi o dinheiro

with aba_resumo:
    st.subheader('Destaques')
    for frase in ft.destaques(fatura):
        st.markdown('- ' + frase)

    st.subheader('Gasto por categoria')
    if (resumo['centavos'] > 0).any():
        st.plotly_chart(grafico_barras(resumo, 'categoria'), width='stretch', config={'displayModeBar': False})
    st.dataframe(tabela_resumo(resumo, 'categoria', 'Categoria'), hide_index=True, width='stretch')

    st.subheader('Tipo de gasto')
    por_tipo = ft.resumo_comportamentos(fatura, tipos)
    st.dataframe(
          pd.DataFrame({
              'Tipo': por_tipo['comportamento']
            , 'Total': [ft.reais(valor) for valor in por_tipo['centavos']]
            , '% do gasto': ['-' if valor is None or pd.isna(valor) else f'{valor:.1f}%'.replace('.', ',') for valor in por_tipo['percentual']]
            , 'Lançamentos': por_tipo['lancamentos']
          })
        , hide_index=True
        , width='stretch'
    )
    st.caption(
        'A categoria diz em quê você gastou; o tipo diz como. Recorrente: cobrança fixa detectada (aba Mês a mês). '
        + 'Parcelado: parcela de compra anterior. Ocasional: o resto das compras. Encargo: juros, multa e IOF. '
        + 'Estorno: dinheiro de volta.'
    )

    st.subheader('Dentro de cada categoria')
    for categoria in resumo['categoria']:
        subcategorias = ft.resumo_subcategorias(fatura, categoria)
        with st.expander(f'{ft.escapar_markdown(categoria)}: {ft.reais_md(total_categoria(categoria))}', expanded=categoria in [ft.COMIDA, ft.TRANSPORTE]):
            st.dataframe(tabela_resumo(subcategorias, 'subcategoria', 'Subcategoria'), hide_index=True, width='stretch')
            itens = fatura[fatura['conta_no_gasto'] & (fatura['categoria'] == categoria)]
            st.dataframe(
                  pd.DataFrame({
                      'Data': itens['data'].dt.strftime('%d/%m/%Y')
                    , 'Descrição': itens['descricao']
                    , 'Subcategoria': itens['subcategoria']
                    , 'Valor': [ft.reais(valor) for valor in itens['centavos']]
                  })
                , hide_index=True
                , width='stretch'
            )

    st.subheader('Onde você mais gastou')
    top = ft.top_estabelecimentos(fatura, 10)
    st.dataframe(
          pd.DataFrame({
              'Estabelecimento': top['estabelecimento']
            , 'Categoria': top['categoria']
            , 'Total': [ft.reais(valor) for valor in top['centavos']]
            , 'Compras': top['compras']
          })
        , hide_index=True
        , width='stretch'
    )

    st.subheader('Gastinhos que somam')
    pequenos = ft.gastinhos(fatura)
    if pequenos is None:
        st.write('Poucas compras do dia a dia nesta fatura para separar as pequenas.')
    else:
        percentual = ''
        if pequenos['percentual_do_gasto'] is not None:
            percentual = f', {pequenos["percentual_do_gasto"]:.0f}% do gasto do período'.replace('.', ',')
        st.markdown(
            f'**{pequenos["quantidade"]} de {pequenos["total_compras"]} compras do dia a dia** foram de até '
            + f'{ft.reais_md(pequenos["corte"])}. Juntas, somam **{ft.reais_md(pequenos["centavos"])}**{percentual}.'
        )
        st.caption(
            'O corte de "pequena" é a mediana das suas próprias compras do dia a dia nesta fatura: metade delas custou até esse valor. '
            + 'Parcelas, assinaturas, juros/multas/IOF e estornos não entram.'
        )
        lugares = pequenos['lugares'].head(10)
        st.dataframe(
              pd.DataFrame({
                  'Estabelecimento': lugares['estabelecimento']
                , 'Categoria': lugares['categoria']
                , 'Compras pequenas': lugares['compras']
                , 'Total': [ft.reais(valor) for valor in lugares['centavos']]
              })
            , hide_index=True
            , width='stretch'
        )


# ---------------------------------------------------------------- aba: até o fechamento

with aba_ciclo:
    st.subheader('Metas desta fatura')
    if erro_metas:
        st.error(
            ft.escapar_markdown(erro_metas)
            + ' As metas não estão sendo usadas, e o app não grava nada por cima desse arquivo até ele ser corrigido.'
        )
    elif len(situacao_metas) == 0:
        st.write('Nenhuma meta ainda. Crie uma abaixo, por exemplo comida + transporte juntos.')
    for linha in situacao_metas:
        st.markdown(mt.frase_situacao(linha))
        # Estornos maiores que as compras deixam o atual negativo: a barra fica vazia.
        st.progress(max(0.0, min(linha['percentual'], 100.0)) / 100)
        detalhes = []
        if linha['por_dia'] is not None:
            detalhes.append(
                f'Para caber na meta: até {ft.reais_md(linha["por_dia"])} por dia nos {linha["dias_restantes"]} dia(s) de compra '
                + f'que faltam depois de {hoje:%d/%m/%Y} ({ft.reais_md(linha["restante"])} no total).'
            )
        elif linha['restante'] > 0 and linha['dias_restantes'] == 0:
            detalhes.append(f'Os dias de compra desta fatura acabaram; sobraram {ft.reais_md(linha["restante"])} da meta.')
        elif linha['restante'] > 0 and datas_validas:
            # Vencimento certo, mas "Considerar compras até" é anterior ao início do ciclo: não há projeção.
            detalhes.append(
                f'Faltam {ft.reais_md(linha["restante"])} para a meta. A data em "Considerar compras até" é anterior '
                + 'ao início do ciclo, então não dá para calcular quanto dá por dia.'
            )
        elif linha['restante'] > 0:
            detalhes.append(f'Faltam {ft.reais_md(linha["restante"])} para a meta. Informe o vencimento para ver quanto dá por dia.')
        if linha['projetado'] is not None and linha['estado'] == 'dentro':
            detalhes.append(f'No ritmo atual fecha em {ft.reais_md(linha["projetado"])}.')
        if anteriores:
            detalhes.append(
                f'Sua média nessas categorias: {ft.reais_md(soma_categorias(medias, linha["categorias"]))} '
                + f'({len(anteriores)} fatura(s) completa(s) do histórico).'
            )
        if detalhes:
            st.caption(' '.join(detalhes))

    if not erro_metas:
        with st.expander('Criar, mudar ou remover metas', expanded=len(metas_usuario) == 0):
            with st.form('form_meta'):
                categorias_meta = st.multiselect('Categorias (uma ou mais, somadas)', options=mt.CATEGORIAS_META, key='meta_categorias')
                valor_meta = st.number_input('Valor máximo na fatura (R$)', min_value=0.0, step=50.0, format='%.2f', key='meta_valor')
                salvar_meta = st.form_submit_button('Salvar meta')
            st.caption('Se já existe meta com exatamente as mesmas categorias, o valor dela é trocado.')
            if salvar_meta:
                try:
                    novas_metas = mt.definir_meta(metas_usuario, categorias_meta, centavos_do_campo(valor_meta))
                except ValueError as erro:
                    st.error(ft.escapar_markdown(str(erro)))
                else:
                    mt.salvar_metas(ARQUIVO_METAS, novas_metas)
                    st.session_state['mensagem'] = f'Meta {ft.escapar_markdown(mt.nome_meta(mt.ordenar_categorias(categorias_meta)))} salva.'
                    st.rerun()
            if metas_usuario:
                nomes_metas = [mt.nome_meta(meta['categorias']) for meta in metas_usuario]
                meta_removida = st.selectbox('Meta para remover', options=nomes_metas, key='meta_remover')
                if st.button('Remover meta'):
                    escolhida = metas_usuario[nomes_metas.index(meta_removida)]
                    mt.salvar_metas(ARQUIVO_METAS, mt.remover_meta(metas_usuario, escolhida['categorias']))
                    st.session_state['mensagem'] = f'Meta {ft.escapar_markdown(meta_removida)} removida.'
                    st.rerun()

    st.subheader('Ciclo e estimativa')
    if vencimento is None or fechamento is None:
        st.info('O nome do arquivo não traz a data de vencimento. Informe o vencimento na barra lateral para ver o ciclo.')
    elif fechamento >= vencimento:
        st.error('O fechamento precisa ser antes do vencimento. Corrija as datas na barra lateral.')
    else:
        st.markdown(
            f'Compras desta fatura: de **{datas["inicio"]:%d/%m/%Y}** a **{datas["ultimo_dia"]:%d/%m/%Y}** '
            + f'(fecha em {datas["fechamento"]:%d/%m/%Y}, vence em {datas["vencimento"]:%d/%m/%Y}).'
        )
        if resultado is None:
            st.info('A data em "Considerar compras até" é anterior ao início do ciclo.')
        else:
            coluna1, coluna2, coluna3 = st.columns(3)
            coluna1.metric('Dias de compra que faltam', f'{resultado["dias_restantes"]} de {resultado["dias_total"]}')
            coluna2.metric('Ritmo do dia a dia', ft.reais(resultado['ritmo_diario']) + ' por dia')
            coluna3.metric('Fatura estimada no fechamento', ft.reais(resultado['fatura_estimada']))
            st.caption(
                'Estimativa simples: se o gasto do dia a dia continuar no mesmo ritmo até o fechamento. '
                + 'Parcelas, assinaturas, juros/multas/IOF e estornos ficam fora do ritmo, porque não se repetem todo dia. '
                + 'Lançamentos a classificar entram no ritmo. '
                + f'A fatura estimada é o que já está na fatura ({ft.reais_md(resultado["fatura_atual"])}, '
                + 'incluindo saldo anterior e pagamentos) mais o ritmo; '
                + f'só o gasto do período ficaria em {ft.reais_md(resultado["projetado"])}.'
            )
            if resultado['depois_de_hoje'] > 0:
                st.caption(
                    f'{resultado["depois_de_hoje"]} lançamento(s) com data depois de {hoje:%d/%m/%Y} '
                    + 'não entram nesta estimativa.'
                )
            tabela = resultado['por_categoria']
            st.dataframe(
                  pd.DataFrame({
                      'Categoria': tabela['categoria']
                    , 'Até agora': [ft.reais(valor) for valor in tabela['centavos_atual']]
                    , 'A mais no ritmo atual': [ft.reais(valor) for valor in tabela['centavos_a_mais']]
                    , 'Estimado no fechamento': [ft.reais(valor) for valor in tabela['centavos_projetado']]
                  })
                , hide_index=True
                , width='stretch'
            )
        datas_lancamentos = fatura['data'].dt.date
        fora = fatura[(datas_lancamentos < datas['inicio']) | (datas_lancamentos > datas['ultimo_dia'])]
        if len(fora) > 0:
            st.caption(
                f'{len(fora)} lançamento(s) têm data fora desse período (comum em estornos e encargos) '
                + 'e entram nos totais, mas não no ritmo.'
            )

        st.subheader('Melhor dia de compra')
        melhor = ft.melhor_dia_de_compra(vencimento, fechamento, hoje)
        st.markdown(
            f'**Dia {melhor["dia"].day}, o dia do fechamento.** Uma compra em **{melhor["dia"]:%d/%m/%Y}** já vai para a fatura '
            + f'que vence em {melhor["vencimento"]:%d/%m/%Y}: **{melhor["prazo_dias"]} dias** até pagar. '
            + f'Na véspera ({melhor["vespera"]:%d/%m/%Y}) ela entraria na fatura que vence em '
            + f'{melhor["vencimento_vespera"]:%d/%m/%Y}, com {melhor["prazo_vespera_dias"]} dias.'
        )
        st.caption(
            'Regra do Nubank: a fatura fecha 7 dias antes do vencimento e a compra do dia do fechamento já fica para a fatura seguinte. '
            + 'Nos meses seguintes, o fechamento fica à mesma distância do vencimento de cada mês; confira o "melhor dia de compra" no app do Nubank.'
        )

    st.subheader('Parcelas que ainda vão cair')
    futuras = ft.parcelas_futuras(fatura)
    if len(futuras) == 0:
        st.write('Nenhuma compra parcelada com parcelas restantes.')
    else:
        st.dataframe(
              pd.DataFrame({
                  'Compra': futuras['estabelecimento']
                , 'Categoria': futuras['categoria']
                , 'Parcela': futuras['parcela_atual'].astype(str) + '/' + futuras['parcela_total'].astype(str)
                , 'Valor da parcela': [ft.reais(valor) for valor in futuras['centavos']]
                , 'Faltam': futuras['restantes']
                , 'Ainda a pagar': [ft.reais(valor) for valor in futuras['centavos_futuros']]
              })
            , hide_index=True
            , width='stretch'
        )
        st.caption(f'Total nas próximas faturas: {ft.reais_md(int(futuras["centavos_futuros"].sum()))} (supondo parcelas de mesmo valor).')

        st.subheader('Já comprometido nas próximas faturas')
        por_mes = ft.parcelas_por_mes(fatura, vencimento if datas_validas else None)
        st.plotly_chart(grafico_colunas(por_mes['fatura'], por_mes['centavos']), width='stretch', config={'displayModeBar': False}, key='grafico_parcelas')
        st.dataframe(
              pd.DataFrame({
                  'Fatura': por_mes['fatura']
                , 'Parcelas': por_mes['compras']
                , 'Já comprometido': [ft.reais(valor) for valor in por_mes['centavos']]
              })
            , hide_index=True
            , width='stretch'
        )
        st.caption(
            'Só as parcelas desta fatura: compras novas e assinaturas vêm por cima. '
            + 'O mês é o do vencimento de cada fatura.'
        )


# ---------------------------------------------------------------- aba: mês a mês

with aba_meses:
    st.caption('Histórico: ' + ft.escapar_markdown(mensagem_historico))
    for erro in erros_historico:
        st.error(f'Fatura guardada {ft.escapar_markdown(erro["vencimento"])} com problema e ignorada: {ft.escapar_markdown(erro["erro"])}')

    st.subheader('Esta fatura e a sua média')
    if resultado is not None:
        tabela_projecao = resultado['por_categoria']
        valores_desta = dict(zip(tabela_projecao['categoria'], tabela_projecao['centavos_projetado']))
        valores_desta['Total'] = resultado['projetado']
        explicacao_desta = 'estimada no fechamento, no ritmo atual'
    else:
        valores_desta = dict(gasto_atual)
        valores_desta['Total'] = valores['gasto']
        explicacao_desta = 'o que já está nela'
    if not anteriores:
        st.info(
            'Ainda não há no histórico uma fatura completa anterior a esta para comparar. '
            + 'Cada fatura que você abrir fica guardada; a comparação aparece a partir da próxima.'
        )
    else:
        comparacao = hist.comparar_com_media(valores_desta, medias)
        atual_ct = soma_categorias(valores_desta, COMIDA_E_TRANSPORTE)
        media_ct = soma_categorias(medias, COMIDA_E_TRANSPORTE)
        coluna1, coluna2 = st.columns(2)
        coluna1.metric(
              'Comida + transporte nesta fatura'
            , ft.reais(atual_ct)
            # O delta passa por markdown: dois "R$" viram fórmula sem o escape.
            , delta=f'{ft.reais_md(atual_ct - media_ct)} vs. média de {ft.reais_md(media_ct)}'
            , delta_color='inverse'
        )
        coluna2.metric(
              'Gasto do período nesta fatura'
            , ft.reais(valores_desta['Total'])
            , delta=f'{ft.reais_md(valores_desta["Total"] - medias.get("Total", 0))} vs. média de {ft.reais_md(medias.get("Total", 0))}'
            , delta_color='inverse'
        )
        variacoes = []
        for valor in comparacao['percentual']:
            if valor is None or pd.isna(valor):
                variacoes.append('-')
            else:
                variacoes.append(f'{valor:+.0f}%')
        st.dataframe(
              pd.DataFrame({
                  'Categoria': comparacao['categoria']
                , 'Esta fatura': [ft.reais(valor) for valor in comparacao['atual']]
                , 'Média': [ft.reais(valor) for valor in comparacao['media']]
                , 'Diferença': [ft.reais(valor) for valor in comparacao['diferenca']]
                , 'Variação': variacoes
              })
            , hide_index=True
            , width='stretch'
        )
        st.caption(
            f'Esta fatura: {explicacao_desta}. '
            + f'Média de {len(anteriores)} fatura(s) completa(s) anterior(es): '
            + ', '.join(item['rotulo'] for item in anteriores)
            + '. Faturas guardadas antes de fechar (parciais) não entram na média. '
            + 'As faturas do histórico são reclassificadas com as suas categorias atuais.'
        )

    st.subheader('Fora do seu padrão')
    fora, quantas_anteriores, comparadas = hist.fora_do_padrao(montadas, vencimento if vencimento is not None else date.max, valores_desta)
    if fora is None:
        st.info(
            f'Ainda não há histórico suficiente: são precisas 2 faturas completas anteriores a esta, e há {quantas_anteriores}.'
        )
    else:
        if len(fora) == 0:
            st.write(f'Nenhuma categoria saiu do intervalo das {quantas_anteriores} faturas completas anteriores.')
        for linha in fora.itertuples(index=False):
            if linha.direcao == hist.ACIMA and linha.maximo == 0:
                st.markdown(
                    f'- **{ft.escapar_markdown(linha.categoria)}**: {ft.reais_md(linha.atual)} nesta fatura; '
                    + f'não apareceu nas {quantas_anteriores} faturas anteriores.'
                )
            elif linha.direcao == hist.ACIMA:
                st.markdown(
                    f'- **{ft.escapar_markdown(linha.categoria)}**: {ft.reais_md(linha.atual)} nesta fatura, '
                    + f'acima do maior valor das {quantas_anteriores} faturas anteriores ({ft.reais_md(linha.maximo)}).'
                )
            else:
                st.markdown(
                    f'- **{ft.escapar_markdown(linha.categoria)}**: {ft.reais_md(linha.atual)} nesta fatura, '
                    + f'abaixo do menor valor das {quantas_anteriores} faturas anteriores ({ft.reais_md(linha.minimo)}).'
                )
        esperados = f'{2 * comparadas / (quantas_anteriores + 1):.1f}'.replace('.', ',')
        st.caption(
            f'Esta fatura: {explicacao_desta}. Como funciona: compara com o menor e o maior valor de cada categoria nas faturas completas anteriores '
            + '("A classificar" e estornos ficam de fora). '
            + f'Se os meses fossem parecidos entre si, cada categoria ficaria fora desse intervalo por acaso 2 vezes em {quantas_anteriores + 1} '
            + f'(acima do maior 1 vez, abaixo do menor 1 vez). Com {comparadas} categorias comparadas, '
            + f'espere uns {esperados} avisos só por acaso: só leve a sério os que forem muitos a mais que isso ou que você reconheça. '
            + 'Quanto mais faturas no histórico, menos avisos por acaso.'
        )

    st.subheader('Gasto por fatura')
    if len(montadas) == 0:
        st.write('Nenhuma fatura guardada ainda.')
    else:
        mensal = hist.tabela_mensal(montadas)
        totais_mensais = mensal[mensal['categoria'] == 'Total']
        rotulos_meses = [rotulo if completa else rotulo + ' (parcial)' for rotulo, completa in zip(totais_mensais['fatura'], totais_mensais['completa'])]
        opcoes_evolucao = ['Total', 'Comida e bebida + Transporte'] + [categoria for categoria in ft.CATEGORIAS if categoria in set(mensal['categoria'])]
        escolhida_evolucao = st.selectbox('Mostrar a evolução de', options=opcoes_evolucao, key='evolucao_categoria')
        if escolhida_evolucao == 'Comida e bebida + Transporte':
            categorias_evolucao = COMIDA_E_TRANSPORTE
        else:
            categorias_evolucao = [escolhida_evolucao]
        valores_evolucao = []
        for item in montadas:
            da_fatura = mensal[(mensal['vencimento'] == item['vencimento']) & mensal['categoria'].isin(categorias_evolucao)]
            valores_evolucao.append(int(da_fatura['centavos'].sum()))
        st.plotly_chart(
              grafico_colunas(rotulos_meses, valores_evolucao, [not completa for completa in totais_mensais['completa']])
            , width='stretch'
            , config={'displayModeBar': False}
            , key='grafico_meses'
        )
        colunas = {}
        for item, rotulo in zip(montadas, rotulos_meses):
            colunas[rotulo] = item['vencimento']
        linhas_tabela = []
        for categoria in ft.CATEGORIAS + ['Total']:
            da_categoria = mensal[mensal['categoria'] == categoria]
            if len(da_categoria) == 0:
                continue
            linha_tabela = {'Categoria': categoria}
            for rotulo, vence in colunas.items():
                valor = da_categoria.loc[da_categoria['vencimento'] == vence, 'centavos']
                linha_tabela[rotulo] = ft.reais(int(valor.iloc[0])) if len(valor) > 0 else '-'
            linhas_tabela.append(linha_tabela)
        st.dataframe(pd.DataFrame(linhas_tabela), hide_index=True, width='stretch')
        st.caption('Gasto do período de cada fatura (sem pagamento e saldo anterior). "Parcial": guardada antes do fechamento.')

    st.subheader('Assinaturas e gastos fixos')
    if len(fixos) == 0:
        st.write('Nenhuma cobrança fixa encontrada.')
    else:
        ativos = fixos[fixos['ativa']]
        st.markdown(
            f'**{ft.reais_md(int(ativos["centavos"].sum()))} por mês** em cobranças fixas, '
            + f'**{ft.reais_md(int(ativos["por_ano"].sum()))} por ano**.'
        )
        st.dataframe(
              pd.DataFrame({
                  'Cobrança': fixos['estabelecimento']
                , 'Categoria': fixos['categoria']
                , 'Por mês': [ft.reais(valor) for valor in fixos['centavos']]
                , 'Por ano': [ft.reais(valor) for valor in fixos['por_ano']]
                , 'Faturas': fixos['faturas']
                , 'Ainda cobrada': ['sim' if valor else 'não' for valor in fixos['ativa']]
                , 'Como foi achada': fixos['como']
              })
            , hide_index=True
            , width='stretch'
        )
    st.caption(
        '"Repete todo mês": mesmo estabelecimento e mesmo valor, uma vez por fatura, em 2 ou mais faturas seguidas do histórico. '
        + '"Assinatura conhecida": categoria Assinaturas. '
        + '"Ainda cobrada": apareceu na última fatura completa ou depois dela (uma fatura ainda aberta não tira nada do total). '
        + '"Valor mudou (a confirmar)": cobrança fixa que veio com outro valor na fatura aberta; ela entra no total no lugar do valor antigo. '
        + 'Parcelas, juros e estornos não entram. O total soma só o que ainda é cobrado.'
    )
    if len(montadas) < 2:
        st.caption('Com menos de 2 faturas guardadas, só aparecem as assinaturas conhecidas pelo nome.')

    st.subheader('Faturas guardadas')
    st.caption(
        f'Ficam em {ft.escapar_markdown(PASTA_HISTORICO)}, no seu computador. '
        + '"Parcial": guardada antes do fechamento, fica fora das médias. Para completar, abra aqui a exportação '
        + 'feita depois do fechamento (ou o mesmo arquivo, se nada mudou).'
    )
    if entradas:
        st.dataframe(
              pd.DataFrame({
                  'Vencimento': [entrada['vencimento'].strftime('%d/%m/%Y') for entrada in entradas]
                , 'Fechamento': [entrada['fechamento'].strftime('%d/%m/%Y') for entrada in entradas]
                , 'Guardada em': [entrada['salvo_em'].strftime('%d/%m/%Y') for entrada in entradas]
                , 'Lançamentos': [len(entrada['df']) for entrada in entradas]
                , 'Situação': ['completa' if entrada['completa'] else 'parcial' for entrada in entradas]
                , 'Arquivo': [entrada['arquivo'] for entrada in entradas]
              })
            , hide_index=True
            , width='stretch'
        )
    opcoes_remover = [entrada['vencimento'].isoformat() for entrada in entradas] + [erro['vencimento'] for erro in erros_historico]
    if opcoes_remover:
        remover_vencimento = st.selectbox(
              'Fatura para remover do histórico'
            , options=sorted(opcoes_remover)
            , format_func=lambda texto: date.fromisoformat(texto).strftime('%d/%m/%Y')
            , key='historico_remover'
        )
        if st.button('Remover do histórico'):
            hist.remover(PASTA_HISTORICO, date.fromisoformat(remover_vencimento))
            # Com o mesmo vencimento: se a fatura aberta não foi guardada porque a guardada estava com problema
            # ou em conflito (as mensagens mandam remover a guardada), ela é guardada agora. Nos outros casos
            # (inclusive "mantive a guardada", versão mais velha aberta) a removida não volta nesta sessão.
            # Com outro vencimento: uma "duplicada" pode ter sido desta que saiu, então tenta de novo.
            processado = st.session_state.get('historico_processado', {})
            for marca_processada, (situacao, texto) in list(processado.items()):
                if marca_processada[3] != base:
                    # Outra base de dados: a remoção não mexeu nela.
                    continue
                if marca_processada[1] == remover_vencimento and situacao in [hist.ERRO, hist.CONFLITO]:
                    del processado[marca_processada]
                elif marca_processada[1] != remover_vencimento and situacao == hist.DUPLICADA:
                    del processado[marca_processada]
                elif marca_processada[1] == remover_vencimento:
                    processado[marca_processada] = (
                          hist.REMOVIDA
                        , f'Fatura {date.fromisoformat(remover_vencimento):%d/%m/%Y} removida do histórico. '
                        + 'Ela só volta se você abrir este arquivo de novo numa nova sessão (recarregando a página).'
                    )
            st.session_state['mensagem'] = f'Fatura {date.fromisoformat(remover_vencimento):%d/%m/%Y} removida do histórico.'
            st.rerun()

    with st.expander('Adicionar faturas antigas'):
        antigas = st.file_uploader(
              'CSVs de faturas anteriores do Nubank (o vencimento vem do nome, Nubank_AAAA-MM-DD.csv)'
            , type=['csv']
            , accept_multiple_files=True
            , key='importar_antigas_' + base
        )
        if st.button('Guardar no histórico', disabled=not antigas):
            resultados = []
            for antiga in antigas:
                vence = ft.vencimento_do_nome(antiga.name)
                if vence is None:
                    resultados.append(f'{antiga.name}: sem a data de vencimento no nome, não guardei.')
                    continue
                try:
                    situacao, texto = hist.guardar(PASTA_HISTORICO, antiga.getvalue(), antiga.name, vence, vence - timedelta(days=7), hist.data_de_hoje())
                except (OSError, ValueError) as erro:
                    texto = f'não consegui ler ({erro})'
                resultados.append(f'{antiga.name}: {texto}')
            st.session_state['mensagem'] = ft.escapar_markdown(' | '.join(resultados))
            st.rerun()
        st.caption('O fechamento dessas faturas é considerado 7 dias antes do vencimento.')


# ---------------------------------------------------------------- aba: classificar

with aba_classificar:
    if erro_regras:
        st.error('Corrija ou apague o arquivo de categorias para poder classificar: ' + ft.escapar_markdown(ARQUIVO_REGRAS))
    else:
        st.write(
            'Escolha a categoria dos lançamentos que o app não reconheceu. '
            + 'A escolha vale para o estabelecimento e fica salva para as próximas faturas.'
        )
        grupos = []
        for chave, grupo in pendentes.groupby('chave', sort=False):
            grupos.append([chave, grupo.iloc[0]['estabelecimento'], grupo.iloc[0]['descricao'], int(grupo.iloc[0]['centavos']), int(grupo['centavos'].sum()), len(grupo)])

        if len(grupos) == 0:
            st.success('Todos os lançamentos têm categoria.')
        else:
            with st.form('form_classificar'):
                for chave, nome, descricao, centavos, total, quantidade in grupos:
                    opcoes = ft.CATEGORIAS_ESCOLHA
                    if total < 0:
                        opcoes = ft.CATEGORIAS_ESCOLHA_CREDITO
                    st.selectbox(
                          f'{ft.escapar_markdown(nome)}: {ft.reais_md(total)} em {quantidade} lançamento(s)'
                        , options=opcoes
                        , index=opcoes.index(ft.A_CLASSIFICAR)
                        , key='classificar_' + chave
                    )
                salvar = st.form_submit_button('Salvar categorias')
            if salvar:
                novas = dict(regras_usuario)
                novos_rotulos = dict(rotulos_usuario)
                mudou = 0
                for chave, nome, descricao, centavos, total, quantidade in grupos:
                    escolha = st.session_state['classificar_' + chave]
                    if escolha != ft.A_CLASSIFICAR:
                        novas = ft.aplicar_escolha(novas, descricao, centavos, escolha)
                        # A escolha do usuário também é rótulo humano para o ML.
                        novos_rotulos = rt.registrar_escolha(novos_rotulos, fatura, chave, escolha)
                        mudou = mudou + 1
                if mudou == 0:
                    st.info('Nenhuma categoria escolhida.')
                else:
                    ft.salvar_regras_usuario(ARQUIVO_REGRAS, novas)
                    gravar_rotulos(novos_rotulos, {chave: rt.ORIGEM_A_CLASSIFICAR for chave in novos_rotulos})
                    st.session_state['mensagem'] = f'{mudou} estabelecimento(s) classificado(s).'
                    st.rerun()

        st.subheader('Conferir categorias (rótulos para o ML)')
        if erro_rotulos:
            st.error('Corrija ou apague o arquivo de rótulos para poder conferir: ' + ft.escapar_markdown(ARQUIVO_ROTULOS))
        else:
            itens_conferir = rt.para_conferir(fatura, rotulos_usuario)
            # O Streamlit guarda o valor de cada campo pela key (no servidor e no navegador) e ignora value/index
            # depois da primeira vez. Se rótulos ou regras mudaram por outro caminho (A classificar, Corrigir,
            # outra base, outra fatura), os campos recebem de novo o que está gravado, pelo session_state:
            # só assim o navegador também troca o que mostra (apagar a key não basta, o navegador manteria o valor
            # antigo e a próxima conferência desfaria em silêncio o que foi gravado).
            assinatura = repr((base, arquivo.name, hashlib.sha256(arquivo.getvalue()).hexdigest(), sorted(rotulos_usuario.items()), sorted(regras_usuario.items())))
            if st.session_state.get('assinatura_conferencia') != assinatura:
                for chave_estado in list(st.session_state.keys()):
                    if str(chave_estado).startswith('conferir_'):
                        del st.session_state[chave_estado]
                for item in itens_conferir.itertuples(index=False):
                    st.session_state['conferir_categoria_' + item.chave] = item.categoria_sugerida
                    st.session_state['conferir_ok_' + item.chave] = bool(item.conferido)
                st.session_state['assinatura_conferencia'] = assinatura
            # Campo que o Streamlit descartou (não foi desenhado numa execução) volta com o valor gravado.
            for item in itens_conferir.itertuples(index=False):
                if 'conferir_categoria_' + item.chave not in st.session_state:
                    st.session_state['conferir_categoria_' + item.chave] = item.categoria_sugerida
                if 'conferir_ok_' + item.chave not in st.session_state:
                    st.session_state['conferir_ok_' + item.chave] = bool(item.conferido)
            st.write(
                'Marque "conferido" nos estabelecimentos cuja categoria você confirmou, mesmo quando o app já acertou. '
                + 'Só os conferidos viram exemplos para treinar e avaliar o modelo, e a categoria escolhida passa a valer no app.'
            )
            st.caption(
                f'{int(itens_conferir["conferido"].sum())} de {len(itens_conferir)} estabelecimentos desta fatura conferidos. '
                + 'Pagamentos, saldo anterior, estornos e juros/multas/IOF ficam de fora.'
            )
            with st.expander('Conferir estabelecimentos desta fatura', expanded=bool((~itens_conferir['conferido']).any())):
                with st.form('form_conferir'):
                    for item in itens_conferir.itertuples(index=False):
                        coluna_nome, coluna_categoria, coluna_ok = st.columns([4, 3, 1])
                        coluna_nome.markdown(
                            f'**{ft.escapar_markdown(item.estabelecimento)}**  \n'
                            + f'{ft.reais_md(item.centavos)} em {item.lancamentos} lançamento(s); hoje: {ft.escapar_markdown(item.categoria_atual)}'
                        )
                        opcoes_conferir = rt.CATEGORIAS_ROTULO + [ft.A_CLASSIFICAR]
                        # Valor inicial vem do session_state (preenchido acima); sem value/index para não conflitar.
                        coluna_categoria.selectbox(
                              f'Categoria de {ft.escapar_markdown(item.estabelecimento)}'
                            , options=opcoes_conferir
                            , key='conferir_categoria_' + item.chave
                            , label_visibility='collapsed'
                        )
                        coluna_ok.checkbox('Conferido', key='conferir_ok_' + item.chave)
                    salvar_conferencia = st.form_submit_button('Salvar conferência')
                if salvar_conferencia:
                    escolhas = {}
                    for item in itens_conferir.itertuples(index=False):
                        escolhas[item.chave] = (
                              st.session_state['conferir_categoria_' + item.chave]
                            , st.session_state['conferir_ok_' + item.chave]
                        )
                    try:
                        novos_rotulos, novas_regras, conferidos, removidos = rt.aplicar_conferencia(rotulos_usuario, regras_usuario, itens_conferir, escolhas)
                    except ValueError as erro:
                        st.error(ft.escapar_markdown(str(erro)))
                    else:
                        origem_por_chave = {}
                        for item in itens_conferir.itertuples(index=False):
                            if escolhas[item.chave][0] == item.categoria_atual:
                                origem_por_chave[item.chave] = rt.ORIGEM_CONFIRMOU
                            else:
                                origem_por_chave[item.chave] = rt.ORIGEM_TROCOU
                        gravar_rotulos(novos_rotulos, origem_por_chave)
                        ft.salvar_regras_usuario(ARQUIVO_REGRAS, novas_regras)
                        st.session_state['mensagem'] = f'{conferidos} estabelecimento(s) conferido(s), {removidos} rótulo(s) removido(s).'
                        st.rerun()

            conjunto = rt.conjunto_rotulado(montadas, rotulos_usuario, origens_rotulos, 'simuladas' if base == SIMULADAS else 'minhas')
            st.caption(
                f'Na base "{base}": {len(conjunto)} lançamento(s) rotulado(s), de {conjunto["chave"].nunique()} estabelecimento(s), '
                + f'em {conjunto["vencimento"].nunique()} fatura(s) do histórico.'
            )
            if len(conjunto) > 0:
                por_rotulo = conjunto.groupby('rotulo').agg(lancamentos=('chave', 'size'), estabelecimentos=('chave', 'nunique')).reset_index()
                st.dataframe(
                      pd.DataFrame({
                          'Categoria': por_rotulo['rotulo']
                        , 'Lançamentos': por_rotulo['lancamentos']
                        , 'Estabelecimentos': por_rotulo['estabelecimentos']
                      })
                    , hide_index=True
                    , width='stretch'
                )
                st.download_button(
                      'Baixar lançamentos rotulados (CSV)'
                    , data=conjunto.to_csv(index=False).encode('utf-8')
                    , file_name='rotulados_' + ('simuladas' if base == SIMULADAS else 'minhas') + '.csv'
                    , mime='text/csv'
                    , key='baixar_rotulados'
                )

        st.subheader('Corrigir a categoria de um estabelecimento')
        estabelecimentos = fatura.drop_duplicates('chave')
        nomes_corrigir = {}
        for item in estabelecimentos.itertuples(index=False):
            nomes_corrigir[item.chave] = f'{item.estabelecimento} (hoje: {item.categoria})'
        chave_escolhida = st.selectbox(
              'Estabelecimento'
            , options=list(nomes_corrigir.keys())
            , format_func=nomes_corrigir.get
            , key='corrigir_estabelecimento'
        )
        exemplo = estabelecimentos[estabelecimentos['chave'] == chave_escolhida].iloc[0]
        opcoes = ft.CATEGORIAS_ESCOLHA
        if int(fatura.loc[fatura['chave'] == chave_escolhida, 'centavos'].sum()) < 0:
            opcoes = ft.CATEGORIAS_ESCOLHA_CREDITO
        nova_categoria = st.selectbox('Nova categoria', options=opcoes + [VOLTAR_AUTOMATICA], key='corrigir_categoria')
        if st.button('Salvar correção'):
            novas = dict(regras_usuario)
            if nova_categoria == VOLTAR_AUTOMATICA:
                novas.pop(chave_escolhida, None)
                novos_rotulos = rt.registrar_escolha(rotulos_usuario, fatura, chave_escolhida, None)
            else:
                novas = ft.aplicar_escolha(novas, exemplo['descricao'], int(exemplo['centavos']), nova_categoria)
                novos_rotulos = rt.registrar_escolha(rotulos_usuario, fatura, chave_escolhida, nova_categoria)
            ft.salvar_regras_usuario(ARQUIVO_REGRAS, novas)
            gravar_rotulos(novos_rotulos, {chave_escolhida: rt.ORIGEM_CORRIGIR})
            st.session_state['mensagem'] = f'Categoria de {ft.escapar_markdown(exemplo["estabelecimento"])} salva.'
            st.rerun()

        if regras_usuario:
            st.caption(f'{len(regras_usuario)} estabelecimento(s) com categoria escolhida por você, salvos em {ft.escapar_markdown(ARQUIVO_REGRAS)}.')


# ---------------------------------------------------------------- aba: lançamentos

with aba_lancamentos:
    filtro = st.multiselect('Filtrar categorias', options=ft.CATEGORIAS, key='filtro_categorias')
    filtro_tipo = st.multiselect('Filtrar tipo de gasto', options=ft.COMPORTAMENTOS, key='filtro_tipos')
    selecao = pd.Series(True, index=fatura.index)
    if filtro:
        selecao = selecao & fatura['categoria'].isin(filtro)
    if filtro_tipo:
        selecao = selecao & tipos.isin(filtro_tipo)
    lista = fatura[selecao]
    parcela = []
    for item in lista.itertuples(index=False):
        if pd.isna(item.parcela_total):
            parcela.append('')
        else:
            parcela.append(f'{item.parcela_atual}/{item.parcela_total}')
    st.dataframe(
          pd.DataFrame({
              'Data': lista['data'].dt.strftime('%d/%m/%Y')
            , 'Descrição': lista['descricao']
            , 'Categoria': lista['categoria']
            , 'Subcategoria': lista['subcategoria']
            , 'Tipo': tipos[selecao]
            , 'Valor': [ft.reais(valor) for valor in lista['centavos']]
            , 'Parcela': parcela
            , 'Quem classificou': lista['origem']
            , 'Conta no gasto': ['sim' if conta else 'não' for conta in lista['conta_no_gasto']]
          })
        , hide_index=True
        , width='stretch'
        , height=600
    )
