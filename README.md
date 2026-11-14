# Raio-X da fatura do cartão

App local (Streamlit) que lê o CSV da fatura do cartão Nubank e mostra para onde foi o dinheiro: total por categoria (comida e bebida, transporte, assinaturas, compras, juros e multas…), o que pesa dentro de cada uma, onde você mais gastou, parcelas que ainda vão cair e uma estimativa da fatura no fechamento.

## Como abrir

1. Uma vez só: `py -m pip install -r requirements.txt` (se o comando `py` não existir no seu computador, use `python -m pip install -r requirements.txt`). O `abrir_app.bat` usa sozinho o comando que funcionar (`py`, `python` ou `python3`).
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

Com `--pessoas 60`, o gerador cria uma **população de pessoas fictícias** em `faturas_sinteticas/populacao/`, usada na previsão do fechamento. Cada pessoa tem o próprio perfil sorteado:

- quanto gasta e quantas compras faz;
- o dia de vencimento;
- as assinaturas e os dias de cobrança;
- os meses de viagem e de atraso;
- o tipo de salário (5º dia útil, dia 5, dia 10 ou quinzena), com intensidade e duração próprias do efeito do salário.

O perfil de cada pessoa fica em `perfis.csv`.

- **Efeito do salário, colocado de propósito:** as compras do dia a dia ficam mais prováveis nos dias logo depois do salário.
- **Cenário de controle:** `--sem-salario` gera as mesmas pessoas sem esse efeito.
- **Faturas da fase 2:** sem `--pessoas`, o gerador produz exatamente os mesmos arquivos de antes.

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

## Previsão do fechamento (aba Até o fechamento)

