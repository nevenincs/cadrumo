---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-plan]]"
---

# Populate active_profile at emit for profile-bound commands from the active-profile resolution, leaving the redacted bucket/profile UUIDs untouched

## Scope

- `src/aeat/entrypoints/cli/_config/_active_profile.py`

## Description

## Outcome

Landed in commit 154ddf3974 — active_profile label on the SchemaEnvelope + ErrorEnvelope spine, resolved at the CLI and injected into the core emitters (layering-clean); LABEL not UUID; optional/null-default.

## Notes
