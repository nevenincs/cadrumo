---
tags:
  - '#exec'
  - '#modelo-190-percepciones-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S03'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-plan]]"
---

# Add a distinct (perceptor, clave, subclave) count aggregation over the withholding source

## Scope

- `src/aeat/domain/calculations/registry/_withholding_bindings.py`

## Description

- Ground current implementation with `uvx vaultspec-rag search "modelo 190 percepciones count withholding source current plan P01 P05" --type code`.
- Inspect the withholding binding resolver implementation and selector validation.
- Run the focused distinct-count tests.

## Outcome

- `percepcion_count` is a supported withholding fact in `src/aeat/domain/calculations/registry/_withholding_bindings.py`.
- The selector validator requires `percepcion_count` to use aggregation op `count_distinct`.
- Runtime resolution counts the distinct tuple `(perceptor_tax_id, clave, subclave)`, not only distinct NIF and not quarterly perceptor-count sums.
- Verification passed in the combined M190 slice: `uv run --no-sync pytest -q --tb=short src/aeat/entrypoints/cli/tests/test_withholding_producer.py src/aeat/domain/calculations/registry/tests/test_withholding_percepcion_count.py src/aeat/application/aggregation/tests/test_withholding_source_resolver.py src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py src/aeat/application/modelo/tests/test_source_boundary_and_enrollment.py::test_s27_withholding_source_kind_is_enrolled_not_deferred src/aeat/application/calculations/tests/test_modelo_190_percepciones_e2e.py src/aeat/application/calculations/tests/test_modelo_190_111_reconciliation_continuity.py src/aeat/domain/calculations/registry/tests/test_modelo_190_193_round_trip.py`: 22 passed.

## Notes

- No code change was needed for S03; the primitive already exists in the current tree.
