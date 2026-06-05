---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
step_id: 'S64'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S64 Registry Binding Verification

Scope: `src/aeat/domain/calculations/registry/tests/test_*binding* src/aeat/domain/calculations/registry/tests`.

## Description

- Verify registry package facade imports for decomposed binding-family symbols.
- Verify no application or CLI code imports the decomposed private registry binding modules.
- Run focused registry binding, selector-shape, public API, detail-record, and application row-set round-trip tests.
- Run ruff over the decomposed registry binding modules and touched tests.

## Outcome

Verification passed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_invoice_bindings.py src/aeat/domain/calculations/registry/tests/test_counterpart_bindings.py src/aeat/domain/calculations/registry/tests/test_detail_record_observations.py src/aeat/domain/calculations/registry/tests/test_selector_shape.py src/aeat/domain/calculations/registry/tests/test_public_api_boundaries.py src/aeat/application/calculations/tests/test_detail_record_round_trip.py src/aeat/application/calculations/tests/test_row_set_assembly.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/calculations/tests/test_grouping_dispatch_coverage.py -q --tb=short` passed with 107 tests.
- `uv run --no-sync ruff check --fix` over the touched registry binding modules and tests completed cleanly, followed by a clean ruff check.
- Package facade smoke import resolved detail-record row resolvers from `aeat.domain.calculations.registry`.
- `rg` found no application or CLI imports into the decomposed private registry binding modules.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-05-codebase-monolith-decomposition-plan.md` passed with only existing warning `PLAN022`.

## Notes

The plan warning `PLAN022` remains the known canonical-id monotonicity warning from earlier plan structure, not a registry binding decomposition failure.
