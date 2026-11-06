# Limitações, vieses e possibilidades de erro

Este documento reúne o que o "Raio-X da fatura" **não** garante. Os números vêm dos dois notebooks, que usam só dados fictícios:

- `notebooks/classificacao_despesas.ipynb`: classificação das despesas (fase 2);
- `notebooks/previsao_gastos.ipynb`: previsão do fechamento (fase 3).

## 1. Dados

- **Quase tudo foi medido com dados fictícios.** Os modelos foram desenvolvidos e avaliados com faturas inventadas pelo gerador do projeto (`ferramentas/gerar_faturas_sinteticas.py`). Existe uma única fatura real, que não entra nos notebooks: por privacidade, e porque um ciclo só não mede erro.
  - Pessoas reais podem gastar de um jeito diferente, e então os erros reais podem ser maiores que os medidos.
- **O gerador decide o que pode ser aprendido.** Os padrões dos dados fictícios foram escolhidos por nós. Dois deles foram colocados de propósito, para testar se os métodos conseguem usá-los:
  - o **dia da semana** (delivery e lazer no fim de semana, transporte em dia útil);
  - o **efeito do salário** (mais compras nos dias depois do salário).
  - Não há evidência de que pessoas reais tenham esses padrões, nem com essa intensidade.
- **Um perfil de consumo.** As faturas fictícias da fase 2 imitam uma pessoa só, que gasta mais com comida e transporte. A população da fase 3 varia quanto e quando cada pessoa gasta, mas os estabelecimentos e as categorias são os mesmos para todas.
- **Só o Nubank.** O app lê o CSV de fatura do Nubank. Outros bancos têm outros formatos e outras regras de fechamento.

## 2. Categorias (regras e modelo de classificação)

- **Regras por nome.** As regras do app reconhecem nomes conhecidos ("posto", "ifood"...). O que elas não reconhecem fica como "A classificar", e só muda de categoria quando a pessoa escolhe ou aceita uma sugestão.
- **Sugestões do modelo (Regressão Logística).**
  - **Os modelos superam o chute ingênuo** (sempre a categoria mais comum) em todas as divisões do teste (hipótese H1 do notebook).
  - **Regras + modelo não ganharam das regras sozinhas de forma consistente:**
    - em média, F1-macro de 0,748 contra 0,726;
    - foi melhor em 3 de 5 divisões (H2 não confirmada).
  - **O dia da semana e a posição no ciclo não ajudaram de forma consistente**, mesmo com o padrão posto de propósito (H3 não confirmada). O app não os usa.
- **A confiança das sugestões não é exata (H4 não confirmada).**
  - Nos estabelecimentos que as regras não reconheciam, o modelo dizia em média 56% e acertou 45%: ele tende a ser **otimista**.
  - As formas de ajuste testadas (calibração por sigmoide e por temperatura) baixaram o acerto ou pioraram o ajuste, então nenhuma foi para o app.
  - O app avisa isso ao lado das sugestões.
- **Poucos rótulos, pouco aprendizado.** O modelo do app aprende só com o que a pessoa conferiu na própria base. No começo há poucos exemplos, e a confiança dele pode ficar ainda mais longe do acerto real. Isso não foi medido.
- **Viés para o lado das regras.** A lista de conferência já vem com a categoria das regras escolhida. Quem só confirma sem olhar ensina o modelo a copiar as regras.

## 3. Previsão do fechamento (modelo de previsão)

- **O modelo é uma Random Forest treinada com 80 pessoas fictícias.** O erro foi medido em outras 40, que ele não viu. Na avaliação final (seção 8 do notebook de previsão), com 40 pessoas de teste numa população separada:
  - **com pelo menos 1 fatura anterior:**

    | Método | Erro médio |
    |---|---|
    | Projeção pelo ritmo | R$ 774 |
    | Random Forest | R$ 405 |
    | Regressão Linear | R$ 409 |

  - **com só 1 fatura anterior:** R$ 511 contra R$ 679. O ganho é real, mas incerto: são poucos casos, e o intervalo vai de R$ 13 a R$ 303 a menos de erro.
- **O modelo não ganhou de uma conta simples.** A conta é "gasto até agora + o que a pessoa costuma gastar depois deste dia do ciclo". Ela errou R$ 394 em média:
  - a Random Forest ficou R$ 11 pior (intervalo de +R$ 1 a +R$ 21; seção 8 do notebook de previsão).
  - **Leitura:** a vantagem sobre a projeção pelo ritmo vem de usar o histórico da pessoa. Os modelos aprendem isso sem ir além.
  - **Decisão do autor:** manter o modelo, na expectativa de que ele ganhe com mais dados. Essa expectativa ainda não foi testada.
- **Sem nenhuma fatura anterior, o modelo erra mais que a projeção pelo ritmo** (seção 5 do notebook de previsão). Por isso o app só mostra a previsão do modelo a partir de 1 fatura completa anterior.
- **O efeito do salário piora a projeção pelo ritmo** (erro médio +R$ 86; seção 8 do notebook de previsão). O modelo e a conta simples quase não mudam, porque o histórico da pessoa já capta o efeito. Ou seja, o ganho maior com o salário vem da projeção piorar, não de o modelo "aprender o salário".
- **A faixa provável acerta cerca de 8 em cada 10 vezes, em pessoas fictícias** (seção 9 do notebook de previsão):
  - 79% no total;
  - de 77% a 81% conforme a altura do ciclo;
  - 80% para quem tem 1 fatura anterior.
  - Com pessoas reais mais irregulares, a faixa pode ficar estreita demais.
