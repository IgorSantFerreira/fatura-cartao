# Fatura Inteligente do Cidadão: contexto, persona e impacto

Texto-fonte da proposta executiva da Global Solution 2026.2 (CitizenTech). Os números vêm das fontes listadas no fim, com o mês de referência de cada um.

## 1. O problema

**Recorte:** adultos que usam o cartão de crédito como principal meio de pagamento, em áreas urbanas do Brasil. Eles veem a fatura como uma lista de compras, mas não sabem para onde foi o dinheiro nem quanto o mês vai fechar.

### Evidências

**Endividamento não é o mesmo que inadimplência.**
- **Endividada**, na pesquisa da CNC, é a família que tem alguma dívida a pagar. Isso inclui compras parceladas no cartão que estão em dia.
- **Inadimplente** é quem está com contas atrasadas.
- Os dois números medem coisas diferentes e não devem ser somados nem confundidos.

| Indicador | Número | Fonte |
|---|---|---|
| Famílias com alguma dívida (endividamento) | **82,0%**, recorde da série | CNC, Peic, julho de 2026 |
| Entre as endividadas, com dívida no cartão | **85,3%**, a modalidade mais citada | CNC, Peic, julho de 2026 |
| Famílias com contas em atraso | **29,8%** | CNC, Peic, julho de 2026 |
| Famílias sem condições de pagar as dívidas atrasadas | **12,3%** | CNC, Peic, julho de 2026 |
| Pessoas inadimplentes (com contas atrasadas) | **84,2 milhões, 51,1% dos adultos** | Serasa Experian, setembro de 2026 |
| Juro médio do rotativo do cartão | **451,7% ao ano** | Banco Central, setembro de 2026 |
| Usuários de cartão que não fazem controle ativo dos gastos | **58%** | CNDL/SPC Brasil, janeiro de 2026 (600 internautas das capitais) |
| Usuários de cartão que não sabem o juro do rotativo | **78%** | CNDL/SPC Brasil, janeiro de 2026 (600 internautas das capitais) |
| Letramento financeiro dos adultos (0 a 100) | **59,6** | Banco Central/FGC, metodologia OCDE, 2023 |

Desde janeiro de 2024, a lei limita o total de juros e encargos do rotativo e do parcelamento da fatura ao valor original da dívida (Lei 14.690/2023, art. 28). Mesmo assim, uma dívida de R$ 1.000 no rotativo pode chegar a R$ 2.000.

### O que a solução enfrenta

**O que este projeto não afirma:** que a falta de organização financeira **causa** o endividamento. Renda, preços, emprego e acesso a crédito também pesam, e as pesquisas acima não medem essa causalidade.

**O problema concreto que a solução enfrenta é a falta de visibilidade e de previsibilidade.**
- A fatura chega como uma lista de nomes pouco claros ("Pag\*", "Mp \*", "Ec \*") e um total.
- Ela não mostra para onde foi o dinheiro, o que é fixo e o que ainda vai cair.
- Ela não mostra se o mês vai fechar acima do que a pessoa consegue pagar.
- A fatura aberta mostra as compras feitas até agora, mas não quanto o mês deve fechar. Sem essa estimativa, passar do orçamento pode ficar visível só no fechamento, quando já não dá para ajustar o consumo.

Na pesquisa da CNDL/SPC (internautas das capitais), mais da metade dos usuários de cartão não acompanha os gastos, e a maioria não sabe o custo do rotativo. Informação clara e antecipada é, então, uma condição para decidir melhor. Não é garantia de que a dívida vai cair.

## 2. Persona

**Lucas, 28 anos, analista administrativo em São Paulo.** A persona é fictícia.

**Baseado em dados de pesquisa** (o perfil que ele representa; são estatísticas de grupo, não fatos medidos sobre ele):
- adulto que trabalha e usa o cartão de crédito no dia a dia;
- não faz controle ativo dos gastos com o cartão, como 58% dos usuários ouvidos pela CNDL/SPC;
- não sabe quanto custa o rotativo, como 78% dos usuários ouvidos pela CNDL/SPC;
- tem dívida no cartão, que é a modalidade mais comum (85,3% das famílias endividadas, CNC).

