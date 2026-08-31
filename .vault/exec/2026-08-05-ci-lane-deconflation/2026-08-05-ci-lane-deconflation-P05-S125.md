---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f81c54da9711a94c80cb4de94d096f031b79249c98b84a989653c64a87a07e51'
step_id: 'S125'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in _namespace_registry.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/__init__.py`
- `M` `src/cadrumo/adapters/persistence/storage/_secure_object_namespaces.py`
- `A` `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`
- `M` `src/cadrumo/adapters/persistence/storage/_storage_path_definitions.py`
- `M` `src/cadrumo/adapters/persistence/storage/attachment.py`
- `M` `src/cadrumo/adapters/persistence/storage/blob_store/_blob_store.py`
- `M` `src/cadrumo/adapters/persistence/storage/runtime.py`
- `M` `src/cadrumo/adapters/persistence/storage/runtime_repository.py`
- `M` `src/cadrumo/adapters/persistence/storage/sql/_secure_object_row_codec.py`
- `M` `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_inner_envelope_vacuity_invariants.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_key_grammar.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_runtime.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_schema_lineage.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_staged_bucket_repository.py`
- `M` `src/cadrumo/application/tests/test_storage_namespace_adoption.py`
- `verify:` `uv run --no-sync pytest --collect-only -q src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry_taxonomy_consumer.py src/cadrumo/application/tests/test_storage_namespace_adoption.py src/cadrumo/adapters/persistence/storage/tests/test_attachment_store_roundtrip.py` -> `pass (71 collected, exit 0)`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry_taxonomy_consumer.py src/cadrumo/application/tests/test_storage_namespace_adoption.py src/cadrumo/adapters/persistence/storage/tests/test_attachment_store_roundtrip.py` -> `pass (71 passed, exit 0)`
- `verify:` `uv run --no-sync ruff check <S125 paths>` -> `pass (exit 0)`
- `verify:` `uv run --no-sync ruff format --check <S125 paths>` -> `pass (exit 0)`
- `verify:` `uv run --no-sync python -c "from cadrumo.tests._size_budget import measure_module_lines; ..."` -> `pass (_namespace_registry.py 174/1250; _secure_object_namespaces.py 1203/1250; exit 0)`

## Notes

- `uv run --no-sync python -m dev.audit.size_budget` remains red only for the 89 live subjects assigned to remaining P05 rows; neither S125 source is a finding.
