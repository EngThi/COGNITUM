---
name: semantic-search
description: Vector embeddings and semantic query system for the cognitive vault.
version: 1.0.0
platforms: [linux]
required_environment_variables: [GEMINI_API_KEY]
worker: search_worker
event_types:
  - action.search_semantic
---

# Semantic Search Skill

## Purpose
Search the Obsidian vault using semantic similarity models.
