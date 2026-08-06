---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-03'
modified: '2026-07-03'
body_hash: 'sha256:f6a82e6b09593a834ea1b15af7339eba3a8541faa3db5b5730db82c79be341ac'
step_id: 'S17'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Delete the parameterised compiled-schema equality harness now that migration is complete

## Scope

- `src/aeat/domain/calculations/registry/tests/test_inline_fragment_equality.py`

## Description

- Delete the spent parameterised compiled-schema equality harness + baselines.

## Outcome

Done in `7e14681d5f`: removed test_inline_fragment_equality.py + the 20 pre-migration baselines. The registry suite collects cleanly (3096 tests); the loader refusal makes a re-inline impossible, so the migration gate is no longer needed.

## Notes

Coordinator-run closeout of D6.