- **Fora do que o modelo viu.** Se o gasto do ciclo ou das faturas anteriores foge muito do que existe no treino, o app não mostra o número do modelo, só a projeção pelo ritmo.
- **Só o total.** O modelo prevê o gasto total do período, não por categoria. As metas por categoria usam a projeção pelo ritmo; só o "orçamento da fatura inteira" usa o modelo.
- **Transparência do método.** Antes do notebook houve experimentos exploratórios, e as regras de decisão foram escritas depois deles. A avaliação final usa uma população de teste nova. O notebook declara as sementes descartadas e por quê.

## 4. Outras estimativas do app

- **Projeção pelo ritmo:** supõe que o gasto do dia a dia continua igual até o fechamento. Erra mais no começo do ciclo.
- **Cobranças fixas:** um gasto é considerado fixo quando se repete com o mesmo valor. Uma cobrança que muda de valor todo mês não é reconhecida.
- **Parcelas futuras:** o app supõe parcelas de mesmo valor (a última pode diferir por centavos).
- **"Fora do seu padrão":** compara com a média das faturas completas anteriores. Com uma ou duas faturas, a média é instável.

## 5. Uso e privacidade

- **Tudo fica no computador.** O app só atende o próprio computador (`localhost`) e não envia estatísticas de uso. Histórico, metas, rótulos e o modelo treinado ficam em `%LOCALAPPDATA%\fatura_cartao\`, fora do OneDrive. A exceção são as categorias escolhidas (`regras_usuario.json`, com nomes de estabelecimentos): elas ficam na pasta do app, que pode estar no OneDrive, fora do git.
- **Nada de CPF ou renda.** O app não pede CPF, renda nem nenhum dado além do CSV da fatura.
- **A pessoa decide.** Nenhuma categoria muda sem a pessoa escolher ou aceitar uma sugestão.
- **Bases separadas.** As faturas reais e as simuladas ficam em bases separadas, e uma mesma fatura não pode ser guardada nas duas.
- **Base errada.** Uma fatura aberta primeiro na base errada não é detectada. Na demonstração, o `abrir_demonstracao.bat` usa uma pasta só para ela, inclusive para "Minhas faturas".

## 6. Acessibilidade

Tudo abaixo foi verificado no navegador Edge, com faturas fictícias, nos temas claro e escuro.

- **O que foi verificado:**
  - **Auditoria automática:** o axe-core 4.10, com as regras do WCAG 2.0 e 2.1, níveis A e AA, não encontrou violações em nenhuma aba.
    - Dois pontos que ele não consegue decidir sozinho foram conferidos à parte:
      - o contraste dos títulos das abas, medido na página: 12,5:1 no tema claro e 18,1:1 no escuro;
      - um atributo interno do Streamlit no arquivo enviado (abaixo).
  - **Foco do teclado:** foi medido comparando a tela com e sem o foco, com o critério de contraste de pelo menos 3:1. Nos controles do app (abas, metas, caixas, botões, a barra lateral e a barra de botões das tabelas), o contorno de foco passa nos dois temas.
    - Nos segmentos dos campos de data e nas células das tabelas, a medição automática não conseguiu medir. As imagens saíram idênticas, com ou sem foco: o calendário aberto cobria a região, e as células focadas são desenhadas na grade, não no lugar medido.
      - **O que as capturas confirmam:** o foco visível no campo "Fechamento" e numa célula da tabela, no tema escuro.
      - **O que não foi capturado:** o campo "Considerar compras até" e o tema claro. Para eles, a conclusão vem por semelhança: é o mesmo tipo de campo do "Vencimento", que passou na medição.
  - **Só pelo teclado** (Tab, setas, Espaço e Enter):
    - trocar de aba, digitar a data e criar uma meta;
    - aceitar uma sugestão do modelo;
    - corrigir e conferir a categoria de um estabelecimento.
  - **Gráficos:** cada gráfico tem a mesma informação numa tabela, e as cores dos gráficos têm contraste de pelo menos 3:1.
- **O que foi corrigido por causa das auditorias:**
  - **Contraste no tema claro:** as legendas cinza, a variação das métricas, o tamanho do arquivo enviado e o título da aba selecionada ficavam abaixo de 4,5:1.
  - **Foco:** o contorno de foco padrão do Streamlit ficava em torno de 1,7:1, e a barra de botões das tabelas não aparecia ao receber o foco.
  - **Nomes repetidos:** as caixas "Conferido" e os campos de correção não diziam a que estabelecimento pertenciam.
- **O que não foi verificado, ou continua com limites:**
  - **Leitores de tela:** a experiência com leitores de tela (NVDA, por exemplo) não foi testada.
  - **Diálogo de arquivo:** escolher o arquivo pelo teclado abre o diálogo do sistema operacional, que não foi testado.
  - **Volta à primeira aba:** depois de salvar uma escolha, a tela volta para a primeira aba, e quem usa o teclado precisa voltar à aba onde estava.
  - **Componentes do Streamlit:** as tabelas, os seletores e o calendário são do próprio Streamlit, e o app só ajusta cores e contornos por cima deles. Um atributo do arquivo enviado (`aria-label` sem papel definido) é interno do Streamlit.
  - **Valores sobre as barras:** com muitos meses, eles ficam pequenos. A tabela logo abaixo de cada gráfico traz os mesmos valores em tamanho normal.
