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

## Privacidade

O app só atende este computador (`localhost`) e a coleta de estatísticas do Streamlit está desligada. O app não envia o CSV para lugar nenhum.

As faturas guardadas e as metas ficam em `%LOCALAPPDATA%\fatura_cartao\`, uma pasta local que o OneDrive não sincroniza. Na pasta do app, que pode estar no OneDrive, ficam dois arquivos pessoais fora do git, que não devem ser publicados:

- `regras_usuario.json`: as suas escolhas de categoria;
- `tests/dados/`: a fatura real usada nos testes.

Para mudar onde ficam os arquivos, use as variáveis de ambiente `FATURA_HISTORICO`, `FATURA_METAS` e `FATURA_REGRAS`.

## Testes

`py -m pytest -q`
