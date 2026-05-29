---
name: generate-flashcards
description: Automatically extracts questions and active-recall cards from ingested concepts.
version: 1.0.0
platforms: [linux]
required_environment_variables: [GEMINI_API_KEY]
worker: flashcard_worker
event_types:
  - note.concept
---

# Generate Flashcards Skill

## Purpose
Automatically generate questions and active-recall cards from ingested concepts.

## When to use
Triggered when new concepts are added to the vault and need reinforcement.

## Procedure
1. Parse concept file.
2. Query Gemini to generate active recall questions.
3. Save generated card states to 'flashcards_state' table.
