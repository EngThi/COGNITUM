# 🧠 COGNITUM — PERSONAL COGNITIVE OPERATING SYSTEM
## System Architecture, Design Blueprint & Implementation Details

COGNITUM is a personal, hybrid, event-driven cognitive operating system designed to capture, process, persist, and reinforce knowledge. It acts as an ambient intelligent substrate that runs quietly in the background, minimizing cognitive load for the user while ensuring durable long-term memory and local data sovereignty.

---

## 1. O que é o COGNITUM hoje

O **COGNITUM** não é apenas um chatbot, uma API isolada, ou um conjunto de fluxos temporários de automação. Ele é um **runtime cognitivo pessoal híbrido**, construído sobre uma infraestrutura orientada a eventos (*event-sourced*). 

Seu objetivo é servir como uma extensão do sistema nervoso do usuário, garantindo a captura livre de fricção em qualquer dispositivo (mobile-first) e a consolidação de conhecimento de forma estruturada e durável em um servidor pessoal local.

### 🖥️ VM Environment & Tech Stack Atual
O sistema está implantado e ativo em uma VPS sob as seguintes especificações técnicas:
* **Host/OS:** Ubuntu 25.10 (2vCPU / 2GB RAM)
* **Runtime:** Python 3.13 com ambiente virtual isolado (`/opt/automation/.venv`)
* **API Edge:** FastAPI com loop de eventos assíncrono gerenciado por `uvloop` e serialização ultra-rápida via `orjson`.
* **Banco de Dados:** SQLite append-only (`/opt/automation/runtime/state/automation.db`).
* **Soberania de Memória:** Vault local estruturado em arquivos Markdown (`/opt/automation/vault/`).
* **Processamento:** Workers assíncronos modularizados rodando sob controle do **systemd** com quotas e limites de recursos restritos (`MemoryMax=500M` e `CPUQuota=50%`).
* **Consumo de Recursos:** Extremamente otimizado, rodando de forma estável com **apenas ~60 MB de RAM**.

---

## 2. A Ideia Central: Event-Sourcing Cognitivo

A fundação da arquitetura baseia-se em um princípio fundamental:

> **Tudo vira um evento (`CognitiveEvent`).**

Diferente de arquiteturas de automação tradicionais (focadas em workflows síncronos), o COGNITUM rastreia e ingere cada interação, nota, erro ou tarefa como uma entrada de registro cronológico imutável.

### 📊 Modelagem das Entradas Comuns
* **`raw.input`**: Capturas gerais não estruturadas de texto.
* **`telegram.message`**: Texto bruto, comandos, ou caminhos de mídias enviadas via celular.
* **`note.idea`**: Pensamentos, insights, e ideias de projetos.
* **`note.mistake`**: Registro de bugs, erros acadêmicos ou falhas em exercícios (para geração de mapas de erro).
* **`note.concept`**: Definições, termos técnicos de engenharia e tópicos acadêmicos.
* **`note.session`**: Resumo ou log de sessões ativas de trabalho ou estudo.
* **`action.daily_brief`**: Gatilho para gerar relatórios e briefs diários.
* **`action.start_review`**: Gatilho para iniciar sessões de revisão espaçada (Active Recall).

#### Estrutura do Evento no SQLite:
```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    payload TEXT NOT NULL, -- JSON com conteúdo e metadados
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### Rastreabilidade de Workers:
```sql
CREATE TABLE processed_events (
    event_id INTEGER NOT NULL,
    worker_name TEXT NOT NULL,
    status TEXT NOT NULL, -- 'pending', 'processed', 'failed'
    error TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, worker_name)
);
```

Esta abordagem append-only garante a **reproducibilidade total**: a qualquer momento, o histórico cognitivo pode ser reprocessado por prompts melhores, novos modelos de linguagem ou novas regras de classificação, sem perda do dado bruto original.

---

## 3. Fluxo de Dados End-to-End

```
Captura (Telegram/Voz/OCR/API/Edge)
               ↓
        FastAPI /ingest
               ↓
   SQLite Append-Only Event Store
               ↓
           AI Router (Gemini-2.5-Flash + Backoff)
               ↓
   Classified Events (note.idea, note.concept, etc.)
               ↓
    Workers (note_worker, flashcard_worker, scheduler)
               ↓
  Vault (Markdown) ───[Projeção]───► Notion Dashboard / Google Tasks
