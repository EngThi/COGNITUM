# Architectural Decisions & Tradeoffs

This document details the major design decisions, library selections, and constraints adopted during the COGNITUM upgrade.

---

## 1. Minimal Dependency Set (Bloat Removal)

* **Decision:** We purged 70+ transitive and unused packages (including `pillow`, `bcrypt`, `paramiko`, `openai`, `sentry-sdk`, `composio-client`) from `requirements.txt`.
* **Rationale:** 
  * The original locked file was captured from a bloated environment and failed to compile on modern runtime versions (e.g. Python 3.14 on Pyenv) because of local C-extension building requirements for `Pillow` (missing `libjpeg-dev`).
  * Removing these packages minimizes CPU/memory usage for low-resource VPS nodes, prevents compilation failures, speeds up clean installations, and hardens the safety boundary.
* **Tradeoff:** Integrations (like Composio) now import packages dynamically inside their execute functions. Users must manually install optional clients if they activate those specific tool integrations.

---

## 2. Configurable Paths vs. Hardcoded `/opt/automation`

* **Decision:** Replaced all hardcoded paths with Pydantic settings that dynamically default to repository folders (`./data`, `./vault`, `./memory`, `./profiles`, `./policies`) but can be overridden at runtime via `.env` or system variables.
* **Rationale:**
  * Allows developers to run tests, write scripts, and develop features entirely inside their workspace without needing system-level `sudo` privileges or files in `/opt/`.
  * Integrates perfectly with standard CI pipelines and local test runners.
* **Tradeoff:** Existing systemd service files calling the daemon loop must specify environment variables (e.g., `DATABASE_PATH="/opt/automation/runtime/state/automation.db"`) to retain active production states.

---

## 3. Lightweight Memory & Vault Search

* **Decision:** Rejected complex dual-memory systems (like Mem0 or specialized vector DBs) in favor of SQLite event transaction records combined with markdown files searched via substring match (Phase A).
* **Rationale:**
  * Keeps resource overhead low.
  * Markdown notes remain fully human-readable and compatible with Obsidian.
  * Substring matching is highly performant for hundreds of notes.
* **Tradeoff:** Lacks semantic similarity queries (like cosine similarity search). We isolated this behind the `cognitum/core/memory_store.py` abstraction, enabling easy drops of a vector database (`sqlite-vec` or other) in the future without modifying API boundaries.

---

## 4. Standardizing on `gemini-2.5-flash`

* **Decision:** Standardized all LLM operations on a single model configuration `gemini-2.5-flash` using the new `google-genai` SDK.
* **Rationale:**
  * Prevents logic drift and inconsistent output formats when switching models.
  * Standardizes structured schema responses via Pydantic validator inputs.
  * `gemini-2.5-flash` has low latency, high context windows, and robust schema obedience.
* **Tradeoff:** Removes usage of local LLMs or smaller models, but increases predictability and safety for system command generation.

---

## 5. Standard unittest Library Choice

* **Decision:** Ported the test suite to use Python's built-in `unittest` module instead of `pytest`.
* **Rationale:**
  * Runs natively on any host without requiring pip installs first.
  * Simplifies local testing.
* **Tradeoff:** Lacks some of pytest's syntax extensions, but keeps core integration checks fast and dependency-free.
