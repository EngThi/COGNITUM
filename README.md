# COGNITUM — Personal Cognitive Automation OS

COGNITUM is a modular, lightweight personal cognitive operating system inspired by Hermes Agent. It runs natively on a linux host and aggregates, classifies, and tracks personal data, events, concepts, and reviews.

## Architecture

- **Event-Driven:** Incoming inputs are normalized by Gateways, transformed into CognitiveEvents, and saved to an append-only SQLite store.
- **Async Workers:** Python workers process unprocessed events based on their types.
- **Skills System:** Standardized procedural skills in `/opt/automation/skills/` define system actions.
- **Obsidian Vault:** Durable markdown notes are preserved in `/opt/automation/vault/`.

## Key Paths

- **Runtime:** `/opt/automation`
- **Memory Pack:** `/opt/automation/memory/`
- **Skills System:** `/opt/automation/skills/`
- **Database:** `/opt/automation/runtime/state/automation.db`
- **Vault:** `/opt/automation/vault/`

## Services

- `automation-bot.service` (Telegram Interface)
- `automation-workers.service` (Event Processing Pipeline)
- `kimiproxy.service` (Browser Proxy for Kimi AI)

## Logs
To view logs:
- `journalctl -u automation-bot -f`
- `journalctl -u automation-workers -f`
- `journalctl -u kimiproxy -f`

## How-To Guides

### Add a Worker
Create a new worker script in `automations/` or `automations/jobs/` and register it inside `automation-workers.service`.

### Add a Gateway
Create a module under `automations/gateways/` to convert external payloads to standardized CognitiveEvents, then save using `save_event`.

### Add a Skill
Create a folder under `skills/core/` or `skills/optional/` with a `SKILL.md` file containing YAML frontmatter and procedural rules.

### Backup Database & Vault
Run a daily script to tar and compress `/opt/automation/runtime/state/` and `/opt/automation/vault/`.
