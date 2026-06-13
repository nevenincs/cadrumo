---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P22-S90]]'
---

# `secure-storage-production-hardening` Code Review

S90-SELF | INFO | Review opened for `W12.P22.S90`.
Scope: preserve `_profile_bucket_scan` as a plaintext manifest discovery adapter, keep encrypted runtime attachment in repository/runtime paths, and remove deprecated inactive or explicit-database shortcuts from adjacent user-profile repository tests.

S90-001 | HIGH | User-profile repository tests still bypassed runtime-owned repository construction.
Initial review found `test_repository.py` directly assembled `SecureObjectRepository` with explicit engine construction and metadata creation. That test seam could pass while `_secure_objects_for_bucket` and runtime route attachment were broken.

S90-002 | HIGH | Default repository tests still manufactured fallback active-bucket sessions.
Initial review found `activate_master_key_provider(..., fallback_bucket_id=...)` paired with `aeat_active_profile=None` in default repository tests. That preserved the deprecated inactive shortcut instead of exercising an active profile bucket.

S90-003 | MEDIUM | Explicit database refusal coverage was combined with fallback enrollment.
Initial review found explicit `aeat_database_url` refusal coverage mixed with fallback bucket session activation. The explicit route test needed to remain a fail-closed runtime policy check only.

S90-REMEDIATION | PASS | Review findings remediated before closure.
`test_repository.py` now provisions a real plaintext bucket manifest, activates `EphemeralMasterKeyProvider` through active-profile settings, and lets `UserProfileLifecycleRepository` / `UserProfileSnapshotRepository` construct their default runtime-owned secure-object repositories. Direct `SecureObjectRepository`, explicit engine construction, metadata creation, `objects=` injection, and fallback session activation were removed from the reviewed test file. The explicit database URL case remains only as fail-closed route refusal coverage with an active profile session.

S90-REREVIEW | PASS | Narrow re-review passed after remediation.
Re-review found no high or critical issues. The reviewer verified the manifest scanner boundary guard remains source/AST-based against `_profile_bucket_scan`, the malformed-manifest test surfaces scan issues, default repository tests use manifest-backed active-profile sessions, and explicit `aeat_database_url` appears only in the fail-closed route refusal test.
