---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S414'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P33.S414`

Replaced duplicated local storage namespace and key constants with typed registry entries in application code.

- Modified: `src/aeat/application/workflow/_persistence.py`
- Modified: `src/aeat/application/workflow/_profile_bucket_scan.py`
- Modified: `src/aeat/application/user_profile/_repository.py`
- Modified: `src/aeat/application/user_profile/_profile_repository.py`
- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/live/_censo.py`
- Modified: `src/aeat/application/live/_borrador_100.py`
- Modified: `src/aeat/application/filing/_history_repository.py`
- Modified: `src/aeat/application/auth/_apoderado.py`
- Modified: `src/aeat/application/auth/test_apoderado.py`
- Modified: `src/aeat/application/ledger/_rule_repository.py`
- Modified: `src/aeat/application/calculations/_observations_repository.py`
- Modified: `src/aeat/application/calculations/_iva_compensation_history.py`
- Modified: `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`

## Description

Application repositories now derive namespace strings, singleton object keys, schema versions, and sensitivity classes from registry entries instead of carrying local duplicated literals. This includes workflow state/runs, user-profile value/snapshot, repair decisions, live snapshots, filing history, apoderado configuration, ledger classification rules, filing observations, wallet decisions/events, and IVA compensation history.

During verification and review, the runtime-migrated repository suite and reviewer exposed hardening issues. `SecureBoundRepository` now accepts an explicit `bucket_id` and resolves it through `secure_object_repository_for_bucket`; apoderado configuration routes every requested bucket through a physical bucket-bound repository; repair decision listing now uses decrypted records instead of `list_keys` HMAC digests, re-validates each content-addressed decision id, and logs enumeration failures at debug level.

## Tests

Passed:

- `uv run ruff check` on the W15.P33 storage and application slices
- `uv run pytest -q src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_keystore_paths.py src/aeat/application/user_profile/test_repository.py src/aeat/application/workflow/test_persistence.py src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100.py src/aeat/application/test_repair_integrity.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/filing/test_history_repository.py src/aeat/application/filing/test_history_repository_roundtrip.py src/aeat/application/auth/test_apoderado.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
