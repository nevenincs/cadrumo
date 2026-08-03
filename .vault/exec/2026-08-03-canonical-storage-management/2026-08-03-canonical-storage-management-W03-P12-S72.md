---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:f450572608e98eb5e38aa02fcde09fef47930549a64a0d67308bc997230567dc'
step_id: 'S72'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Close the provenance gate's database-path pending-debt entries by declaring taxonomy members for the root-fallback database file and the database file beneath the per-bucket db directory, so the database-URL resolver and the storage-route classifier read declared members instead of joining the root ad hoc

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`
- `src/cadrumo/core/config.py`
- `src/cadrumo/core/_config_storage_route.py`

## Description

- Declare taxonomy members for the root-fallback database file and the database file beneath the per-bucket db directory, so the database-URL resolver and the storage-route classifier read declared members instead of joining the root ad hoc.

## Outcome

Landed in commit `807578540c` ("declare the root-fallback and per-bucket database files"), committed at HEAD. Two new `StorageCategory` members close the last two duplicate database-path derivations: `ROOT_FALLBACK_DATABASE` (root-scoped, the cold-start database before any profile bucket exists) and `BUCKET_DATABASE_FILE` (bucket-relative, the file nested inside the `BUCKET_DATABASE` directory member, which previously governed only the directory and left the file itself an ungoverned leaf). Both are files, `UNBOUNDED_BY_DESIGN` lifecycle, `FIXED` override policy, `PARTICIPATING` in the fingerprint. The provenance gate's `PENDING_ENROLLMENT` table's production-side entries were struck as a result; the table's own docstring confirms "the production enrollments this table opened with were migrated, and their entries went stale and were struck." What remains in the table today is entirely the five master-key/keystore test-re-expression entries S77 already targets — no production debt remains.

## Notes
