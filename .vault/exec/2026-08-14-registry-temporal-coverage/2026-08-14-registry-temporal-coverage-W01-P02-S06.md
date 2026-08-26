---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:d94004607a2c493a9e0e5ff17d50cc0a63e7981ce768727a1171a707dd1da07d'
step_id: 'S06'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-14-registry-campaign-sequencing-audit]]'
---

# Add a structural gate refusing any modelo-named field on a generic registry schema type and any modelo branch in generic authority construction, proven by a planted field observed red then removed

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`
- `dev/`

## Description

The registry-owned structural test scans the production registry package AST and refuses enum-derived modelo-code field names on generic schema classes. It separately refuses `Modelo.M###` branches in the generic `authority.py` and `snapshot.py` construction surfaces. Per-modelo types and per-modelo modules are excluded deliberately, and `_supplementary_orden.py` is protected as the table-driven non-vacuity control.

The implementation landed across commits `58b836437a`, `829bb302bd`, and `02bdc6fc16`. Public-module relocations later made the test's `_schema.py` and `_snapshot.py` coordinates stale; commit `cbedc8b90c` reconciled them to `schema.py` and `snapshot.py` without changing the gate contract.

## Outcome

The current gate passes with an empty allowlist and scans the live public registry surfaces. Its planted `m303_planted` generic-field mutation and planted `Modelo.M303` generic-construction branch are each detected, while per-modelo code remains outside the prohibition.

Focused verification on 2026-08-26:

- `uv run pytest -q -n 0 src/cadrumo/domain/calculations/registry/tests/test_generic_schema_modelo_naming.py` -> 8 passed in 8.57 seconds.
- Ruff format/check and `git diff --check` passed for commit `cbedc8b90c`.

No Modelo 200 or registry-data path was touched.

## Notes

The earlier execution snapshot recorded five passing tests, one temporary `_schema_exports.py` allowlist entry, and uncommitted work. Those are historical conditions, not the current state: the allowlist is empty, the implementation is committed, the private module names have been retired, and all eight current structural tests pass.

This row owns a prevention gate and therefore deletes no production surface itself. S04 records the field and branch deletion that this gate keeps from returning.
