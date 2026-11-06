# Fatura Inteligente do Cidadão: contexto, persona e impacto

Este documento é o texto-fonte do resumo executivo (PDF). Os números vêm das fontes listadas no fim, com o mês de referência de cada um.

## 1. O problema: o cartão é a principal dívida do brasileiro, e pouca gente acompanha os próprios gastos

- **82% das famílias brasileiras estavam endividadas em julho de 2026**, o maior patamar da série histórica. Entre elas, **85,3% tinham dívida no cartão de crédito**, de longe a modalidade mais citada. **29,8% das famílias tinham contas em atraso** (CNC, Peic, julho de 2026).
- **84,2 milhões de brasileiros estavam inadimplentes em setembro de 2026**, ou **51,1% da população adulta**. É o recorde da série (Serasa Experian, setembro de 2026).
- **O juro médio do rotativo do cartão chegou a 451,7% ao ano em setembro de 2026** (Banco Central, divulgado em 29/10/2026). Desde 2024, a lei limita o total de juros e encargos do rotativo e do parcelamento da fatura ao valor original da dívida (Lei 14.690/2023, art. 28). Na prática, uma dívida de R$ 1.000 no rotativo ainda pode virar R$ 2.000.
- **58% dos usuários de cartão não fazem nenhum controle ativo dos gastos, e 78% não sabem a taxa de juros do rotativo.** No último ano, **30% foram negativados por causa do cartão.** (CNDL/SPC Brasil e Offerwise; 600 internautas das capitais; coleta de 2 a 9 de janeiro de 2026)
- **No letramento financeiro dos adultos, o Brasil tirou nota média de 59,6 numa escala de 0 a 100.** A pesquisa, de março e abril de 2023, é do Banco Central com o FGC e seguiu a metodologia internacional da OCDE/INFE.

**Leitura.** O cartão é, ao mesmo tempo, o meio de pagamento do dia a dia e a principal porta de entrada para a dívida cara. O problema não é só falta de dinheiro: é **falta de visibilidade**. A fatura chega como uma lista de nomes pouco claros ("Pag*", "Mp *", "Ec *") e um total. Ela não diz para onde o dinheiro foi, o que é fixo, o que ainda vai cair nem se o mês vai fechar acima do que a pessoa consegue pagar.

## 2. A solução: o Raio-X da fatura

Um aplicativo gratuito, que roda no próprio computador, para quem tem cartão Nubank. Basta exportar o CSV da fatura e abrir no app.

- **Onde foi o dinheiro.** Gasto por categoria, explicado em português simples. Separa o que é **recorrente** (assinaturas), **parcelado** e **ocasional**, e destaca os "gastinhos que somam".
- **Quanto a fatura vai fechar.** Antes do fechamento, o app estima o total do mês por dois caminhos:
  - a estimativa pelo ritmo de gasto;
  - uma previsão por **aprendizado de máquina** que usa o histórico da pessoa.
  - Mostra também uma faixa provável e quanto cada método costuma errar.
- **Alerta de orçamento.** A pessoa define um limite para a fatura ou para categorias, e o app avisa quando a previsão passa do limite. O aviso chega a tempo de mudar o comportamento, e não depois da fatura fechada.
- **Categorias com ajuda do modelo.** Para nomes que o app não reconhece, um modelo sugere a categoria. A pessoa aceita, corrige ou rejeita: **nada muda sem ela decidir**.
- **Privacidade por padrão.** Os dados não saem do computador. O app não pede CPF, renda nem senha de banco.

**O que já foi medido** (com pessoas fictícias; detalhes em [LIMITACOES.md](LIMITACOES.md)):
- **Com pelo menos uma fatura anterior,** a previsão errou em média cerca de R$ 405 por fatura, contra R$ 774 da estimativa pelo ritmo.
- **Com 0 faturas anteriores,** o app avisa que ainda não há histórico suficiente e mostra só a estimativa pelo ritmo.
- **A faixa provável** acertou em cerca de 8 de cada 10 vezes.

