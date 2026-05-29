---
name: cognitum-mcp-server
description: Model Context Protocol (MCP) server implementation for external agents.
version: 1.0.0
platforms: [linux]
required_environment_variables: []
worker: mcp_worker
event_types:
  - action.mcp_call
---

# Cognitum MCP Server Skill

## Purpose
Expose local COGNITUM tools to external AI agents.
