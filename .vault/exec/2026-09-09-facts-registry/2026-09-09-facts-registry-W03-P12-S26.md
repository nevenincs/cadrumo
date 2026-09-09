---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:3bfebd51214b66c2ead38cf1b3230a8660ef0e79e56de0ae8deda3410a38b043'
step_id: 'S26'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Rewire IVA lookups while preserving domain facades

## Scope

- `src/cadrumo/domain/iva`

## Changes

- `M` `src/cadrumo/domain/iva/lookup.py`
- `M` `src/cadrumo/domain/iva/recargo_equivalencia.py`
- `M` `src/cadrumo/domain/iva/tests/test_rates_temporal.py`
- `M` `src/cadrumo/domain/iva/tests/test_recargo_rate_applied_rate_lookup.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W03-P12-S26.md`
- `verify:` `uv run basedpyright src/cadrumo/domain/iva/lookup.py src/cadrumo/domain/iva/recargo_equivalencia.py src/cadrumo/domain/iva/tests/test_rates_temporal.py src/cadrumo/domain/iva/tests/test_recargo_rate_applied_rate_lookup.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/iva/lookup.py src/cadrumo/domain/iva/recargo_equivalencia.py src/cadrumo/domain/iva/tests/test_rates_temporal.py src/cadrumo/domain/iva/tests/test_recargo_rate_applied_rate_lookup.py` -> `pass`
- `verify:` `uv run pytest src/cadrumo/domain/iva/tests/test_rates.py src/cadrumo/domain/iva/tests/test_rates_temporal.py src/cadrumo/domain/iva/tests/test_recargo_rate_applied_rate_lookup.py -q` -> `pass`
