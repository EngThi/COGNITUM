---
name: hermes-sidecar
description: Sidecar agent architecture mapping for Hermes AI runner.
version: 1.0.0
platforms: [linux]
required_environment_variables: []
worker: sidecar_worker
event_types:
  - action.sidecar_hermes
---

# Hermes Sidecar Skill

## Purpose
Run Hermes Agent in a restricted sidecar environment to assist with specific operations.
