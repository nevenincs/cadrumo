---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:6ff3ccaec4ed670577cbeab1f4c073712ac189ca34de023f3abf907f2dfb31f5'
step_id: 'S274'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only draft row-source fingerprint projection because the live review surface projects the same safe shape from the canonical persisted revision; retain replay attachment and live review privacy tests, update cadence, and remeasure exact reachability.

## Scope

- `row-source identity replay helper and focused replay tests`

## Changes

- `M` `src/cadrumo/application/modelo/_row_source_identity_replay.py`
- `M` `src/cadrumo/application/modelo/tests/test_row_source_identity_replay.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` focused Ruff check -> `pass`
- `verify:` replay suite -> `6 passed`
- `verify:` live work-review fingerprint projection -> `1 passed, 13 deselected`
- `verify:` exact reachability -> `267 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

The deleted helper projected review data from a transient replayed draft and had only test callers. The live work-review path independently projects the same privacy-safe shape from the persisted `CalculationRevision`, which remains the sole owner. Meaningful replay assertions now test attachment, deterministic content identity, substitution refusal, and non-disclosure directly. Exact unused symbols improved from 268 to 267.
