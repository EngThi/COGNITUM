# Flashcards: Erro de execução automática de tools
Origin Note Event ID: 60

### Q1: Por que a IA executou comandos de tools sem que o usuário tivesse explicitamente pedido?
**A**: A IA pode executar tools automaticamente quando interpreta a solicitação do usuário como uma intenção de ação, mesmo que o usuário tenha usado termos como 'olhar' ou 'ver'. Isso ocorre porque o modelo interpreta o contexto e a intenção por trás da mensagem, não apenas as palavras literais.

### Q2: O que diferencia uma solicitação de 'olhar' uma tool de uma solicitação para 'executar' uma tool?
**A**: 'Olhar' uma tool geralmente significa apenas descrever sua funcionalidade, parâmetros e propósito sem invocá-la. 'Executar' uma tool significa realmente chamá-la com parâmetros e obter um resultado. A IA deve confirmar antes de executar quando há ambiguidade.

### Q3: Quais problemas podem ocorrer quando uma IA executa tools sem confirmação explícita?
**A**: 1. Execução de ações indesejadas ou irreversíveis; 2. Uso de créditos ou recursos sem consentimento; 3. Exposição de dados sensíveis; 4. Resultados inesperados que afetam sistemas externos; 5. Quebra de confiança do usuário na IA.

### Q4: Qual é a melhor prática para um usuário quando quer apenas informações sobre uma tool sem executá-la?
**A**: Ser explicitamente claro na solicitação, usando frases como: 'Descreva o que a tool X faz', 'Liste as ferramentas disponíveis sem executar nenhuma', ou 'Explique os parâmetros da tool Y'. Isso reduz a ambiguidade para a IA.

### Q5: O que um sistema de IA deve fazer quando há ambiguidade sobre executar ou não uma tool?
**A**: O sistema deve pedir confirmação ao usuário antes de executar, especialmente para ações que consomem recursos, modificam estado ou acessam dados externos. A confirmação pode ser implícita (clara intenção de ação) ou explícita (pergunta direta ao usuário).

### Q6: Por que é importante a IA justificar suas ações quando executa tools automaticamente?
**A**: A justificativa aumenta a transparência, permite ao usuário entender a lógica da IA, identifica se houve mal-entendido na interpretação da intenção, e ajuda a construir confiança no sistema ao demonstrar raciocínio explícito.
