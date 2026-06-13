---
tags: ["#audit", "#secure-storage-production-hardening"]
date: "2026-05-26"
modified: '2026-05-26'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# `secure-storage-production-hardening` Code Review

SECURE-STORAGE-RUNTIME-001 | HIGH | Unsecured backend can be reported runtime-ready
`src/aeat/adapters/persistence/storage/runtime.py` originally copied the active session unsecured-backend flag into diagnostics but did not add a readiness issue for it. A matching active bucket route could therefore return `ready=True` for a deterministic unsecured backend. Resolved by adding `UNSECURED_BACKEND` readiness, marking such runtime state unready, and covering it in `src/aeat/adapters/persistence/storage/test_runtime.py`.

SECURE-STORAGE-RUNTIME-002 | HIGH | Runtime diagnostics expose private bucket and path identifiers
`src/aeat/adapters/persistence/storage/runtime.py` originally exposed storage root, route classification with database URL/path, and bucket ids through the public runtime model. Resolved by redacting public runtime output to route kind and boolean attachment/path presence, excluding internal storage-root and bucket-id fields from dumps and repr, and adding JSON serialization coverage that rejects bucket, database, and root path leakage.

SECURE-STORAGE-RUNTIME-003 | MEDIUM | Repository factory trusted stale runtime snapshots
`src/aeat/adapters/persistence/storage/runtime.py` originally allowed a ready runtime snapshot to construct a bucket-attached repository after the live active session changed or disappeared. Resolved by rechecking the current active session immediately before repository construction and refusing missing, sealed, expired, unsecured, or changed-bucket sessions. Added real-session tests for each drift branch.

SECURE-STORAGE-RUNTIME-004 | REVIEW | Final review found no remaining medium or higher findings
The final narrow review verified unsecured backend refusal, public diagnostic redaction, and live-session factory rechecks. Residual low branch-coverage risk was eliminated with additional sealed, expired, and unsecured factory recheck tests.

W02-P03-S13-001 | HIGH | Profile aggregate runtime enrollment bypasses explicit database URL route refusal
`src/aeat/application/user_profile/_repository.py` originally synthesized fresh settings with only `aeat_local_storage_root` and `aeat_active_profile` before calling `inspect_storage_runtime`, dropping any explicit `aeat_database_url` from live settings. Resolved by adding `inspect_bucket_storage_runtime`, which first classifies live settings and keeps explicit database URLs unready/fail-closed, then using that helper from default user-profile repository construction.

SECURE-STORAGE-RUNTIME-005 | REVIEW | W02.P03.S13 explicit-route repair verified
Re-review found no remaining HIGH, CRITICAL, MEDIUM, or LOW findings in named-bucket profile repository routing. Default user-profile repositories resolve through `inspect_bucket_storage_runtime(...).secure_object_repository()`, explicit `aeat_database_url` routes remain unready/fail-closed, normal bucket routes synthesize the requested bucket database, and storage exports expose the runtime helper through the public storage surface.

W02.P03.S14-001 | LOW | Review complete with no HIGH/CRITICAL findings
Profile state projection reads now route through storage runtime readiness; explicit database URL profile reads fail closed as unreadable instead of opening side databases; normal bucket projection remains covered by targeted passing tests.

W02.P03.S14-002 | LOW | Error registry integration verified
StorageValidationError remains registered and registry enforcement and CLI contract tests pass for the reviewed storage-runtime readiness surface.
