---
tags:
  - '#exec'
  - '#retenciones-perceptor-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S07'
related:
  - "[[2026-06-24-retenciones-perceptor-count-plan]]"
---

# Close M180 perceptores retenciones aggregation cutover

## Scope

- `keep the base/retenciones monetary relations`
- `src/aeat/_data/registry/aeat/modelos/180`

## Description

- Verify both M180 revisions bind `modelo-180-115-perceptores-anual` with `source = "retenciones_aggregation"`.
- Verify the M180 perceptor-count selector targets `decl.total-perceptores` with `fact = "perceptor_count_distinct"`.
- Verify the monetary base and retenciones bindings remain relation-prefill relations instead of being moved onto the perceptor-count source.

## Outcome

M180 P03 cutover is present at current HEAD. The annual perceptor count is no longer sourced from an op=sum quarterly relation; the base and retenciones totals remain on the relation-prefill monetary path.

Verification: `uv run --no-sync pytest -q --tb=short src/aeat/application/calculations/tests/test_modelo_180_115_reconciliation_continuity.py src/aeat/application/calculations/tests/test_modelo_193_123_reconciliation_continuity.py src/aeat/application/aggregation/tests/test_retenciones_aggregation_resolver.py` passed with 14 tests.

## Notes

No production code changed in this checkpoint for S07; closure records current-state verification.
