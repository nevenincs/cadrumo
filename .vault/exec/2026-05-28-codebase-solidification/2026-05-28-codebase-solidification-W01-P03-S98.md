---
step_id: S98
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-07-17'
body_hash: 'sha256:20d28e5a834425510f27a3ce5717478d5c937a0cb86e190362f6a36a09bd4b8e'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P03.S98 — test missing_required_casilla localization

## Outcome

Two real-behavior tests added to `src/aeat/application/modelo/test_actions.py`
covering S97:

- `test_missing_required_casilla_finding_message_is_localised`: asserts message
  contains casilla_id and is not the raw locale key.
- `test_missing_required_casilla_finding_message_changes_with_casilla_id`: asserts
  two different casilla_ids produce distinct messages (anti-tautology).

Both landed in commit `e5e3c630e` by a parallel agent. 51 tests pass.

## Files touched

- `src/aeat/application/modelo/test_actions.py` (in HEAD)

## Verification

`uv run --no-sync pytest src/aeat/application/modelo/test_actions.py -q` — 20 passed.
`vault plan step check S98` applied.
