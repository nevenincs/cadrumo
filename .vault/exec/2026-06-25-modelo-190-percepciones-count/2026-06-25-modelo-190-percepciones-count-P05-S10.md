---
tags:
  - '#exec'
  - '#modelo-190-percepciones-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S10'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-plan]]"
---

# Add the distinct-count regression and run the full registry and aggregation suites

## Scope

- `src/aeat/application/aggregation/tests`

## Description

- Run focused M190/withholding registry, aggregation, enrollment, and calculation tests.
- Incorporate read-only verifier findings from the independent explorer pass.
- Classify the broad registry+aggregation sweep status under the shared-worktree owner-aware gate.

## Outcome

- Focused owner slice passed: `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_withholding_producer.py` reported all checks passed.
- Focused owner slice passed: `uv run --no-sync pytest -q --tb=short src/aeat/entrypoints/cli/tests/test_withholding_producer.py src/aeat/domain/calculations/registry/tests/test_withholding_percepcion_count.py src/aeat/application/aggregation/tests/test_withholding_source_resolver.py src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py src/aeat/application/modelo/tests/test_source_boundary_and_enrollment.py::test_s27_withholding_source_kind_is_enrolled_not_deferred src/aeat/application/calculations/tests/test_modelo_190_percepciones_e2e.py src/aeat/application/calculations/tests/test_modelo_190_111_reconciliation_continuity.py src/aeat/domain/calculations/registry/tests/test_modelo_190_193_round_trip.py`: 22 passed.
- Independent read-only verifier ran a broader registry+aggregation attempt and reported 4071 passed, 3 failed. The failures were unrelated Modelo 100 registry/legal-ref failures, not M190 percepciones-count failures.

## Notes

- The full registry+aggregation lane is not honestly all-green in the shared worktree today because of unrelated Modelo 100 failures. This step closes the M190-owned regression and records the broad-suite caveat for follow-up rather than claiming global green.
