# Raio-X da fatura do cartão

App local (Streamlit) que lê o CSV da fatura do cartão Nubank e mostra para onde foi o dinheiro: total por categoria (comida e bebida, transporte, assinaturas, compras, juros e multas…), o que pesa dentro de cada uma, onde você mais gastou, parcelas que ainda vão cair e uma estimativa da fatura no fechamento.

## Como abrir

1. Uma vez só: `py -m pip install -r requirements.txt`
2. Dê dois cliques em `abrir_app.bat`. O navegador abre em `http://localhost:8501`.
3. Selecione o CSV exportado do Nubank (ex.: `Nubank_2026-11-25.csv`).

Para parar o app, feche a janela preta do `abrir_app.bat`.

## Como ler os números

- **Gasto no período**: compras + juros/multas/IOF − estornos. **Não** entram o "Pagamento recebido" nem o "Valor pendente do mês anterior", que são a fatura passada. A linha "Conferência" mostra que a soma do CSV fecha com esses três pedaços.
- **A classificar**: o app não chuta. Estabelecimento que ele não reconhece fica nessa categoria até você escolher uma na aba **Classificar**. A escolha vale para o estabelecimento e fica salva em `regras_usuario.json`, que é usado nas próximas faturas.
- **Até o fechamento**: o vencimento vem do nome do arquivo e o fechamento é 7 dias antes (padrão do Nubank). As duas datas podem ser corrigidas na barra lateral. A estimativa supõe que o gasto do dia a dia continua no mesmo ritmo. Parcelas, assinaturas, juros e estornos ficam fora desse ritmo. A "fatura estimada" soma também o saldo anterior e os pagamentos já lançados. Só entram lançamentos até a data de "Considerar compras até".
- **Estornos** voltam para a categoria da compra original (ex.: estorno do iFood reduz Comida; estorno de juros reduz Juros, multas e IOF).
- **Gastinhos que somam**: quantas das compras do dia a dia ficaram até a mediana delas (metade custou até esse valor) e quanto essas compras pequenas somam.

## Metas

Na aba **Até o fechamento**, crie uma meta com uma ou mais categorias (ex.: Comida e bebida + Transporte = R$ 1.400). O app mostra quanto já foi, quanto ainda dá para gastar por dia até o fechamento e se, no ritmo atual, a meta estoura. Nesse caso aparece um aviso no topo. As metas ficam em `%LOCALAPPDATA%\fatura_cartao\metas_usuario.json`.

## Melhor dia de compra e parcelas

Ainda em **Até o fechamento**:

- **Melhor dia de compra**: é o dia do fechamento (regra do Nubank). O app mostra o próximo, em que fatura a compra cai e quantos dias até pagar.
- **Já comprometido nas próximas faturas**: quanto de cada fatura seguinte já está tomado pelas parcelas.

## Histórico (aba Mês a mês)

