---
tags:
  - '#exec'
  - '#modelo-runtime-performance'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:30c8b70918a596a532738e5c9434cf69269d8e1e848ce1e6cd783291bd1b21d5'
related:
  - "[[2026-10-07-modelo-runtime-performance-plan]]"
---

# `modelo-runtime-performance` ledger

## Changes

- `S02` `M` `src/cadrumo/application/operations/registry_schema_validation.py`
- `S02` `A` `src/cadrumo/application/operations/tests/test_schema_generator_parity.py`
- `S02` `A` `src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py`
- `S02` `verify:` `uv run --no-sync pytest -m unit src/cadrumo/application/operations/tests/test_schema_generator_parity.py src/cadrumo/application/operations/tests/test_registry_schema_validation.py src/cadrumo/application/operations/tests/test_schema_binding.py src/cadrumo/application/operations/tests/test_contract_invariants.py src/cadrumo/application/operations/tests/test_registry.py src/cadrumo/application/operations/tests/test_public_contracts.py src/cadrumo/application/operations/tests/test_typed_financial_operand_contract.py src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py --basetemp=.tmp/perf-s02-final-pytest -q` -> `pass`
- `S02` `verify:` `uv run --no-sync ty check src/cadrumo/application/operations/registry_schema_validation.py src/cadrumo/application/operations/tests/test_schema_generator_parity.py src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py` -> `pass`
- `S02` `verify:` `uv run --no-sync basedpyright src/cadrumo/application/operations/registry_schema_validation.py` -> `pass`
- `S02` `verify:` `uv run --no-sync pyrefly check src/cadrumo/application/operations/registry_schema_validation.py` -> `pass`
- `S02` `verify:` `uv run --no-sync ruff check src/cadrumo/application/operations/registry_schema_validation.py src/cadrumo/application/operations/tests/test_schema_generator_parity.py src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py` -> `pass`
- `S02` `verify:` `uv run --no-sync ruff format --check src/cadrumo/application/operations/registry_schema_validation.py src/cadrumo/application/operations/tests/test_schema_generator_parity.py src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py` -> `pass`
- `S02` `verify:` `actual alternating production-registry wall median 3.151s to 2.484s; CPU3.109s to 2.438s with identical contracts` -> `pass`
- `S01` `A` `dev/ci/modelo_runtime_benchmark.py`
- `S01` `A` `dev/ci/tests/test_modelo_runtime_benchmark.py`
- `S01` `A` `dev/ci/tests/test_modelo_runtime_benchmark_process.py`
- `S01` `M` `dev/docs/sequences/runner.py`
- `S01` `M` `dev/docs/sequences/runtime_fixture.py`
- `S01` `A` `dev/docs/sequences/tests/test_benchmark_scopes.py`
- `S01` `M` `justfile`
- `S01` `verify:` `uv run --no-sync pytest -n 0 --basetemp=.tmp/pytest-modelo-benchmark-observability-1 -m 'unit or integration' dev/ci/tests/test_modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark_process.py dev/docs/sequences/tests/test_benchmark_scopes.py dev/docs/sequences/tests/test_runtime_fixture.py --tb=line` -> `pass`
- `S01` `verify:` `uv run --no-sync ruff check dev/ci/modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark_process.py dev/docs/sequences/runner.py dev/docs/sequences/runtime_fixture.py dev/docs/sequences/tests/test_benchmark_scopes.py` -> `pass`
- `S01` `verify:` `uv run --no-sync ruff format --check dev/ci/modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark_process.py dev/docs/sequences/runner.py dev/docs/sequences/runtime_fixture.py dev/docs/sequences/tests/test_benchmark_scopes.py` -> `pass`
- `S01` `verify:` `uv run --no-sync ty check dev/ci/modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark_process.py dev/docs/sequences/runner.py dev/docs/sequences/runtime_fixture.py dev/docs/sequences/tests/test_benchmark_scopes.py --output-format concise` -> `pass`
- `S01` `verify:` `just benchmark-modelo-runtime --help` -> `pass`
- `S01` `verify:` `uv run --no-sync pytest -n 0 --basetemp=.tmp/pytest-modelo-performance-probe-3 -m integration .tmp/test_modelo_perf_probe.py --tb=line` -> `pass`
- `S03` `M` `src/cadrumo/domain/modelos/calculation_revision_rendering.py`
- `S03` `M` `src/cadrumo/domain/modelos/tests/test_calculation_revision_rendering.py`
- `S03` `verify:` `uv run --no-sync pytest -v -n0 src/cadrumo/domain/modelos/tests/test_calculation_revision_rendering.py src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py` -> `pass`
- `S03` `verify:` `uv run --no-sync ruff check src/cadrumo/domain/modelos/calculation_revision_rendering.py src/cadrumo/domain/modelos/tests/test_calculation_revision_rendering.py` -> `pass`
- `S03` `verify:` `uv run --no-sync ruff format --check src/cadrumo/domain/modelos/calculation_revision_rendering.py src/cadrumo/domain/modelos/tests/test_calculation_revision_rendering.py` -> `pass`
- `S03` `verify:` `uv run --no-sync ty check src/cadrumo/domain/modelos/calculation_revision_rendering.py src/cadrumo/domain/modelos/tests/test_calculation_revision_rendering.py` -> `pass`
- `S03` `verify:` `uv run --no-sync pyrefly check src/cadrumo/domain/modelos/calculation_revision_rendering.py` -> `pass`
- `S03` `verify:` `uv run --no-sync basedpyright src/cadrumo/domain/modelos/calculation_revision_rendering.py` -> `pass`
- `S03` `verify:` `actual encrypted M100 load median2.147s to1.600s with identical saved JSON and digests` -> `pass`
- `S03` `verify:` `isolated admitted dependency floor pydantic-core2.46.0 serializer constructor and explicit copied-schema serialization` -> `pass`
- `S06` `M` `dev/ci/modelo_runtime_benchmark.py`
- `S06` `M` `dev/ci/tests/test_modelo_runtime_benchmark.py`
- `S06` `verify:` `uv run --no-sync pytest -n 0 --basetemp=.tmp/pytest-modelo-benchmark-startup-1 -m 'unit or integration' dev/ci/tests/test_modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark_process.py dev/docs/sequences/tests/test_benchmark_scopes.py dev/docs/sequences/tests/test_runtime_fixture.py --tb=line` -> `pass`
- `S06` `verify:` `uv run --no-sync pytest -n 0 --basetemp=.tmp/pytest-modelo-benchmark-startup-cache-1 -m unit dev/ci/tests/test_modelo_runtime_benchmark.py::test_observed_real_cli_materialization_keeps_its_cache_and_restores_after_failure --tb=line` -> `pass`
- `S06` `verify:` `uv run --no-sync ruff check dev/ci/modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark_process.py` -> `pass`
- `S06` `verify:` `uv run --no-sync ruff format --check dev/ci/modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark_process.py` -> `pass`
- `S06` `verify:` `uv run --no-sync ty check dev/ci/modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark.py dev/ci/tests/test_modelo_runtime_benchmark_process.py --output-format concise` -> `pass`
- `S05` `M` `src/cadrumo/application/modelo/selectors.py`
- `S05` `M` `src/cadrumo/application/modelo/revision_selection_operation.py`
- `S05` `M` `src/cadrumo/application/modelo/tests/test_revision_selection_operation.py`
- `S05` `A` `src/cadrumo/application/modelo/tests/test_selector_catalogue_reads.py`
- `S05` `verify:` `uv run --no-sync pytest -n 0 -m unit src/cadrumo/application/modelo/tests/test_selector_catalogue_reads.py src/cadrumo/application/modelo/tests/test_revision_selection_operation.py src/cadrumo/application/modelo/tests/test_revision_id_d1_resolver_policy.py --basetemp=.tmp/modelo-selector-dedup-tests-boundaries -q` -> `pass`
- `S05` `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/selectors.py src/cadrumo/application/modelo/revision_selection_operation.py src/cadrumo/application/modelo/tests/test_revision_selection_operation.py src/cadrumo/application/modelo/tests/test_selector_catalogue_reads.py` -> `pass`
- `S05` `verify:` `uv run --no-sync basedpyright src/cadrumo/application/modelo/selectors.py src/cadrumo/application/modelo/revision_selection_operation.py src/cadrumo/application/modelo/tests/test_revision_selection_operation.py src/cadrumo/application/modelo/tests/test_selector_catalogue_reads.py` -> `pass`
- `S05` `verify:` `uv run --no-sync pyrefly check src/cadrumo/application/modelo/selectors.py src/cadrumo/application/modelo/revision_selection_operation.py src/cadrumo/application/modelo/tests/test_revision_selection_operation.py src/cadrumo/application/modelo/tests/test_selector_catalogue_reads.py` -> `pass`
- `S05` `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/selectors.py src/cadrumo/application/modelo/revision_selection_operation.py src/cadrumo/application/modelo/tests/test_revision_selection_operation.py src/cadrumo/application/modelo/tests/test_selector_catalogue_reads.py` -> `pass`
- `S05` `verify:` `uv run --no-sync ruff format --check src/cadrumo/application/modelo/selectors.py src/cadrumo/application/modelo/revision_selection_operation.py src/cadrumo/application/modelo/tests/test_revision_selection_operation.py src/cadrumo/application/modelo/tests/test_selector_catalogue_reads.py` -> `pass`
- `S07` `M` `src/cadrumo/domain/calculations/registry/schema_surfaces.py`
- `S07` `A` `src/cadrumo/domain/calculations/registry/tests/test_schema_surface_duplicate_identities.py`
- `S07` `verify:` `uv run --no-sync pytest -v -n0 src/cadrumo/domain/calculations/registry/tests/test_schema_surface_duplicate_identities.py src/cadrumo/domain/modelos/tests/test_calculation_revision_rendering.py src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py` -> `pass`
- `S07` `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/schema_surfaces.py src/cadrumo/domain/calculations/registry/tests/test_schema_surface_duplicate_identities.py` -> `pass`
- `S07` `verify:` `uv run --no-sync ruff format --check src/cadrumo/domain/calculations/registry/schema_surfaces.py src/cadrumo/domain/calculations/registry/tests/test_schema_surface_duplicate_identities.py` -> `pass`
- `S07` `verify:` `uv run --no-sync ty check src/cadrumo/domain/calculations/registry/schema_surfaces.py src/cadrumo/domain/calculations/registry/tests/test_schema_surface_duplicate_identities.py` -> `pass`
- `S07` `verify:` `uv run --no-sync pyrefly check src/cadrumo/domain/calculations/registry/schema_surfaces.py` -> `pass`
- `S07` `verify:` `uv run --no-sync basedpyright src/cadrumo/domain/calculations/registry/schema_surfaces.py` -> `pass`
