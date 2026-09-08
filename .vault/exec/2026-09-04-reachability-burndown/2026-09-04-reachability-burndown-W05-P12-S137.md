---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:5d62dff1d70334062bfa7126d72c1a9b48e56987c5dcba32060afd8c9431d25f'
step_id: 'S137'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the previous-filing source-year registry-coverage gate and its allowance ledger because previous_filing consumes evidence-backed filed observations rather than source-year registry snapshots, and retire the registry reviewability size thresholds and per-module baselines instead of repinning deleted modules

## Scope

- `registry-wide validation`
- `previous-filing year validator and tests`
- `reviewability threshold tests`
- `live embed signal`
- `and cross-period authority`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/validate_registry_scope.py`
- `D` `src/cadrumo/domain/calculations/registry/_validate_previous_filing_year_coverage.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_validate_previous_filing_year_coverage.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_registry_reviewability.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/validate_registry_scope.py src/cadrumo/domain/calculations/registry/_validate_relation_sources.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/domain/calculations/registry/tests/test_authority.py src/cadrumo/domain/calculations/registry/tests/test_committed_registry.py src/cadrumo/domain/calculations/registry/tests/test_relation_closure.py` -> `pass`

## Notes

The live modelo embed signal fell from 26 to 22. The deleted validator's stale row in the development load-classification subsystem is intentionally not updated; that authored metastate subsystem is the next owner.