**O que é ilustrativo** (para dar rosto ao problema, sem medição):
- **renda e salário:** cerca de R$ 4.500 por mês, com salário no 5º dia útil;
- **uso do cartão:** quase tudo passa por ele, como delivery, aplicativo de transporte, combustível, mercado e quatro assinaturas;
- **como se sente:** "Eu ganho razoavelmente, mas no fim do mês não sei para onde foi o dinheiro";
- **histórico:** duas vezes no último ano pagou só o mínimo da fatura, e uma vez atrasou;
- **o que já tentou:** uma planilha, que abandonou, e o app do banco, que lista as compras mas não diz se o mês vai estourar.

**Necessidades:**
1. entender em um minuto para onde foi o dinheiro;
2. saber no meio do mês se a fatura vai passar do orçamento;
3. ser avisado a tempo;
4. não entregar a senha do banco para ninguém.

## 3. Público beneficiado e ecossistema

Organizado pela relação de cada um com o produto. Nenhuma parceria institucional foi formalizada. Os papéis abaixo descrevem quem poderia participar.

| Relação com o produto | Quem | Papel |
|---|---|---|
| **Usa diretamente** | Adultos que usam cartão de crédito, como o Lucas | Abre a fatura, define o orçamento e decide as categorias |
| **Beneficiado indiretamente** | Família e dependentes de quem usa | Orçamento doméstico mais previsível |
| **Necessário para funcionar** | Emissor do cartão que oferece a exportação da fatura em CSV (hoje, o Nubank) | Fonte dos dados. O app usa o arquivo que o próprio banco oferece, sem integração nem acordo com ele |
| **Necessário para funcionar** | Mantenedores do software (hoje, o autor) | Código, testes, documentação e atualização das regras de categoria |
| **Canal de difusão possível** | Educadores financeiros, escolas, ONGs e programas de educação financeira | Usar o app em oficinas com a fatura do próprio participante |
| **Interesse público relacionado, sem parceria** | Banco Central (cidadania financeira), Procons e Idec (defesa do consumidor) | Objetivos alinhados, como consumidor informado e menos inadimplência. Não há relação formal com o projeto |

## 4. Solução

O **Raio-X da fatura** é um aplicativo gratuito que roda no computador da pessoa. Ela exporta o CSV da fatura do Nubank e abre no app.

**Funcionalidades:**
- **Onde foi o dinheiro:** gasto por categoria e por tipo (recorrente, parcelado e ocasional), em português simples.
- **Previsão do fechamento:** no meio do ciclo, o app estima por dois métodos quanto a fatura vai fechar.
  - **Ritmo de gasto:** supõe que a pessoa continua gastando no mesmo ritmo até o fechamento.
  - **Modelo de aprendizado de máquina:** usa o histórico da pessoa.
  - Junto com o número, o app mostra uma faixa provável e quanto cada método costuma errar.
- **Alerta de orçamento:** quando a previsão passa do limite definido pela pessoa, o app avisa antes do fechamento.
- **Sugestões de categoria:** para os nomes que as regras não reconhecem, o modelo sugere uma categoria. A pessoa aceita, corrige ou rejeita.

**Dados usados e informações entregues:**

| Dados usados | Informações entregues |
|---|---|
| O CSV da fatura (data, descrição e valor de cada lançamento) | Gastos por categoria |
| As faturas anteriores que a pessoa guardou no app | Previsão do fechamento e faixa provável |
| As categorias que a pessoa confirmou | Alerta de orçamento |
| | Parcelas futuras e assinaturas |
| | Comparação com a média dos meses anteriores |

**Acessibilidade:**
- **Pouca conectividade:**
  - **o que já existe:** o app roda inteiro no computador e o código dele não faz nenhuma chamada à internet. Isso não foi testado com a rede desligada;
  - **o limite:** a instalação inicial precisa de internet (Python e bibliotecas).
