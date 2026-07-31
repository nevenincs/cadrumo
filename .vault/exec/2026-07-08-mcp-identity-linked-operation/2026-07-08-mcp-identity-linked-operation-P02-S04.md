---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:cd0ac1dae95932c77821a4008db0198510ddc788a470e89b8057afd0b3f1cf1b'
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
