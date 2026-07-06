---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S24'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Execution Notes

## Grounding
- RAG search: `uvx vaultspec-rag search "application bucket maintenance tests bucket_paths manifest_path provision_bucket_directory read_manifest BucketLifecycleStatus real source" --type code --max-results 10`.
- Concrete source confirmed from `src/aeat/adapters/persistence/storage/bucket/__init__.py` and exact symbol search:
  - `BucketLifecycleStatus`
  - `bucket_paths`
  - `manifest_path`
  - `provision_bucket_directory`
  - `read_manifest`

## Change
Replaced bucket-maintenance tests that imported bucket storage helpers via `src/aeat/tests/application_adapter_exports.py` with direct imports from `src/aeat/adapters/persistence/storage/bucket`.

Touched files:
- `src/aeat/application/bucket_maintenance/tests/test_sandbox.py`
- `src/aeat/application/bucket_maintenance/tests/test_service_disk_usage.py`

## Verification
- `uv run --no-sync ruff check src/aeat/application/bucket_maintenance/tests/test_sandbox.py src/aeat/application/bucket_maintenance/tests/test_service_disk_usage.py` -> passed.
- `uv run --no-sync pytest -q src/aeat/application/bucket_maintenance/tests/test_sandbox.py src/aeat/application/bucket_maintenance/tests/test_service_disk_usage.py -n 0` -> `18 passed`.
