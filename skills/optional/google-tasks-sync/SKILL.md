---
name: google-tasks-sync
description: Syncs local task events with Google Tasks API.
version: 1.0.0
platforms: [linux]
required_environment_variables: [GOOGLE_TASKS_CLIENT_SECRET]
worker: task_sync_worker
event_types:
  - task.created
  - task.completed
---

# Google Tasks Sync Skill

## Purpose
Sync local to-do items with a Google Tasks account.

## When to use
Triggered when tasks are created or status changes in local system.

## Procedure
1. Detect task modifications.
2. Authenticate and update state on Google Tasks API.
