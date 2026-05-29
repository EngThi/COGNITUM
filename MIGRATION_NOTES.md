# COGNITUM Migration Notes

This document guides repo maintainers and engineers through the architectural updates introduced during the COGNITUM stabilization pass.

---

## 1. Summary of Changes

* **New Package Structure:** All core logic has been reorganized into the `cognitum` Python package under `cognitum/core/`, `cognitum/api/`, and `cognitum/gateways/`.
* **Centralized Configuration:** Paths (database, vault, profiles, memory) and API keys are managed dynamically via Pydantic Settings in `cognitum/config.py` loading from local `.env` variables.
* **FastAPI Lifespan Implementation:** Upgraded event lifecycle management in `cognitum/main.py` to use FastAPI's unified `lifespan` manager, replacing deprecated `@app.on_event("startup")` and `@app.on_event("shutdown")` decorators.
* **Standardized Model:** All LLM integrations standardized on `gemini-2.5-flash` using the new `google-genai` SDK.
* **safety policies & Profiles:** Implemented Pydantic-validated YAML configurations under `profiles/` and `policies/` folders, with deterministic evaluations in `core/policy_gate.py`.
* **Isolated Testing:** The API test suite under `tests/test_api.py` utilizes isolated directories and mocks Gemini planning, allowing tests to run locally with zero side effects.

---

## 2. Legacy Features Removed & Cleaned Up

* **Dependency Bloat Removal:** purges of C-compiling libraries (e.g. `pillow`, `paramiko`, `bcrypt`, `openai`) from `requirements.txt`.
* **Removed Hardcodings:** Purged all hardcoded references to `/opt/automation` in Python logic. They are now dynamic settings.
* **API responses:** Standardized responses across health, capture, and new endpoints.

---

## 3. Experimental Status

* **Vector Search / `sqlite-vec`:** Remains experimental. An abstraction interface has been established inside `cognitum/core/memory_store.py` so semantic embedding search can be added later without modifications to routing logic.
* **Composio / MCP:** The stdio MCP client and Composio execution wrappers remain experimental and have been moved under `cognitum/core/tools/`.

---

## 4. Manual Deployment Migration Steps

If migrating a running VPS daemon:

1. **Stop active services:**
   ```bash
   sudo systemctl stop automation-bot
   sudo systemctl stop automation-workers
   ```
2. **Pull the latest codebase and update configurations:**
   Copy `.env.example` to `/opt/automation/.env` (or project root `.env`) and verify variables:
   ```bash
   cp .env.example .env
   ```
3. **Upgrade dependencies inside your virtual environment:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Update systemd service execution targets:**
   Update unit execution lines inside `/etc/systemd/system/` services to point to the new package path:
   * Worker daemon: `python3 -m cognitum.core.workers`
   * Bot daemon: `python3 -m cognitum.core.bot`
   * Web server: `uvicorn cognitum.main:app --host 0.0.0.0 --port 8000`
5. **Reload services:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start uvicorn
   sudo systemctl start automation-bot
   sudo systemctl start automation-workers
   ```