Toda fatura aberta com vencimento conhecido é guardada em `%LOCALAPPDATA%\fatura_cartao\historico\`, uma por vencimento. Reabrir não duplica. Uma exportação mais nova da mesma fatura substitui a guardada. Uma mais velha não apaga lançamentos: se ela só tem lançamentos a menos ou termina antes, o app mantém a guardada e avisa.

A aba mostra:

- a fatura atual comparada com a média das faturas anteriores completas;
- o gasto de cada fatura;
- as **assinaturas e gastos fixos**: o que se repete com o mesmo valor todo mês, mais as assinaturas reconhecidas pelo nome, com o custo por mês e por ano. Uma compra habitual de mesmo valor uma vez por mês (ex.: o mesmo prato no mesmo restaurante) também aparece como "repete todo mês". Se o valor de uma assinatura muda (reajuste, cobrança em dólar), o total usa só o valor mais recente. Uma fatura ainda aberta não tira do total o que só não foi cobrado ainda.

Uma fatura guardada antes do fechamento fica marcada como **parcial** e não entra na média. Para completá-la, abra no app, depois do fechamento, a exportação nova (ou o mesmo arquivo, se nada mudou). Também dá para adicionar faturas antigas de uma vez ou remover uma fatura do histórico.

## Tipo de gasto

Além da categoria (em quê), cada lançamento tem um tipo (como): **recorrente** (cobrança fixa detectada), **parcelado**, **ocasional**, **encargo** (juros, multa, IOF), **estorno** ou **movimento da fatura** (pagamento e saldo anterior). O resumo por tipo fica em **Onde foi o dinheiro**, e o filtro por tipo em **Lançamentos**.

Na aba **Mês a mês** também aparecem:

- a evolução de uma categoria escolhida ao longo das faturas;
- **Fora do seu padrão**: as categorias em que esta fatura passa do maior valor ou fica abaixo do menor valor das faturas completas anteriores.

O "Fora do seu padrão" precisa de pelo menos 2 faturas completas anteriores, e "A classificar" e estornos ficam de fora. Se os meses fossem parecidos entre si, cada categoria ficaria fora do intervalo por acaso 2 vezes em n+1, onde n é o número de faturas anteriores. A tela mostra quantos avisos isso dá por acaso: com 2 faturas anteriores e 9 categorias, uns 6.

## Bases de dados e faturas simuladas

Na barra lateral, **Base de dados** escolhe entre:

- **Minhas faturas**: as reais;
- **Faturas simuladas**: para demonstração e para treinar o ML.

Cada base tem o próprio histórico, metas, categorias escolhidas e rótulos. Cada uma tem também o próprio campo de arquivo: ao trocar de base, a fatura aberta não vai junto e precisa ser aberta de novo. Só assim ela é guardada na outra base. A base simulada fica em `%LOCALAPPDATA%\fatura_cartao\simuladas\`.

**Atenção:** o app sempre começa em "Minhas faturas". Um arquivo simulado aberto ali é guardado como fatura real. Se isso acontecer, remova-o em **Mês a mês → Faturas guardadas**.

Para criar faturas simuladas:

- **Formato**: o mesmo do Nubank, com o cabeçalho `date,title,amount`. A data é `AAAA-MM-DD`. O valor pode ser `"12,90"` (vírgula decimal, entre aspas) ou `12.90`. Crédito tem valor negativo.
- **Nome do arquivo**: `Nubank_AAAA-MM-DD.csv`, com a data de **vencimento**. Use uma fatura por mês, com vencimentos diferentes.
- **Conteúdo realista**: inclua parcelas (`Loja X - Parcela 2/5`), assinaturas, `Pagamento recebido`, estornos e, principalmente, estabelecimentos que as regras do app não conhecem. É neles que o modelo mostra se aprende algo além das regras.
- **Abrir no app**: escolha "Faturas simuladas" na barra lateral **antes** de abrir os arquivos. Faturas antigas podem ser adicionadas de uma vez em **Mês a mês → Adicionar faturas antigas**.

### Gerador de faturas sintéticas

`py ferramentas/gerar_faturas_sinteticas.py` cria 13 faturas 100% fictícias em `faturas_sinteticas/`, com um `gabarito.csv` (categoria certa de cada lançamento) e um `LEIA-ME.txt`. Para gerar mais meses, use `--meses 36`.

- A semente é fixa: rodar de novo gera os mesmos arquivos.
- O perfil de gasto é parecido com o de uma pessoa real, mas nenhum estabelecimento ou valor é copiado.
- A pasta gerada fica fora do git, como todo CSV.

## Rótulos para o ML (aba Classificar)

Em **Conferir categorias**, marque "conferido" em cada estabelecimento depois de confirmar a categoria, **inclusive quando o app já acertou**. Só os conferidos viram exemplos para treinar e avaliar o modelo. Sem essa confirmação, o modelo apenas copiaria as regras do app.

As escolhas feitas em "A classificar" e em "Corrigir" também contam como conferidas. O rótulo vale para o estabelecimento: todas as compras do mesmo lugar ficam com a mesma categoria.

O botão **Baixar lançamentos rotulados** gera o CSV usado no notebook. Além da categoria conferida, o CSV traz:

- `categoria_regras`: a categoria que as regras dariam sozinhas, usada como base de comparação;
- `origem`: de onde veio o rótulo (confirmou a categoria do app, trocou na conferência, A classificar ou Corrigir), junto com a data;
- `base`: de qual base de dados é o lançamento.

A origem permite medir quantos rótulos só confirmaram a sugestão do app. A lista de conferência já vem com a categoria das regras escolhida, e isso puxa os rótulos para o lado das regras.

## Sugestões do modelo (aba Classificar)

Quando a base tem estabelecimentos conferidos em pelo menos 2 categorias, um modelo de **Regressão Logística** aprende com eles e sugere uma categoria para cada estabelecimento "A classificar" da fatura aberta. Cada sugestão vem com:

- a **confiança** do modelo;
- uma pista: os estabelecimentos que você já conferiu com nome mais parecido. Não é o motivo da sugestão; o modelo também usa o valor e quantas vezes o estabelecimento aparece.

Para cada sugestão há quatro opções:

- **Aceitar**: a categoria passa a valer e vira rótulo, com origem "aceitou sugestão do modelo".
- **Corrigir**: você escolhe a categoria certa.
- **Rejeitar**: o lançamento continua "A classificar" e essa sugestão não aparece mais para aquele estabelecimento.
- **Decidir depois**.

Nada muda de categoria sem você aceitar.

O modelo usa o nome do estabelecimento (pedaços de 2 a 4 letras), o valor, em quantas faturas o estabelecimento aparece, se o valor se repete e se é parcela. O CSV do Nubank não tem horário. O dia da semana e a posição no ciclo foram testados no notebook e não ajudaram de forma consistente, mesmo com um padrão de dia da semana colocado de propósito nas faturas sintéticas; o app usa o modelo sem eles.

A confiança mostrada **não é calibrada** e tende a ser otimista. O app cita os números medidos no notebook (guardados em `src/modelo.py`, `CALIBRACAO_SUGESTOES`): nos 31 estabelecimentos que as regras não reconheciam, o modelo dizia em média 56% e acertou 45%. As calibrações testadas (sigmoide e temperatura) ou baixaram o acerto ou pioraram a calibração, então nenhuma foi para o app.

## Experimento de ML (notebook)

`notebooks/classificacao_despesas.ipynb` desenvolve e avalia a classificação com as faturas sintéticas. Se elas faltarem, o notebook as recria com o gerador. Os detalhes:

- **Validação cruzada:** agrupada por estabelecimento. Nenhum estabelecimento aparece no treino e no teste ao mesmo tempo.
- **Bases de comparação:** a classe mais comum e as regras do app.
- **Modelos:** Regressão Logística e Random Forest, com e sem contexto temporal. Os hiperparâmetros são escolhidos por busca com validação aninhada.
- **Escolha do modelo do app:** totalmente aninhada (a escolha entre modelos também é feita dentro de cada dobra), para que a nota não seja otimista. O notebook tem travas que falham se a configuração ou os números de confiança em `src/modelo.py` ficarem diferentes do que ele calcula.
- **Métricas:** F1-macro, precisão, recall, matriz de confusão e calibração (curva de confiabilidade, ECE e Brier).
- **Conclusão:** a resposta a cada hipótese, com critério definido antes, e as limitações. Resumo da execução atual: os modelos ficam bem acima do chute ingênuo; regras + modelo ganham das regras em média (F1-macro 0,748 contra 0,726), mas não em todas as dobras; o contexto temporal não ajudou de forma consistente; a confiança não ficou calibrada.
- **Dados:** as faturas sintéticas têm um padrão de dia da semana colocado pelo gerador (delivery e lazer mais no fim de semana, estacionamento e transporte em dia útil). Ele serve para testar se o método consegue usar contexto temporal; não diz nada sobre pessoas reais.

Para rodar de novo: abra o notebook na pasta `notebooks/` e execute tudo. Ele usa só dados fictícios.

## Privacidade

O app só atende este computador (`localhost`) e a coleta de estatísticas do Streamlit está desligada. O app não envia o CSV para lugar nenhum.

As faturas guardadas e as metas ficam em `%LOCALAPPDATA%\fatura_cartao\`, uma pasta local que o OneDrive não sincroniza. Na pasta do app, que pode estar no OneDrive, ficam dois arquivos pessoais fora do git, que não devem ser publicados:

- `regras_usuario.json`: as suas escolhas de categoria;
- `tests/dados/`: uma fatura real, opcional. Os testes usam uma fatura fictícia (`tests/exemplo.py`); a real só serve para o teste de privacidade conferir que nenhum estabelecimento dela aparece em arquivos do repositório (sem ela, esse teste é pulado).

Os rótulos de "Minhas faturas" ficam em `%LOCALAPPDATA%\fatura_cartao\rotulos.json`.

Para mudar onde ficam os arquivos, use as variáveis de ambiente `FATURA_HISTORICO`, `FATURA_METAS`, `FATURA_REGRAS` e `FATURA_ROTULOS` (base "Minhas faturas") e `FATURA_SIMULADAS` (pasta da base simulada).

## Testes

`py -m pytest -q`
