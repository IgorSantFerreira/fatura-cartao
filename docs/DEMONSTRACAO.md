# Roteiro de demonstração (só dados fictícios)

Para apresentar o app sem expor nenhuma fatura real. Todos os dados são 100% fictícios, criados pelo gerador do projeto.

## Como abrir

Dê dois cliques em **`abrir_demonstracao.bat`**, na pasta `fatura_cartao`. Ele:

1. aponta **todos** os dados do app para uma pasta só da demonstração (`%LOCALAPPDATA%\fatura_cartao\demonstracao\`). Isso inclui a base "Minhas faturas" e as categorias escolhidas. As suas faturas reais, metas, rótulos e categorias não são usados nem alterados, mesmo que algum passo do roteiro seja feito fora de ordem;
2. cria as faturas fictícias em `faturas_sinteticas/`, fora do git, se ainda não existirem;
3. prepara a base "Faturas simuladas" com `ferramentas/preparar_demonstracao.py --com-rotulos`:
   - guarda 13 meses de faturas fictícias, de 25/10/2025 a 25/10/2026; a última fica marcada como parcial até ser aberta;
   - confere as categorias das 3 primeiras faturas pelo gabarito do gerador, para a aba Classificar ter sugestões do modelo;
   - não sobrescreve nada que já esteja na base;
4. abre o app no navegador.

Na primeira vez, a previsão do fechamento leva cerca de meio minuto para preparar o modelo. Depois ele fica guardado no computador e as aberturas seguintes são imediatas. Vale abrir uma vez antes da apresentação.

## Durante a apresentação

1. **Base de dados:** na barra lateral, escolha **"Faturas simuladas"**. Se o arquivo for aberto antes, em "Minhas faturas", o app avisa que ele já está na outra base e não guarda nada. Mesmo assim, a pasta é só da demonstração.
2. **Arquivo:** abra `faturas_sinteticas/faturas/Nubank_2026-10-25.csv`.
3. **Data:** em **"Considerar compras até"**, digite **05/10/2026**. É o meio do ciclo, que vai de 18/09 a 17/10, e simula alguém olhando a fatura antes de ela fechar.

O que mostrar em cada aba:

| Aba | O que mostrar |
|---|---|
| **Onde foi o dinheiro** | Gasto por categoria (gráfico e tabela), tipo de gasto (recorrente, parcelado, ocasional), onde mais gastou, "gastinhos que somam". |
| **Até o fechamento** | **Previsão do fechamento**: o gasto até agora, a previsão do modelo, a projeção pelo ritmo, a faixa provável e quanto cada método costuma errar. Criar uma meta com **"Orçamento da fatura inteira"** abaixo da previsão: aparece o alerta. Também: parcelas que ainda vão cair e melhor dia de compra. |
| **Mês a mês** | Evolução por fatura, "fora do seu padrão" e assinaturas e gastos fixos achados sozinhos. |
| **Classificar** | **Sugestões do modelo** para os estabelecimentos que as regras não reconhecem, com a confiança e os nomes parecidos. Aceitar, corrigir ou rejeitar: nada muda sem a pessoa decidir. |
| **Lançamentos** | Todos os lançamentos, com categoria e tipo. |

**Um número que pode confundir:** na aba "Até o fechamento", a **"Fatura estimada no fechamento"** pode aparecer negativa. Isso acontece porque ela inclui o pagamento da fatura anterior, que entra como crédito, e o saldo anterior. O gasto do mês é o **"Gasto até agora"**, e a previsão é o **"Previsto pelo modelo no fechamento"**.

Para mostrar o aviso de **histórico insuficiente**, use uma base sem histórico. Uma forma é remover as faturas guardadas em **Mês a mês → Faturas guardadas** e abrir a fatura de novo.

## Depois da apresentação

- **Pasta da demonstração:** `%LOCALAPPDATA%\fatura_cartao\demonstracao\` pode ser apagada inteira. O `abrir_demonstracao.bat` a prepara de novo.
- **Ferramenta direto:** para usar `ferramentas/preparar_demonstracao.py` direto (sem o `.bat`), ela grava na base simulada normal do app. Ela recusa, sem gravar nada, uma pasta que coincida com algum arquivo da base "Minhas faturas", e não sobrescreve faturas, rótulos nem categorias que já existam.

## Os notebooks

- **`notebooks/classificacao_despesas.ipynb`:** como o modelo de categorias foi desenvolvido e avaliado (F1-macro, precisão, recall, matriz de confusão e calibração).
- **`notebooks/previsao_gastos.ipynb`:** como o modelo de previsão foi desenvolvido e avaliado (MAE, RMSE, comparação com a projeção linear e com a conta simples, e faixa provável).
- **Limitações:** as limitações dos dois estão em [LIMITACOES.md](LIMITACOES.md).
