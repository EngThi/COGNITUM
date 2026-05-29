# COGNITUM — Cognition Layer for the HOMES Ecosystem

COGNITUM is a modular, production-ready "Cognition Layer" designed for the HOMES ecosystem. It serves as the central hub for agent planning, safety policies, user profiles, transactional event queues, and long-term memory.

---

## 🚀 Core Features

* **FastAPI API Layer:** Clean, schema-validated endpoints aligning with the HOMES engine model.
* **YAML Safety Policies:** Deterministic gate checks evaluating action safety, banned terms, path containment, and quiet hours before execution.
* **YAML User Profiles:** Dynamic configurations for timezone, active objectives, and prompt formatting instructions.
* **Structured Planning Endpoint:** Centralized planning utilizing Gemini 2.5 Flash (`google-genai` SDK) to build safety-validated step-by-step action sequences.
* **Lightweight Memory Store:** A unified search and storage manager querying SQLite event queues and Obsidian Vault markdown files.
* **Daemon Workers & bot:** Continuous background processing loop (for briefs, active recalls, OCR, audio voice notes) and Telegram bot interface.

---

## 📂 Repository Structure

```
cognitum/
├── main.py               # FastAPI App entrypoint
├── config.py             # Pydantic Settings configuration manager
│
├── api/                  # FastAPI routers
│   ├── context.py        # Context assembly (profile + policies + health + memories)
│   ├── memory.py         # Memory ingestion and unified search
│   ├── plan.py           # Structured policy-approved planner
│   ├── policy.py         # Safety policy gate check
│   └── profile.py        # User profile configuration
│
├── core/                 # Core engine implementations
│   ├── planner.py        # Gemini client wrapper and structured output schemas
│   ├── policy_gate.py    # Policy verification logic
│   ├── profile_store.py  # User profile manager
│   ├── memory_store.py   # Database/Vault search and storage
│   ├── state.py          # SQLite connection and session persistence helpers
│   ├── log.py            # Stream logging formatters
│   ├── router.py         # AI input router (classifies raw incoming data)
│   ├── workers.py        # Daemon execution loop (notes, briefs, flashcards)
│   └── bot.py            # Telegram chatbot interface
│
└── gateways/             # Payload normalization gateways
    ├── gemini_gateway.py
    ├── telegram_gateway.py
    └── ...
```

---

## ⚙️ Configuration & Setup

### 1. Requirements

* Python 3.10+ (tested on Python 3.14)
* SQLite3

### 2. Environment Setup

Copy `.env.example` to `.env` and fill in your variables:

```bash
cp .env.example .env
```

Key environment variables:
* `GEMINI_API_KEY`: Required for planner, brief summaries, and flashcards.
* `GEMINI_MODEL`: Standardized default (`gemini-2.5-flash`).
* `TELEGRAM_BOT_TOKEN`: Token for bot interface daemon.

### 3. Local Installation

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 🏃 Running COGNITUM

### 1. API Server

Run the FastAPI application with Uvicorn:

```bash
uvicorn cognitum.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Background workers

Start the event loop processor:

```bash
python -m cognitum.core.workers
```

### 3. Telegram bot Daemon

Start the bot polling daemon:

```bash
python -m cognitum.core.bot
```

---

## 🧪 Running Tests

A complete suite of unittest files is included under `tests/`. Run them natively:

```bash
python3 -m unittest discover tests/
```