## 3. Persona

**Lucas, 28 anos, analista administrativo em São Paulo** (persona fictícia).

- **Perfil:** renda de cerca de R$ 4.500 por mês, salário no 5º dia útil. Usa o cartão para quase tudo: delivery, aplicativo de transporte, combustível, mercado e quatro assinaturas de streaming e de academia.
- **Como se sente:** "Eu ganho razoavelmente, mas no fim do mês não sei para onde foi o dinheiro." Abre a fatura, vê o total e sente que ela "sempre vem mais alta do que eu imaginava".
- **O que já aconteceu:** duas vezes no último ano, pagou só o mínimo e entrou no rotativo, sem saber quanto de juros pagaria. Uma vez atrasou a fatura e pagou multa e juros.
- **O que já tentou:** planilha (abandonou em duas semanas) e o app do banco, que mostra a lista de compras, mas não diz se o mês vai fechar acima do que ele consegue pagar.
- **O que ele quer:**
  1. entender em 1 minuto onde o dinheiro foi;
  2. saber, no meio do mês, se a fatura vai estourar;
  3. ser avisado a tempo;
  4. não entregar a senha do banco para ninguém.
- **Como o app ajudaria** (ilustração, com os valores do exemplo):
  - Lucas veria que comida e transporte somam metade do gasto;
  - veria que os pedidos de delivery pequenos, juntos, passam de R$ 300;
  - receberia o aviso, ainda no meio do ciclo, de que a fatura deve fechar acima do orçamento que ele definiu;
  - veria quanto das próximas faturas as parcelas já comprometeram.

Lucas representa o público que mais aparece nas pesquisas: adulto, trabalhador, que usa o cartão como principal forma de pagamento e de crédito, e que não faz controle ativo dos gastos.

## 4. Stakeholders (partes interessadas)

| Parte interessada | O que ganha | O que precisa ver no projeto |
|---|---|---|
| **Cidadão usuário** (como o Lucas) | Entender e prever os gastos, evitar rotativo e atraso | Linguagem simples, privacidade, controle sobre as categorias |
| **Família e dependentes** | Orçamento doméstico mais previsível | Alertas claros, nada de jargão |
| **Educadores financeiros, escolas e faculdades** | Uma ferramenta concreta para ensinar com a fatura real do aluno | Explicações e limitações transparentes |
| **Organizações de defesa do consumidor (Procons, Idec)** | Consumidores mais informados sobre juros e parcelas | Nenhum conflito de interesse (o app não oferece crédito) |
| **Banco Central e governo** (cidadania financeira, Desenrola) | Menos inadimplência e mais letramento financeiro | Alinhamento com educação financeira, sem coleta de dados |
| **Emissores de cartão** (por exemplo, o Nubank) | Clientes que pagam a fatura em dia | Uso do CSV que o próprio banco oferece, sem acesso à conta |
| **FIAP e banca avaliadora** | Um trabalho com ML aplicado e impacto social | Modelos treinados e avaliados com rigor, limitações declaradas |
| **Desenvolvedores e mantenedores** | Base para evoluir (outros bancos, celular) | Código aberto à revisão, testes e documentação |

## 5. Objetivos de Desenvolvimento Sustentável (ODS)

| ODS | Meta | Como o projeto contribui |
|---|---|---|
| **ODS 1, Erradicação da pobreza** | 1.4: garantir a homens e mulheres, particularmente aos pobres e vulneráveis, direitos iguais a recursos econômicos e acesso a serviços básicos, inclusive serviços financeiros | Ajuda a evitar a dívida cara (rotativo a 451,7% ao ano), que empurra famílias para a inadimplência |
| **ODS 8, Trabalho decente e crescimento econômico** | 8.10: fortalecer as instituições financeiras para ampliar o acesso a serviços bancários, de seguros e financeiros para todos | Torna o uso do cartão, o serviço financeiro mais comum, mais consciente e menos arriscado |
| **ODS 10, Redução das desigualdades** | 10.2: empoderar e promover a inclusão social, econômica e política de todos, independentemente de idade, gênero, raça, condição econômica ou outra | Ferramenta gratuita, em português simples e acessível pelo teclado, que não exige conhecimento técnico nem dados pessoais |

