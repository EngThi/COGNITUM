---
name: calendar-sync
description: Synchronizes session schedules and reminders with Google Calendar.
version: 1.0.0
platforms: [linux]
required_environment_variables: [GOOGLE_CALENDAR_CREDENTIALS]
worker: calendar_worker
event_types:
  - schedule.event
---

# Calendar Sync Skill

## Purpose
Add events, review blocks or sessions into Google Calendar.
