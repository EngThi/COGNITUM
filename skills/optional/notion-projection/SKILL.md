---
name: notion-projection
description: Syncs Markdown vault artifacts and concepts into Notion databases.
version: 1.0.0
platforms: [linux]
required_environment_variables: [NOTION_API_KEY, NOTION_DATABASE_ID]
worker: projection_worker
event_types:
  - note.concept
  - note.idea
---

# Notion Projection Skill

## Purpose
Mirror structured local Markdown files into a central Notion workspace database.

## When to use
Triggered when notes are written to the vault and Notion integration is enabled.

## Procedure
1. Parse Obsidian note content and frontmatter.
2. Call Notion API to search or create page.
3. Keep page content synchronized with Markdown contents.
