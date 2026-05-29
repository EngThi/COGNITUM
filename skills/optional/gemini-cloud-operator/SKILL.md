---
name: gemini-cloud-operator
description: Advanced Gemini reasoning and function calling cloud operator.
version: 1.0.0
platforms: [linux]
required_environment_variables: [GEMINI_API_KEY]
worker: cloud_worker
event_types:
  - action.gemini_cloud
---

# Gemini Cloud Operator Skill

## Purpose
Execute remote Gemini API functions and orchestrate cloud integrations.
