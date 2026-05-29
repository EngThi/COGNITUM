---
name: perplexity-research-ingest
description: Ingests structured research data using Perplexity API.
version: 1.0.0
platforms: [linux]
required_environment_variables: [PERPLEXITY_API_KEY]
worker: research_worker
event_types:
  - action.research
---

# Perplexity Research Ingest Skill

## Purpose
Query Perplexity API for technical topics and save outputs into local vault.
