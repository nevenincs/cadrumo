---
tags:
  - '#exec'
  - '#retenciones-perceptor-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S09'
related:
  - "[[2026-06-24-retenciones-perceptor-count-plan]]"
---

# Verify retenciones count and M190 withholding parity

## Scope

- `pull==calculate perceptor-count parity`
- `distinct-NIF anti-tautology proof`
- `expected from the AEAT Diseño not the formula`
- `src/aeat/application/calculations/tests`

## Description

- Ground the failing M190/M111 reconciliation helper with `uvx vaultspec-rag search "M190 M111 reconciliation missing binding fact modelo-111-trabajo-dinerario-perceptores test helper" --type code`.
- Ground the source-family split with `uvx vaultspec-rag search "M190 percepciones withholding source resolver not retenciones_aggregation" --type code`.
- Refresh the M190 reconciliation fixture so M111 bound retenciones facts are produced through real `RetencionObservation` rows, `aggregate_retenciones_111`, and `resolve_retenciones_aggregation_binding_values`.
- Verify M190 still uses withholding/percepciones for `decl.total-percepciones`, while monetary M111 relations continue to feed `decl.percepciones-total` and `decl.retenciones-total`.

## Outcome

The M190-focused verification failure is fixed without moving M190 onto the RET-1 perceptor-count source. The test helper now follows the current M111 registry binding contract instead of passing bound 01/02/03 casillas as manual inputs.

Verification:

- `uv run --no-sync ruff check src/aeat/application/calculations/tests/test_modelo_190_111_reconciliation_continuity.py` passed.
- `uv run --no-sync pytest -q --tb=short src/aeat/application/calculations/tests/test_modelo_190_111_reconciliation_continuity.py src/aeat/application/aggregation/tests/test_withholding_source_resolver.py src/aeat/application/calculations/tests/test_modelo_190_percepciones_e2e.py src/aeat/domain/calculations/registry/tests/test_withholding_percepcion_count.py` passed with 12 tests.
- `uv run --no-sync pytest -q --tb=short src/aeat/application/calculations/tests/test_modelo_180_115_reconciliation_continuity.py src/aeat/application/calculations/tests/test_modelo_193_123_reconciliation_continuity.py src/aeat/application/aggregation/tests/test_retenciones_aggregation_resolver.py` passed with 14 tests.
- `uv run --no-sync pytest -q --tb=short src/aeat/application/aggregation/tests/test_retencion_observations_repository_roundtrip.py src/aeat/application/aggregation/tests/test_retenciones.py src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py` passed with 33 tests.
- `uv run --no-sync vaultspec-core vault plan status .vault/plan/2026-06-24-retenciones-perceptor-count-plan.md` reported 9 of 9 steps complete.
- `uv run --no-sync vaultspec-core vault check body-links --feature retenciones-perceptor-count`, `vault check placeholders --feature retenciones-perceptor-count`, `vault check schema --feature retenciones-perceptor-count`, `vault check annotations --feature retenciones-perceptor-count`, `vault check modified-stamp --feature retenciones-perceptor-count`, and `vault check features --feature retenciones-perceptor-count` passed.

## Notes

No fakes, mocks, monkeypatches, skips, or xfails were introduced. The fixture creates typed retencion observations only to feed the same production aggregation and registry binding APIs used by the calculation path.

`uv run --no-sync vaultspec-core vault check all --feature retenciones-perceptor-count` still exits non-zero because the global `feature-rename-integrity` check reports 32 pre-existing exec-folder rename drifts outside this feature. The retenciones feature-local checks listed above are clean.
