---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-plan]]"
---

# Add the whoami console tool over assess_active_profile_health returning the active-profile label, tax_id_present, readiness, and next_action, with a description stating its identity-safety job

## Scope

- `src/aeat/entrypoints/mcp/_harness_tools.py`

## Description

## Outcome

Landed in commit 30be9ceeda — whoami identity-safety core tool over assess_active_profile_health; always advertised, never persona-scoped; label not UUID.

## Notes