- **Pouco letramento digital:**
  - **o que já existe:** os textos estão em português simples; o app explica cada número e mostra avisos quando não há dados suficientes;
  - **o limite:** hoje o app precisa ser instalado num computador. Um instalador e uma versão para celular são próximos passos.
- **Deficiência:**
  - **o que já existe:** a auditoria automática (axe-core, WCAG 2.1 A e AA, temas claro e escuro) não encontrou violações. O app funciona só pelo teclado, com foco visível. Cada gráfico tem uma tabela com os mesmos dados;
  - **o limite:** não foi testado com leitor de tela.

## 5. Benefícios, impactos e ODS

**Benefícios esperados para a pessoa:**
- entender os próprios gastos;
- decidir antes do fechamento, e não depois;
- evitar surpresas na fatura;
- reduzir o risco de recorrer ao rotativo ou atrasar a fatura.

**O que é contribuição potencial e o que é impacto comprovado.**
- **Contribuição potencial:** os benefícios acima. Eles ainda não foram medidos com pessoas reais. O projeto **não afirma** que reduz a inadimplência.
- **Medido em dados sintéticos** (não é desempenho comprovado com pessoas reais):
  - **previsão:** a previsão do fechamento errou menos que a estimativa pelo ritmo;
  - **classificação:** as regras somadas a um modelo tiveram desempenho próximo ao das regras sozinhas;
  - os números e os limites estão na seção 6.

**Indicadores para um piloto futuro:**

| Indicador | Como medir |
|---|---|
| Pessoas que sabem dizer suas 3 maiores categorias de gasto | Pergunta antes e depois de 1 mês de uso |
| Alertas de orçamento recebidos antes do fechamento | Contagem no próprio app (local) |
| Faturas pagas no rotativo ou com atraso | 3 faturas antes e 3 depois do uso |
| Juros, multa e IOF por atraso pagos | Linha "Juros, multas e IOF" do app, antes e depois |
| Erro da previsão com faturas reais | Previsão comparada ao valor final, com consentimento |

**ODS, revisados.** O edital pede poucos ODS, com relação clara ao problema. O projeto reivindica um só.

| ODS | Meta | Por que a conexão é defensável | Indicadores ligados |
|---|---|---|---|
| **ODS 10, Redução das desigualdades** (um dos 7 destacados no edital) | 10.2: empoderar e promover a inclusão social e econômica de todos, independentemente de idade, gênero, raça, condição econômica ou outra | O app dá a qualquer pessoa, de graça e sem senha de banco, uma análise da própria fatura que costuma depender de planilha, de conhecimento financeiro ou de apps que pedem acesso à conta. É uma contribuição potencial para a autonomia econômica | Pessoas que sabem dizer suas 3 maiores categorias; faturas pagas no rotativo ou com atraso |

**Considerados e não reivindicados:**
- **ODS 1 (meta 1.4)** e **ODS 8 (meta 8.10):** as duas metas tratam de **ampliar o acesso** a serviços financeiros. O app não amplia esse acesso: ele só apoia o uso informado de um cartão que a pessoa já tem.
- **ODS 4:** o app explica os números, mas não é uma ação de educação. O dado de letramento financeiro (59,6) entra só como contexto do problema.
- **Os demais destacados no edital** (2, 3, 9, 11 e 13) não têm relação direta com o problema.

**Como ampliar:** um instalador simples, leitura de faturas de outros bancos e uma versão para celular. O próximo passo é um piloto com voluntários, com consentimento, para medir os indicadores acima com pessoas reais.

## 6. Resultados técnicos (dados sintéticos)

| Tarefa | Método | Resultado |
|---|---|---|
| **Categorias** (F1-macro, validação cruzada por estabelecimento) | Regras do app | 0,726 ± 0,114 |
| | Regras + modelo (escolhido dentro de cada divisão: Regressão Logística em 3, Random Forest em 2; o app usa Regressão Logística) | 0,748 ± 0,171. Melhor em 3 de 5 divisões; o ganho não é consistente |
| **Fechamento** (MAE nas 40 pessoas de teste, com pelo menos 1 fatura anterior) | Projeção pelo ritmo | R$ 774 |
| | Regressão Linear | R$ 409 |
| | Random Forest | R$ 405 (o modelo do app, mesma configuração treinada com outra população fictícia: R$ 395) |
| | Referência simples (o histórico da pessoa) | R$ 394 |

