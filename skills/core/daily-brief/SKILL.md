---
name: daily-brief
description: Generates daily briefings summarizing logs, lessons learned, and system stats.
version: 1.0.0
platforms: [linux]
required_environment_variables: [GEMINI_API_KEY]
worker: daily_brief_worker
event_types:
  - action.daily_brief
---

# Daily Brief Skill

## Purpose
Synthesize operational, learning, and life data collected during the last 24 hours into a cohesive Markdown summary.

## When to use
Executed daily (e.g. by systemd timer or user command '/summary').

## Procedure
1. Scan for recent database entries.
2. Query system status and dead-letter statistics.
3. Summarize newly added Obsidian notes.
4. Output Markdown files into summaries directory.
