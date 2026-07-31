---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:4a906f9a1e1b7b1e834b6f5217bd082c7f70d662bdcbe9f7ca64045c4b77ffee'
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