```

---

## 4. O Papel das Camadas Híbridas

O COGNITUM é híbrido por design, equilibrando a ubiquidade da nuvem com a privacidade do servidor local.

### 4.1 Cloud Edge Layer (Convenicência & Mobile)
Projetada para estar sempre disponível, capturando pensamentos no celular sem criar fricção organizacional.
* **Gemini (Raciocínio & Ação):** Responsável por classificar dados, gerar revisões contextualizadas, e agir sobre APIs do Google Workspace.
* **Perplexity (Radar de Pesquisa):** Ferramenta de inteligência externa para buscar notícias, artigos acadêmicos e documentações técnicas.
* **Pipedream (Event Bridge):** Transforma webhooks e e-mails na nuvem em requisições HTTP para o core local de forma *stateless*.
* **Composio (Integrações):** Simplifica autenticações OAuth com GitHub, Google, e Notion.
* **Google Tasks & Calendar:** Camada temporal visual de agendamentos e alertas móveis.

### 4.2 Local Core Runtime ( VPS / Soberania )
A fonte primária da verdade, responsável por guardar a inteligência gerada de forma durável e controlável.
* Escreve e mantém a estrutura física de arquivos em disco.
* Executa algoritmos de agendamento de estudo localmente (FSRS-lite).
* Trata serviços cloud como meros adaptadores que podem quebrar ou expirar sem comprometer a memória durável.

---

## 5. Estrutura e Recursos Ativos na VPS

### 5.1 O Markdown Vault (`/opt/automation/vault/`)
Organizado de forma limpa para garantir compatibilidade com Obsidian e versionamento local:
```
/vault/
├── 00-inbox/           # Ideias brutas e capturas rápidas
├── 01-concepts/        # Conceitos acadêmicos e técnicos
├── 02-sessions/        # Registro de sessões de estudo/trabalho
├── 03-mistakes/        # Log de falhas e lições aprendidas (Mapas de erro)
├── 04-artifacts/
│   ├── flashcards/     # Arquivos markdown de flashcards gerados por IA
│   ├── quizzes/        # Questionários gerados
│   └── summaries/      # Sumários diários gerados
├── 05-research/        # Relatórios de pesquisa técnica externos
├── 06-reviews/         # Folhas de revisão ativa geradas pelo sistema
└── .meta/              # Metadados e configurações do sistema
```

### 5.2 O AI Router com Resiliência a Rate-Limit
Equipado com o modelo `gemini-2.5-flash` através da nova biblioteca `google-genai`. Para lidar com a cota restrita de requisições do Free Tier do Gemini, o roteador foi desenhado com um mecanismo robusto de **Exponential Backoff & Retries** automático:
```python
# Se bater em 429 RESOURCE_EXHAUSTED, o worker suspende sua fila temporariamente
# e realiza tentativas com intervalos crescentes (10s, 20s, 40s...)
```

### 5.3 Workers em Background (Executando)
* **`note_worker`:** Consome eventos de notas estruturadas e gera os arquivos `.md` no respectivo subdiretório do Vault, aplicando *frontmatter* e limpando a formatação.
* **`flashcard_worker`:** Analisa as notas recém-criadas, aciona o Gemini para extrair fatos de recall ativo e os insere na tabela `flashcards_state` do SQLite, gerando também a versão markdown para o Vault.
* **`daily_brief_worker`:** Consolida os relatórios diários de status.
* **`review_worker` (FSRS Agendador):** Gera dinamicamente folhas de estudo sob `/vault/06-reviews/` com as respostas ocultas em comentários HTML, e atualiza os prazos de revisão das cartas no banco.

---

## 6. Ferramentas de Interação Móvel e Observabilidade

### 6.1 Telegram Bot Terminal (@cog_ni_tumBOT)
O robô age como o terminal mobile principal do usuário.
* **Transcrição de Voz Automática:** O bot detecta mensagens de áudio, realiza o download no diretório `/opt/automation/tmp` temporariamente, faz o upload para a File API do Gemini e transcreve o conteúdo na base como um evento brutos.
* **OCR de Fotos:** Ao enviar imagens de cadernos, quadros ou apresentações, o Gemini extrai os tópicos e formata uma nota markdown completa.
* **Integração de Dashboard:** O comando `/status` executa o script local de observabilidade e renderiza o dashboard no próprio chat.

### 6.2 Painel de Observabilidade CLI (`/opt/automation/scripts/status_check.py`)
Utilitário executável na VPS para monitorar a saúde da infraestrutura do COGNITUM:
```
============================================================
🧠 COGNITUM RUNTIME SYSTEM OBSERVABILITY DASHBOARD
============================================================
🖥️  SYSTEM HEALTH:
   • CPU Usage:    1.2%
   • RAM Usage:    20.5%
   • Disk Usage:   8.68%
------------------------------------------------------------
📊 EVENT PIPELINE:
   • Total Events: 8
   • Pending:      0
   • Failed:       0 (Dead-letter Queue)
------------------------------------------------------------
📚 MEMORY VAULT:
   • Notes Written: 3
   • Flashcards Due: 0
============================================================
```

---

## 7. Como o COGNITUM se diferencia de Agentes Generalistas

Sistemas como **OpenClaw** e **Hermes Agent** são focados no *ciclo de vida do agente* (ferramentas que a IA pode rodar ativamente, manipulação de navegadores e assistentes sempre online). 

O **COGNITUM** posiciona-se em um nível diferente:

| Característica | OpenClaw / Hermes Agent | COGNITUM |
| :--- | :--- | :--- |
| **Abstração** | Agente generalista com ferramentas | Sistema Operacional Cognitivo Orientado a Eventos |
| **Foco de Memória** | Janela de contexto / Logs de chat | Vault local em Markdown e banco SQLite append-only |
| **Escopo Principal** | Ações de chatbot e automações gerais | Reforço acadêmico, mapas de erro, flashcards e FSRS |
| **Arquitetura** | Agent-first (executores rodando skills) | Event-first (ingestão -> roteamento -> workers) |

> **Analogia:** Se OpenClaw e Hermes são funcionários digitais capazes com acesso a ferramentas, o COGNITUM é o **sistema operacional e a empresa digital** onde esses e outros agentes trabalham e depositam a inteligência coletiva de forma estruturada.

---

## 8. Roadmap de Evolução

* [x] **Fase 1 (Ativada):** Ingestão FastAPI, SQLite append-only, Workers systemd, AI Router com backoff, Painel de observabilidade e Telegram bot com voz/OCR.
* [ ] **Fase 2 (Revisão & Calendário):** Conexão com Google Tasks e Calendar para exibição física de revisões devidas, e refino da projeção FSRS.
* [ ] **Fase 3 (Cloud Bridges):** Integração com Composio e Pipedream para capturar webhooks e logs de vagas/e-mails passivamente.
* [ ] **Fase 4 (Notion Projections):** Worker para espelhar as notas do Vault local diretamente para dashboards visuais do Notion.
* [ ] **Fase 5 (Busca Semântica):** Geração de embeddings leves locais para busca vetorial sobre o Vault sem sobrecarregar a memória RAM.
