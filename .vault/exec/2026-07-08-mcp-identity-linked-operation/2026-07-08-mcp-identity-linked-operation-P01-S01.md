---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-09'
step_id: 'S01'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-plan]]"
---

# Add the optional active_profile label field to the shared SchemaEnvelope spine and the stderr ErrorEnvelope sibling, defaulting null before a profile exists

## Scope

- `src/aeat/core/json_contract.py`

## Description

## Outcome

Landed in commit 154ddf3974 — active_profile label on the SchemaEnvelope + ErrorEnvelope spine, resolved at the CLI and injected into the core emitters (layering-clean); LABEL not UUID; optional/null-default.

## Notes
