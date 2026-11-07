# Privacidade, LGPD e uso responsável dos dados

**Escopo deste documento.** Ele descreve como o "Raio-X da fatura" trata dados pessoais. É uma descrição técnica e não uma avaliação jurídica. O projeto **não afirma** estar em conformidade integral com a LGPD (Lei 13.709/2018), porque nenhuma auditoria jurídica foi feita.

## 1. Onde o processamento acontece

- **Processamento local:** o app roda no computador da pessoa (Streamlit em `localhost`).
  - **Recusa de rede:** ele se recusa a abrir a fatura se for iniciado para atender a rede ou com a coleta de estatísticas do Streamlit ligada.
  - **Sem servidor:** não há servidor do projeto, conta de usuário nem envio de dados para o desenvolvedor.
- **O que isso não garante:** o processamento local **não** garante que nenhum dado saia do computador. Os arquivos ficam sujeitos à configuração do próprio computador:
  - **CSV da fatura:** se a pessoa baixá-lo numa pasta sincronizada (OneDrive, Google Drive, Dropbox), ele vai para a nuvem dela;
  - **pasta do app:** o arquivo das categorias escolhidas fica dentro dela. Se ela estiver sincronizada, esse arquivo também vai.
  - **Backups e acesso ao computador:** cópias de segurança e quem tem acesso ao usuário do computador alcançam os mesmos arquivos.

## 2. Dados pessoais tratados e finalidade

| Dado | Onde fica | Finalidade |
|---|---|---|
| CSV da fatura (data, descrição do estabelecimento e valor de cada lançamento) | Onde a pessoa salvou o arquivo; o app lê na memória | Mostrar os gastos, as categorias e a previsão da fatura aberta |
| Histórico de faturas (o texto do CSV, o vencimento e o fechamento) | `%LOCALAPPDATA%\fatura_cartao\historico\`, uma pasta por base | Comparar meses, achar cobranças fixas e alimentar a previsão com as faturas anteriores |
| Categorias escolhidas por estabelecimento | `regras_usuario.json`, na pasta do app | Aplicar as escolhas da pessoa nas próximas faturas |
| Rótulos conferidos e a origem de cada um | `%LOCALAPPDATA%\fatura_cartao\rotulos.json` e `rotulos_origem.json` | Treinar, no próprio computador, o modelo que sugere categorias |
| Sugestões rejeitadas | `%LOCALAPPDATA%\fatura_cartao\sugestoes_rejeitadas.json` | Não sugerir de novo o que a pessoa recusou |
| Metas e orçamentos | `%LOCALAPPDATA%\fatura_cartao\metas_usuario.json` | Alertar quando o gasto ou a previsão passa do limite |
| Modelo de previsão treinado | `%LOCALAPPDATA%\fatura_cartao\modelo_previsao\` | Evitar treinar de novo a cada abertura. Contém só o que foi aprendido com pessoas fictícias, nenhum dado da pessoa |

**O que o app não pede:**
- CPF, renda e endereço;
- senha de banco, nem acesso à conta;
- nenhum dado além do CSV que a própria pessoa exporta.

## 3. Armazenamento e controle de acesso

- **Pasta local:** os arquivos ficam no computador, na pasta local do usuário do Windows (`%LOCALAPPDATA%`), que o OneDrive não sincroniza por padrão. A exceção é `regras_usuario.json`, que fica na pasta do app.
- **Controle de acesso:** é o da conta do sistema operacional. O app não tem senha própria e **não criptografa** os arquivos. Quem tem acesso ao usuário do computador tem acesso aos dados.
- **Bases separadas:** "Minhas faturas" e "Faturas simuladas" ficam em pastas diferentes. O app recusa guardar numa base uma fatura que já está na outra.
- **Pasta de demonstração:** o `abrir_demonstracao.bat` usa uma pasta só para a demonstração, inclusive para "Minhas faturas".

## 4. Correção e exclusão

- **Categorias:** a pessoa corrige qualquer categoria na aba Classificar ("Classificar à mão" e "Corrigir a categoria de um estabelecimento").
  - **Rótulos:** podem ser trocados ou retirados na conferência.
  - **Sugestões:** nenhuma sugestão do modelo vira categoria sem a pessoa aceitar.
- **Faturas:** a pessoa remove qualquer fatura em **Mês a mês → Faturas guardadas**.
- **Metas:** a pessoa remove qualquer meta em **Até o fechamento**.
- **Exclusão total:** apagar a pasta `%LOCALAPPDATA%\fatura_cartao\` e o arquivo `regras_usuario.json` da pasta do app. Não há cópia em outro lugar.

## 5. Riscos e mitigações

| Risco | Mitigação adotada | O que ainda não é coberto |
|---|---|---|
| A fatura ou as categorias irem para a nuvem pela sincronização da pasta | Os dados do app ficam fora do OneDrive; o README e este documento avisam | O app não controla onde a pessoa salva o CSV nem a pasta do app |
| Outra pessoa com acesso ao computador ver os dados | Nenhum dado fica fora da conta do usuário | Sem senha própria nem criptografia |
| O app ficar acessível pela rede | Só atende `localhost` e se recusa a abrir se for configurado de outro jeito | |
| Dados reais irem para o repositório público do código | Todo CSV fica fora do git; os testes usam uma fatura fictícia; um teste confere que nenhum estabelecimento real aparece nos arquivos | |
| Dados reais aparecerem numa apresentação | A demonstração usa só faturas fictícias, numa pasta separada | |
| O arquivo do modelo (pickle) ser trocado por um malicioso | Fica na pasta local do usuário; arquivo inválido é descartado e o modelo é treinado de novo | Quem consegue gravar na pasta do usuário já consegue executar programas como ele |
| Uma sugestão errada mudar a categoria sem a pessoa perceber | Nada muda sem a pessoa aceitar | |

## 6. Dados sintéticos na demonstração e no desenvolvimento

- **Modelos e notebooks:** foram desenvolvidos e avaliados só com faturas **100% fictícias**, do gerador do projeto (`ferramentas/gerar_faturas_sinteticas.py`, com sementes fixas).
- **Demonstração:** as capturas de tela da apresentação vêm da demonstração com essas faturas.
- **Fatura real:** a única fatura real do autor fica fora do repositório. Ela só é usada no computador do autor, pelo teste de privacidade, que confere que nenhum estabelecimento dela aparece nos arquivos do repositório. Ela não entra em nenhum notebook, imagem ou documento publicado.

## 7. Limitações e vieses dos modelos

- **Classificação** (Regressão Logística):
  - aprende só com as categorias que a pessoa conferiu;
  - a confiança mostrada não é calibrada e tende a ser otimista (56% dita contra 45% de acerto nos testes);
  - no começo, com poucos exemplos, erra mais.
- **Previsão** (Random Forest), treinada com pessoas fictícias:
  - **salário em data fixa:** essas pessoas recebem salário em datas fixas, e quem tem **renda irregular** (autônomos, informais, trabalhadores de aplicativo) pode ter padrões que o modelo não viu;
  - **faixa de gasto:** gastos muito acima ou abaixo da faixa do treino ficam sem previsão do modelo, e o app avisa e mostra só a projeção pelo ritmo;
  - **perfil urbano:** os hábitos de consumo do gerador são urbanos.
- **Acesso:** hoje o app só lê faturas do Nubank e precisa de um computador. Isso deixa de fora quem usa outro banco ou só tem celular.

A lista completa de limitações está em [LIMITACOES.md](LIMITACOES.md).
