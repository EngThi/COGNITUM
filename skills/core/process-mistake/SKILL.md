---
name: process-mistake
description: Logs mistakes and lessons learned, preventing repeating historical errors.
version: 1.0.0
platforms: [linux]
required_environment_variables: []
worker: note_worker
event_types:
  - note.mistake
---

# Process Mistake Skill

## Purpose
Log errors and capture core lessons learned into a dedicated vault directory.

## When to use
Triggered when user logs mistakes using command '/erro' or unstructured inputs classified as mistakes.

## Procedure
1. Create mistake log entry.
2. Format lessons learned and actions to prevent recurrence.
3. Persist file into '02-lessons/' path in vault.