## 6. Impacto esperado

**Cadeia de impacto.** Mais clareza sobre os gastos leva a decisões no meio do mês, e não depois da fatura. Isso significa menos rotativo e menos atraso, e portanto menos juros, multas e negativação.

**Indicadores propostos para um piloto.** Ainda não foram medidos com pessoas reais.

| Indicador | Como medir |
|---|---|
| A pessoa sabe dizer suas 3 maiores categorias de gasto | Pergunta antes e depois de 1 mês de uso |
| Alertas de orçamento recebidos antes do fechamento | Contagem no próprio app (local) |
| Faturas pagas no rotativo ou com atraso | Comparar 3 faturas antes e 3 depois do uso |
| Juros, multa e IOF por atraso pagos | Linha "Juros, multas e IOF" do app, antes e depois |
| Erro da previsão com faturas reais | Comparar a previsão com o valor final, com consentimento dos participantes |

**Escala possível.** A ferramenta é gratuita e roda no computador da pessoa, sem servidor. O custo de levar a mais gente é baixo. Os próximos passos seriam aceitar faturas de outros bancos e fazer uma versão para o celular.

## 7. Limitações (resumo)

- **Dados de teste fictícios:** os modelos foram avaliados com pessoas fictícias. Com pessoas reais, o erro pode ser maior.
- **Previsão e conta simples:** a previsão por aprendizado de máquina não foi melhor que uma conta simples com o histórico da pessoa. A vantagem sobre a estimativa pelo ritmo vem de usar esse histórico.
- **Confiança das sugestões:** a confiança das sugestões de categoria não é exata e tende a ser otimista.
- **Só o Nubank, no computador:** por enquanto, o app só lê faturas do Nubank e roda no computador.
- **Lista completa:** em [LIMITACOES.md](LIMITACOES.md).

## Fontes

1. CNC, Pesquisa de Endividamento e Inadimplência do Consumidor (Peic), julho de 2026. Agência Brasil, "CNC: endividamento das famílias sobe para 82%, mas inadimplência cai", 06/08/2026. https://agenciabrasil.ebc.com.br/economia/noticia/2026-08/cnc-endividamento-das-familias-sobe-para-82-mas-inadimplencia-cai
2. Serasa Experian, Indicador de Inadimplência do Consumidor, setembro de 2026. https://www.serasaexperian.com.br/conteudos/indicadores-economicos/
3. Banco Central do Brasil, estatísticas de crédito de setembro de 2026, divulgadas em 29/10/2026. WSCOM, "Juro do rotativo do cartão de crédito sobe para 451,7% ao ano em setembro, aponta Banco Central", 30/10/2026. https://wscom.com.br/economia/2026/10/30/juro-do-rotativo-do-cartao-de-credito-sobe-para-4517-ao-ano-em-setembro-aponta-banco-central/
4. Lei nº 14.690, de 3 de outubro de 2023, art. 28, § 1º. https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/lei/l14690.htm
5. CNDL/SPC Brasil e Offerwise, pesquisa sobre o uso do cartão de crédito, coleta de 2 a 9 de janeiro de 2026, publicada em 23/04/2026. https://cndl.org.br/varejosa/58-dos-consumidores-nao-controlam-gastos-com-cartao-de-credito-aponta-cndl-spc-brasil/
6. Banco Central do Brasil e FGC, pesquisa de letramento e inclusão financeira de adultos (metodologia OCDE/INFE), março e abril de 2023. Agência Gov, 21/11/2023. https://agenciagov.ebc.com.br/noticias/202311/inclusao-financeira-do-brasileiro-avanca-mas-letramento-financeiro-ainda-pode-melhorar
7. Nações Unidas no Brasil, Objetivos de Desenvolvimento Sustentável 1, 8 e 10. https://brasil.un.org/pt-br/sdgs
