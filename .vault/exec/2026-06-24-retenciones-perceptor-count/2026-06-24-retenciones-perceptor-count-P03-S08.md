---
tags:
  - '#exec'
  - '#retenciones-perceptor-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S08'
related:
  - "[[2026-06-24-retenciones-perceptor-count-plan]]"
---

# Close M193 cutover and document M190 percepciones split

## Scope

- `src/aeat/_data/registry/aeat/modelos/193`
- `src/aeat/_data/registry/aeat/modelos/190`
- `src/aeat/application/calculations/tests`

## Description

- Verify M193 binds `modelo-193-123-perceptores-anual` with `source = "retenciones_aggregation"` and `fact = "perceptor_count_distinct"`.
- Verify M193 monetary base and retenciones totals remain relation-prefill bindings.
- Verify M190 deliberately remains outside `retenciones_aggregation`: `modelo-190-percepciones-anual` uses `source = "withholding"` and `fact = "percepcion_count"` over distinct `(perceptor, clave, subclave)` rows.
- Edit P03.S08 wording to document the obsolete M190 grouping as a scoped deviation, not a production target.

## Outcome

M193 satisfies the distinct-NIF retenciones cutover. M190 is closed by documented deviation: its annual header field is not a perceptor count and is correctly handled by the withholding/percepciones source.

Verification: `uv run --no-sync pytest -q --tb=short src/aeat/application/calculations/tests/test_modelo_180_115_reconciliation_continuity.py src/aeat/application/calculations/tests/test_modelo_193_123_reconciliation_continuity.py src/aeat/application/aggregation/tests/test_retenciones_aggregation_resolver.py` passed with 14 tests. The M190-specific set `uv run --no-sync pytest -q --tb=short src/aeat/application/calculations/tests/test_modelo_190_111_reconciliation_continuity.py src/aeat/application/aggregation/tests/test_withholding_source_resolver.py src/aeat/application/calculations/tests/test_modelo_190_percepciones_e2e.py src/aeat/domain/calculations/registry/tests/test_withholding_percepcion_count.py` passed with 12 tests.

## Notes

The previous P03.S08 wording was overbroad because it grouped M190 with M193. Current code and tests preserve the legal/source distinction: M193 counts distinct perceptores; M190 counts distinct percepciones.
