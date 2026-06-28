---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S1534-S1550'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
---

# `cli-workflow-redesign` `W52` registry provider integration closeout

Completed the remaining W52 provider-adapter and registry-integration test slice without adding placeholder persistence paths or uncommitted modelo semantics.

- Added: `src/aeat/application/aggregation/_registry_provider.py`
- Added: `src/aeat/application/aggregation/test_per_modelo_registry_provider.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

Baseline verification found W52 had two open rows:

- `S1534`: connect persistence, bucket events, registry data, or provider adapters required by per-modelo aggregation.
- `S1550`: add persistence or registry integration tests for per-modelo aggregation.

The committed registry surface currently has real counterpart aggregation bindings for Modelo 349. It does not yet declare equivalent per-modelo aggregation bindings for 347, 720, or the retenciones modelos. This slice therefore implements the real Modelo 349 registry provider adapter and explicitly avoids inventing unsupported provider semantics.

The new registry provider adapter:

- accepts the central `PerModeloAggregationCommand`;
- delegates aggregation through `aggregate_per_modelo`;
- resolves committed Modelo 349 counterpart binding values from a supplied `ModeloRevision`;
- resolves committed row binding values and bound casilla inputs through the registry calculation APIs;
- filters observations by the binding source kinds committed in the registry revision;
- filters registry facts through the central 349 aggregation readiness gates before resolving bindings;
- refuses revisions that declare counterpart bindings for unsupported modelo/provider combinations.

The integration test loads the committed `registry/aeat` authority, snapshots Modelo 349 for filing year 2026 and period `1T`, and verifies scalar bindings, row bindings, casilla values, committed source-kind filtering, and readiness-gate filtering for foreign NIF-IVA and Spanish GROI failures. It does not use mocks, fakes, stubs, monkeypatching, xfail, or skipped assertions.

Rows checked in the plan:

- `S1534` provider adapter integration
- `S1550` committed registry integration coverage

## Tests

Focused verification passed:

- `uv run --no-sync ruff check src/aeat/application/aggregation/_registry_provider.py src/aeat/application/aggregation/test_per_modelo_registry_provider.py src/aeat/application/aggregation/__init__.py`
- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_per_modelo_registry_provider.py src/aeat/application/aggregation/test_per_modelo_service.py src/aeat/domain/calculations/registry/test_modelo_349_registry.py::test_committed_modelo_349_full_counterpart_to_casilla_pipeline`
- Post-review rerun: same focused command passed 16 tests after readiness-gate coverage was added.

Wider behavior verification passed:

- `uv run --no-sync pytest -q src/aeat/application/aggregation src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py::test_per_modelo_aggregation_placeholder_paths_stay_removed src/aeat/entrypoints/cli/test_backend_boundary.py::test_per_modelo_aggregation_duplicate_cli_surfaces_stay_absent src/aeat/entrypoints/cli/test_backend_boundary.py::test_legacy_application_aggregation_test_tree_stays_absent src/aeat/entrypoints/cli/test_backend_boundary.py::test_cli_unit_tests_do_not_contain_process_state_or_xfail_language`
- Post-review rerun: same wider command passed 216 tests after readiness-gate coverage was added.

Known unrelated lint limitation:

- `uv run --no-sync ruff check src/aeat/application/aggregation src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py` currently reports existing `N813` import-alias violations in `src/aeat/application/aggregation/_errors.py` and `src/aeat/application/aggregation/_models.py`. The touched files pass targeted lint.

Baseline/review context:

- Fast baseline agent confirmed W52 open rows were exactly `S1534` and `S1550`, and that committed registry-backed per-modelo aggregation semantics currently exist for Modelo 349 only.
- Scoped code review found a readiness-gate bypass in the first provider adapter. Remediation now derives eligible registry facts from `CounterpartAggregation` rollups whose `declarable_readiness_satisfied` flag is true, preserving the central service's GROI/NIF-IVA gates before registry binding resolution.
