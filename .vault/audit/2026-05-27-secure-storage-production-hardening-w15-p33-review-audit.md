---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` W15.P33 Review

W15.P33 review covered the typed namespace registry, application enrollment, storage hierarchy centralization, and repair-decision listing behavior.

## Findings

| Id | Severity | Status | Finding |
|---|---|---|---|
| W15-P33-001 | HIGH | Resolved | Apoderado configuration used the requested bucket only as the secure-object key while routing repository IO through the active/default bucket. |
| W15-P33-002 | MEDIUM | Resolved | Registry-declared sensitivity could drift from consumers because workflow, live snapshots, and attachments still hard-coded sensitivity classes at read/write gates. |
| W15-P33-003 | MEDIUM | Resolved | The wrapped bucket DEK filename remained duplicated as `bucket.dek.json` outside the typed hierarchy registry. |
| W15-P33-004 | LOW | Resolved | Repair-decision listing returned an empty tuple on enumeration failure without logging the failure cause. |
| W15-P33-005 | MEDIUM | Resolved | User-profile value/snapshot repositories still hard-coded IDENTITY sensitivity after namespace and schema were registry-derived. |
| W15-P33-006 | MEDIUM | Resolved | Repair-decision listing still degraded contract-invalid decision rows to debug-only skips after the HMAC digest issue was fixed. |
| W15-P33-007 | LOW | Resolved | Apoderado namespace scope was still marked profile-local despite explicit bucket-local routing. |

## Resolution Notes

- Apoderado now constructs `_ApoderadoConfigRepository(bucket_id=...)` per requested bucket and caches repositories by safe bucket id. The regression test now writes bucket A and bucket B and asserts both physical bucket databases exist.
- Workflow state/runs, live censo/borrador snapshots, and attachment blobs/manifests now derive sensitivity from their registry definitions, not local `SensitivityClass` literals.
- `BUCKET_DEK_FILENAME` and the `bucket_dek` storage path definition were added to the registry; master-key and profile repository code consume the shared filename.
- Repair-decision listing now surfaces enumeration failures and invalid decision rows instead of degrading them to an empty listing.
- User-profile value/snapshot sensitivity now comes from the namespace registry definitions.
- Apoderado namespace scope is now `BUCKET_LOCAL`, matching the physical repository route.

## Verification

Passed:

- `uv run ruff check` on W15.P33 storage and application slices.
- `uv run pytest -q src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_keystore_paths.py src/aeat/application/user_profile/test_repository.py src/aeat/application/workflow/test_persistence.py src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100.py src/aeat/application/test_repair_integrity.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/filing/test_history_repository.py src/aeat/application/filing/test_history_repository_roundtrip.py src/aeat/application/auth/test_apoderado.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `uv run pytest -q src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/application/user_profile/test_repository.py src/aeat/application/test_repair_integrity.py src/aeat/application/auth/test_apoderado.py`
