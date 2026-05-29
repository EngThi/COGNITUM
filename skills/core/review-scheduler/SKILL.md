---
name: review-scheduler
description: Schedules active recall review sessions for flashcards using spacing algorithms (FSRS).
version: 1.0.0
platforms: [linux]
required_environment_variables: []
worker: review_worker
event_types:
  - action.start_review
---

# Review Scheduler Skill

## Purpose
Evaluate and construct daily spaced-repetition sessions from flashcards due for review.

## When to use
Invoked via Telegram command '/review' or automated timers.

## Procedure
1. Retrieve card state from 'flashcards_state' DB.
2. Filter cards with next review timestamp in the past.
3. Generate review session Markdown containing hidden recall questions.