Além da estimativa pelo ritmo ("se continuar gastando assim"), o app prevê o gasto do período no fechamento com uma **Random Forest**. O modelo não aprende com as suas faturas: ele é treinado com 80 pessoas fictícias do gerador, e o erro é medido em outras 40, que ele não viu. O treino acontece na primeira vez que o app abre (cerca de meio minuto). Depois disso, o modelo fica guardado num arquivo em `%LOCALAPPDATA%\fatura_cartao\modelo_previsao\` e as aberturas seguintes são imediatas. Ele é treinado de novo sozinho se o arquivo sumir ou estiver corrompido, ou se mudar o código da previsão, do gerador ou das regras, ou a versão do Python e das bibliotecas. O arquivo tem só o modelo treinado com pessoas fictícias, nenhum dado seu.

Para prever, o modelo olha:

- o gasto deste ciclo até a data de "Considerar compras até";
- as faturas **completas** anteriores guardadas na base em uso, no máximo as 12 mais recentes.

Nada com data depois de "hoje" entra na previsão. Também ficam de fora as faturas posteriores, as que ainda não tinham fechado em "hoje" e as faturas parciais. Uma fatura que está guardada na outra base não recebe previsão: a previsão nunca mistura faturas reais e simuladas.

Nos testes, o modelo não foi melhor que uma conta simples (o gasto até agora mais o que a pessoa costuma gastar depois deste dia do ciclo): empatou numa população e ficou um pouco pior em outra. O app diz que o modelo não foi melhor que essa conta. A vantagem sobre a estimativa pelo ritmo vem de usar o histórico da pessoa.

A tela mostra:

- **gasto até agora, previsão do modelo e estimativa pelo ritmo**, lado a lado;
- a **faixa provável** no fechamento: nos testes com pessoas fictícias novas, o valor real ficou dentro dela em 79% das vezes;
- o **erro típico** do modelo e da estimativa pelo ritmo nesta altura do ciclo, ajustado ao tamanho do seu gasto.

Quando o app não mostra a previsão do modelo:

- **Histórico insuficiente:** a previsão precisa de pelo menos 1 fatura completa anterior. Sem nenhuma, nos testes o modelo errava mais que a estimativa pelo ritmo, e o app avisa e fica só com a estimativa.
- **Fora do que o modelo viu no treino:** por exemplo, um gasto deste ciclo muito acima das faturas anteriores. O app avisa em vez de extrapolar.
- **Compras do ciclo encerradas:** não há o que prever.

**Orçamento da fatura inteira:** nas metas, marque "Orçamento da fatura inteira (todas as categorias)". Quando a previsão do modelo passa desse valor, o app alerta. As metas por categoria continuam com a estimativa pelo ritmo, porque o modelo prevê só o total.

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

`notebooks/previsao_gastos.ipynb` desenvolve e avalia a previsão do fechamento com populações de pessoas fictícias geradas na hora: 80 de treino e 40 de teste, com e sem o efeito do salário. Os detalhes:

- **Retratos:** cada ciclo é visto em cada dia, com atributos calculados só com o que se sabia naquele dia. Uma trava confere que apagar o futuro não muda nada. Outra confere que a projeção linear do notebook é a mesma do app.
- **Validação:** cruzada agrupada por pessoa (nenhuma pessoa no treino e no teste ao mesmo tempo), mais uma avaliação final em 40 pessoas que não participaram de nenhuma escolha. As diferenças têm intervalo de confiança por bootstrap de pessoas.
- **Bases de comparação:** a projeção linear do app e uma referência simples sem aprendizado ("o gasto até agora mais o que a pessoa costuma gastar depois deste dia do ciclo").
- **Escolhas com regra declarada:** o histórico mínimo, os dias por ciclo no treino, as folhas da Random Forest e o modelo do app (Random Forest só se for significativamente melhor que a Regressão Linear). O notebook tem travas que falham se as constantes de `src/previsao.py` ficarem diferentes do que ele mede.
- **Transparência:**
  - **Experimentos exploratórios:** antes do notebook houve experimentos exploratórios, com as sementes 1 e 2. Os atributos e as regras foram escritos depois deles.
  - **Semente final:** a avaliação final usa uma população de teste com uma semente nova (6161), não usada em mais nada.
  - **Sementes descartadas:**
    - **2027:** veio antes da revisão.
    - **4242:** revelou que a faixa provável de quem tem 1 fatura anterior estava larga demais. A calibração foi corrigida, conferida só na população de treino, e então a semente foi trocada.
- **Resultado da execução atual** (40 pessoas de teste com pelo menos 1 fatura anterior, com o efeito do salário):
  - **MAE geral:** projeção linear R$ 774; Regressão Linear R$ 409; Random Forest R$ 405. Os dois modelos erram significativamente menos que a projeção linear.
  - **Com poucas faturas:**

    | Faturas anteriores | Random Forest | Projeção linear |
    |---|---|---|
    | 1 | R$ 511 | R$ 679 |
    | 2 | R$ 412 | R$ 798 |
    | 3 ou mais | R$ 393 | R$ 782 |

    A diferença é significativa em todas as faixas, mas as faixas de 1 e 2 faturas têm só 40 ciclos cada. Com 1 fatura, o intervalo vai de −R$ 303 a −R$ 13.
  - **Referência simples:** os modelos **não são melhores** que ela (R$ 394). Nesta população, a Random Forest ficou até um pouco pior: R$ 11 a mais, IC [+1; +21]. Numa população anterior, empatou. O ganho vem de usar o histórico da pessoa no mesmo ponto do ciclo, e os modelos aprendem isso sem ir além.
  - **Efeito do salário:** ele piora a projeção linear (o MAE sobe R$ 86). O erro dos modelos e o da referência simples quase não mudam (de R$ 1 a R$ 14). O ganho maior com o salário vem da projeção linear errar mais, não de o modelo "aprender o salário".
  - **Sem fatura anterior:** os modelos erram mais que a projeção linear. Por isso o mínimo é 1 fatura.
  - **Faixa provável:** cobre 79,0% dos casos no total, e entre 77,2% e 81,2% por faixa do ciclo.
  - **Casos fora do treino:** nenhum dos 14.120 casos de teste.
- **Limitação principal:** todas as pessoas vêm do mesmo gerador. O erro real, com pessoas reais, pode ser maior.
- **Dataset em CSV:** o notebook grava os lançamentos fictícios e as tabelas de treino e teste em `notebooks/dados_previsao/`, lê de volta e confere que são idênticas às geradas. A pasta fica fora do git, como todo CSV.

## Demonstração e limitações

- **Apresentar o app só com dados fictícios:** [docs/DEMONSTRACAO.md](docs/DEMONSTRACAO.md). O `abrir_demonstracao.bat` abre o app numa pasta só da demonstração, sem tocar nos dados reais, e prepara a base "Faturas simuladas" com 13 meses de faturas fictícias (`ferramentas/preparar_demonstracao.py`).
- **O que o app não garante** (dados fictícios, confiança não calibrada, modelo que não ganha de uma conta simples, acessibilidade verificada e não verificada): [docs/LIMITACOES.md](docs/LIMITACOES.md).
- **Contexto social, persona, ODS e impacto:** [docs/CONTEXTO_E_IMPACTO.md](docs/CONTEXTO_E_IMPACTO.md).
- **Privacidade, LGPD e vieses:** [docs/PRIVACIDADE_LGPD.md](docs/PRIVACIDADE_LGPD.md).
- **Origem:** o projeto nasceu como uso pessoal e também foi apresentado como trabalho de Machine Learning na FIAP (Global Solution 2026.2).

## Privacidade

O app só atende este computador (`localhost`) e a coleta de estatísticas do Streamlit está desligada. O app não envia o CSV para lugar nenhum.

As faturas guardadas e as metas ficam em `%LOCALAPPDATA%\fatura_cartao\`, uma pasta local que o OneDrive não sincroniza. Na pasta do app, que pode estar no OneDrive, ficam dois arquivos pessoais fora do git, que não devem ser publicados:

- `regras_usuario.json`: as suas escolhas de categoria;
- `tests/dados/`: uma fatura real, opcional. Os testes usam uma fatura fictícia (`tests/exemplo.py`); a real só serve para o teste de privacidade conferir que nenhum estabelecimento dela aparece em arquivos do repositório (sem ela, esse teste é pulado).

Os rótulos de "Minhas faturas" ficam em `%LOCALAPPDATA%\fatura_cartao\rotulos.json`.

Para mudar onde ficam os arquivos, use as variáveis de ambiente `FATURA_HISTORICO`, `FATURA_METAS`, `FATURA_REGRAS` e `FATURA_ROTULOS` (base "Minhas faturas") e `FATURA_SIMULADAS` (pasta da base simulada). O modelo da previsão fica em `FATURA_MODELO`. Essa pasta deve ser só sua, e não compartilhada nem sincronizada: o arquivo do modelo é lido como código Python (pickle).

## Testes

`py -m pytest -q`
