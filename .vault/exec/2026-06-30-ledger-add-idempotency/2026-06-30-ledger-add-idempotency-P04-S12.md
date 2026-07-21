---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-08'
step_id: 'S12'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Update the agent-harness ledger persona or skill instruction to mandate passing a stable idempotency key on every ledger add, citing only the live CLI surface

## Scope

- `src/aeat/_data/agent/`

## Description

- Add a ledger-groomer persona instruction mandating a stable `--idempotency-key` on every `aeat app ledger add`, so an uncertain retry is a safe no-op rather than a duplicate row, and to omit the key only for a deliberate genuinely-identical movement.
- Add `add` to the persona's ledger tool scope.

## Outcome

Landed in commit `497ccbb81`. Cites only the live CLI surface; the rule-surface conformance gate (`test_rule_surface_conformance.py`) passes.

## Notes
