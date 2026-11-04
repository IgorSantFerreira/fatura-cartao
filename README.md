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

## Privacidade

O app só atende este computador (`localhost`) e a coleta de estatísticas do Streamlit está desligada. O CSV não é enviado para lugar nenhum. `tests/dados/` tem uma fatura real usada nos testes, e `regras_usuario.json` guarda as suas escolhas: não publique esses arquivos.

## Testes

`py -m pytest -q`
