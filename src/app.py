# Tela do app. Rodar com abrir_app.bat (ou: py -m streamlit run src/app.py).

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import fatura as ft


PASTA_APP = Path(__file__).resolve().parent.parent
ARQUIVO_REGRAS = os.environ.get('FATURA_REGRAS', str(PASTA_APP / 'regras_usuario.json'))
COR_BARRA = '#2a78d6'
VOLTAR_AUTOMATICA = 'Voltar para a categoria automática'


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

if 'mensagem' in st.session_state:
    st.success(st.session_state.pop('mensagem'))

arquivo = st.file_uploader('Escolha o CSV da fatura do cartão Nubank', type=['csv'])
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

aba_resumo, aba_ciclo, aba_classificar, aba_lancamentos = st.tabs(
    ['Onde foi o dinheiro', 'Até o fechamento', 'Classificar', 'Lançamentos']
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


# ---------------------------------------------------------------- aba: até o fechamento

with aba_ciclo:
    if vencimento is None or fechamento is None:
        st.info('O nome do arquivo não traz a data de vencimento. Informe o vencimento na barra lateral para ver o ciclo.')
    elif fechamento >= vencimento:
        st.error('O fechamento precisa ser antes do vencimento. Corrija as datas na barra lateral.')
    else:
        datas = ft.ciclo(vencimento, fechamento)
        resultado = ft.projecao(fatura, datas['inicio'], datas['ultimo_dia'], hoje)
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
                mudou = 0
                for chave, nome, descricao, centavos, total, quantidade in grupos:
                    escolha = st.session_state['classificar_' + chave]
                    if escolha != ft.A_CLASSIFICAR:
                        novas = ft.aplicar_escolha(novas, descricao, centavos, escolha)
                        mudou = mudou + 1
                if mudou == 0:
                    st.info('Nenhuma categoria escolhida.')
                else:
                    ft.salvar_regras_usuario(ARQUIVO_REGRAS, novas)
                    st.session_state['mensagem'] = f'{mudou} estabelecimento(s) classificado(s).'
                    st.rerun()

        st.subheader('Corrigir a categoria de um estabelecimento')
        estabelecimentos = fatura.drop_duplicates('chave')
        rotulos = {}
        for item in estabelecimentos.itertuples(index=False):
            rotulos[item.chave] = f'{item.estabelecimento} (hoje: {item.categoria})'
        chave_escolhida = st.selectbox(
              'Estabelecimento'
            , options=list(rotulos.keys())
            , format_func=rotulos.get
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
            else:
                novas = ft.aplicar_escolha(novas, exemplo['descricao'], int(exemplo['centavos']), nova_categoria)
            ft.salvar_regras_usuario(ARQUIVO_REGRAS, novas)
            st.session_state['mensagem'] = f'Categoria de {ft.escapar_markdown(exemplo["estabelecimento"])} salva.'
            st.rerun()

        if regras_usuario:
            st.caption(f'{len(regras_usuario)} estabelecimento(s) com categoria escolhida por você, salvos em {ft.escapar_markdown(ARQUIVO_REGRAS)}.')


# ---------------------------------------------------------------- aba: lançamentos

with aba_lancamentos:
    filtro = st.multiselect('Filtrar categorias', options=ft.CATEGORIAS, key='filtro_categorias')
    lista = fatura
    if filtro:
        lista = fatura[fatura['categoria'].isin(filtro)]
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
            , 'Valor': [ft.reais(valor) for valor in lista['centavos']]
            , 'Parcela': parcela
            , 'Quem classificou': lista['origem']
            , 'Conta no gasto': ['sim' if conta else 'não' for conta in lista['conta_no_gasto']]
          })
        , hide_index=True
        , width='stretch'
        , height=600
    )
