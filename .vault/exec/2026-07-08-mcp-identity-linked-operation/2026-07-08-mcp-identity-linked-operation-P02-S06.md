---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:dbadb5128d815f4b492a19c57140d85adcf2a5be33c088702870723d6283574b'
step_id: 'S06'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-plan]]"
---

# Add whoami tests: it is always advertised, returns the active label, and is never persona-scoped away

## Scope

- `src/aeat/entrypoints/mcp/tests/test_harness_delivery.py`

## Description

## Outcome

Landed in commit 30be9ceeda — whoami identity-safety core tool over assess_active_profile_health; always advertised, never persona-scoped; label not UUID.

## Notes
