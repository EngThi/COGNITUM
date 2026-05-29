---
name: vault-writing
description: Persistence of structured notes, ideas, concepts and mistakes into target Obsidian vault paths.
version: 1.0.0
platforms: [linux]
required_environment_variables: []
worker: note_worker
event_types:
  - note.idea
  - note.concept
  - note.mistake
---

# Vault Writing Skill

## Purpose
Format and persist structured event content as Markdown files in the Obsidian vault.

## When to use
Invoked by note worker to write classified notes into appropriate directories.

## Procedure
1. Create target file paths.
2. Format as Obsidian-compatible Markdown notes with YAML metadata.
3. Write file and verify disk persistence.
