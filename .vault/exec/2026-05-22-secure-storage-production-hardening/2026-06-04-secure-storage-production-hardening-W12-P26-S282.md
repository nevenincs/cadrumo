---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S282'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S282 - Close AFR-180 for workflow models

Scope: close `AFR-180` for `src/aeat/application/workflow/_models.py` with
signals `secure-object, active-profile, manifest-bucket`, target `runtime-default`,
and owner `W12.P21.S85`.

## Description

- Audited workflow model records, active-profile resolution, and active transaction
  catalogue runtime binding.
- Preserved centralized active-bucket and secure-object runtime helpers; no new path,
  environment, manifest, SQL, or master-key route was introduced.
- Added debug observability when `active_profile_record()` catches a narrowed
  `ProfileNotFoundError` and returns the existing `None` contract.
- Ran vaultspec RAG semantic search and focused workflow model/runtime tests.

## Outcome

`AFR-180` is closed as a runtime-default workflow model boundary. The slice continues
to use shared pydantic models and runtime helpers, and the missing active-profile
record path is no longer silent.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/workflow/_models.py src/aeat/application/workflow/test_models.py src/aeat/application/workflow/test_active_profile_resolution.py src/aeat/application/workflow/test_transaction_catalogue_resolution.py src/aeat/application/workflow/test_state_persistence_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_models.py src/aeat/application/workflow/test_active_profile_resolution.py src/aeat/application/workflow/test_transaction_catalogue_resolution.py src/aeat/application/workflow/test_state_persistence_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "workflow models WorkflowState ProfileBucketPointer secure object active profile manifest bucket runtime default" --type code --port 8766 --max-results 10`

## Notes

The returned value for a missing active profile record remains `None`; only debug
observability changed.
