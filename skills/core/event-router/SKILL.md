---
name: event-router
description: AI-driven classification and distribution of unstructured events into structured system paths.
version: 1.0.0
platforms: [linux]
required_environment_variables: [GEMINI_API_KEY]
worker: ai_router
event_types:
  - raw.input
  - telegram.message
---

# Event Router Skill

## Purpose
Analyze incoming unstructured inputs using Gemini and classify them into specific schemas.

## When to use
Triggered when raw inputs or Telegram messages are received and need classification.

## Procedure
1. Pick unprocessed raw events.
2. Query Gemini model using structured prompt definitions.
3. Save classified output into a new structured event (e.g. 'note.idea', 'note.mistake').
