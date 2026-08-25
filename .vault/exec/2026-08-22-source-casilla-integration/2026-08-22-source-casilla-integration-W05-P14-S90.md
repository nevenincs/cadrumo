---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:93aef75686e9aaef6e07cbda9f81011860f0e036425cb4bf0af35fdcb5c0d2c1'
step_id: 'S90'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# reject unknown fields, row ownership collisions, sparse invalid rows, and caller substitution

## Scope

- `src/cadrumo/application/storage/calc_sheets/_row_set_assembly.py`

## Description

- Project the authoritative snapshot row-set columns and reject undeclared groupings, unknown fields, and bindings substituted from another grouping before assembly.
- Reserve submitted grouping-and-row coordinates across every input block before delegating typed assembly, refusing a second owner instead of overwriting a partial row.
- Delegate valid row-set blocks only to the established snapshot-bound S87 assembler and retain its localized sparse-row validation contract.
- Exercise the gateway with live registry snapshots and public worksheet edit records; do not replace transport or assembly boundaries with mocks.

## Outcome

- Added a thin fail-closed worksheet ingress boundary with no resolver, store, provenance, or source-identity carrier.
- Confirmed the focused gateway suite: `5 passed in 37.17s`.
- Confirmed the adjacent row-set projection and canonical assembler suite: `38 passed in 59.17s`.
- Passed scoped lint: `uv run --no-sync ruff check` over the changed application and test files.
- Passed scoped type analysis: `uv run --no-sync ty check` over the new gateway and its test module.

## Notes

- Deferred source-specific resolution, durable identity, encrypted persistence, and the S91 round-trip as out of scope for this refusal step.
