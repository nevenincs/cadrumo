---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d74b3dc873521a31cc5f7894d22b7751e9ac7a89215ff2c139bd7af5e66b6b21'
step_id: 'S326'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the IVA-category AST singularity registry and its embedded rival classifiers

## Scope

- `IVA category source census`
- `focused ledger behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_iva_category_singularity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_ledger_tax_fact_manipulations.py src/cadrumo/tests/test_ledger_modelo_staleness.py src/cadrumo/tests/test_ledger_corpus_fidelity.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 279 unused symbols. The separate rate-observation source census remains red on concurrent aggregation changes; the three owning ledger behavior suites pass 14 tests.
