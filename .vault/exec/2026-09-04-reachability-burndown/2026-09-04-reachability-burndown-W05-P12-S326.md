---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:c490535afc4af5c6f7807aa0f1f8077bd186f3d916c88406d10f132178f94753'
step_id: 'S326'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
