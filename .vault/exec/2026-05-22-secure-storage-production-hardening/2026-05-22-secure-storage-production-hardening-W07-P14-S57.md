---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S57'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Add a guard that flags ad hoc secure-storage test password and ephemeral default-repository patterns

## Scope

- `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`

## Description

- Traced the two ad-hoc password/default-repository controls to `177f0669a`.
- Confirmed their current storage-tests topology.
- Ran the focused secure-SQL and ephemeral-key hygiene suite.

## Outcome

The hygiene guard remains present and passed in the 8-test focused suite.

## Notes

The original flat test path has moved without changing the guard controls.