**Leitura:** o aprendizado de máquina errou cerca de metade do que erra a projeção pelo ritmo, mas **não superou** a referência simples que usa o histórico da pessoa: a Random Forest ficou R$ 11 pior, uma diferença pequena, mas estatisticamente significativa. Todos esses números vêm de pessoas fictícias e **não** representam desempenho comprovado com cidadãos reais.

**Por que o app mantém o aprendizado de máquina:** a hipótese do projeto é que, com pessoas reais, de padrões mais variados que os do gerador, o modelo possa ir além da regra simples. Essa hipótese não está comprovada. Num piloto, a referência simples continua sendo a comparação obrigatória.

**Ordem no tempo:** com um corte no calendário (treino só com ciclos antigos, teste só com ciclos posteriores), o padrão se manteve: Random Forest R$ 388, projeção pelo ritmo R$ 783 e referência simples R$ 362 (notebook, seção 8).

## 7. Privacidade

O processamento é local: o app roda no computador da pessoa e não envia dados a nenhum servidor do projeto. Isso **não** quer dizer que nenhum dado sai do computador. Se a pessoa guardar o CSV da fatura, ou a pasta do app, numa pasta sincronizada (OneDrive, Google Drive), esses arquivos seguem a configuração de nuvem dela.

Os detalhes estão em [PRIVACIDADE_LGPD.md](PRIVACIDADE_LGPD.md), e as limitações em [LIMITACOES.md](LIMITACOES.md).

## Fontes

1. **CNC, Pesquisa de Endividamento e Inadimplência do Consumidor (Peic), julho de 2026.**
   - Endividamento 82,0%, contas em atraso 29,8%, sem condições de pagar 12,3%: Fecomércio-SC, relatório Peic de julho de 2026, com os resultados nacionais. https://www.fecomercio-sc.com.br/wp-content/uploads/2026/08/202607_PEIC.pdf
   - Cartão 85,3%: Agência Brasil, 06/08/2026. https://agenciabrasil.ebc.com.br/economia/noticia/2026-08/cnc-endividamento-das-familias-sobe-para-82-mas-inadimplencia-cai
2. **Serasa Experian, Indicador de Inadimplência do Consumidor, setembro de 2026.** https://www.serasaexperian.com.br/conteudos/indicadores-economicos/
3. **Banco Central do Brasil, estatísticas de crédito de setembro de 2026, divulgadas em 29/10/2026,** pela imprensa (a nota do Banco Central não foi localizada). WSCOM, 30/10/2026. https://wscom.com.br/economia/2026/10/30/juro-do-rotativo-do-cartao-de-credito-sobe-para-4517-ao-ano-em-setembro-aponta-banco-central/
4. **Lei nº 14.690, de 3 de outubro de 2023, art. 28, § 1º.** https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/lei/l14690.htm
5. **CNDL/SPC Brasil e Offerwise, pesquisa sobre o cartão de crédito.** 600 internautas das 27 capitais; coleta de 2 a 9/01/2026; publicada em 23/04/2026. https://cndl.org.br/varejosa/58-dos-consumidores-nao-controlam-gastos-com-cartao-de-credito-aponta-cndl-spc-brasil/
6. **Banco Central e FGC, letramento e inclusão financeira de adultos** (metodologia OCDE/INFE), março e abril de 2023. Agência Gov, 21/11/2023. https://agenciagov.ebc.com.br/noticias/202311/inclusao-financeira-do-brasileiro-avanca-mas-letramento-financeiro-ainda-pode-melhorar
7. **Nações Unidas no Brasil, Objetivos de Desenvolvimento Sustentável.** https://brasil.un.org/pt-br/sdgs
