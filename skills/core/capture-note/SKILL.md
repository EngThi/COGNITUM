---
name: capture-note
description: Capture a note from Telegram, API, Gemini, Pipedream or manual input and convert it into a CognitiveEvent.
version: 1.0.0
platforms: [linux]
required_environment_variables: []
worker: note_worker
event_types:
  - note.raw
  - telegram.message
  - raw.input
---

# Capture Note Skill

## Purpose
Convert user input into a durable CognitiveEvent and persist it into the SQLite event store.

## When to use
Use this skill when the input is a study note, a raw idea, a quick Telegram capture, or any external input that needs parsing.

## Procedure
1. Receive input payload.
2. Store inside events database under type 'raw.input' or 'telegram.message'.
3. Assign an event ID.
