---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d0a6d5708d1bc0d913113e835f3b69ef1f3780a5e0fbbef377ba885c7131ccb1'
step_id: 'S252'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unwired portal-drift model and synthetic preflight injection path

## Scope

- `Keep portal-registry assembly health`
- `remove the type-only drift DTO and evaluator plus tests that manufactured observations no product path captures`
- `run portal and preflight gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record`

## Changes

- `M` `src/cadrumo/application/preflight.py`
- `M` `src/cadrumo/application/tests/test_preflight.py`
- `D` `src/cadrumo/domain/portals/drift.py`
- `D` `src/cadrumo/domain/portals/tests/test_drift.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/preflight.py src/cadrumo/application/tests/test_preflight.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/tests/test_preflight.py src/cadrumo/domain/portals/tests` -> `fail`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/tests/test_preflight.py -k portal_health` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The combined preflight and portal suite reached 83 passing tests and one unrelated failure in `test_corpus_row_healthy_for_bundled_normatives`; the current bundled normative corpus probe returned unhealthy. The focused portal-health owner test passes, and this Step did not modify corpus data or its probe.
