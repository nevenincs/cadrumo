---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W09.P041.S0244-S0246'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w09-p041-s0241-profile-service-ownership-audit]]"
---

# `cli-workflow-redesign` `W09.P041.S0244-S0246`

Closed plan rows:

- `W09.P041.S0244`
- `W09.P041.S0246`

## Description

**Persistence (S0244).** Added `src/aeat/application/user_profile/_repository.py` exposing two bucket-scoped secure-storage adapters:

- `UserProfileLifecycleRepository` (namespace `aeat.application.user_profile.value`, sensitivity `IDENTITY`) — owns live `UserProfileRecord` aggregates per `(bucket_id, profile_id)`. `load(profile_id)` raises `ProfileNotFoundError` when the row is absent. Object keys follow `user-profile:{bucket_id}:{profile_id}`.
- `UserProfileSnapshotRepository` (namespace `aeat.application.user_profile.snapshot`, sensitivity `IDENTITY`) — owns immutable filing-time snapshots per `(bucket_id, snapshot_id)`. `load(snapshot_id)` raises `ProfileSnapshotNotFoundError` when the row is absent. Object keys follow `user-profile-snapshot:{bucket_id}:{snapshot_id}`.

Both repositories accept an optional `SecureObjectRepository` for test injection, validate non-blank `bucket_id` at construction, and round-trip through the standard `Envelope[T]` schema-versioning gate. The namespace + per-bucket object-key shape mirrors the W61.P301 transaction catalogue contract so the active-bucket plumbing extends naturally.

**Error registry (S0246).** Registered six new typed errors in `aeat.core.errors.registry._domain` and exposed them from `aeat.domain.user_profile`:

- `ProfileNotFoundError` → `REFUSED_PROFILE_NOT_FOUND`
- `ProfileAlreadyExistsError` → `REFUSED_PROFILE_ALREADY_EXISTS`
- `ProfileSchemaValidationError` → `REFUSED_PROFILE_SCHEMA_VALIDATION`
- `ProfilePreflightMissingError` → `REFUSED_PROFILE_PREFLIGHT_MISSING`
- `ProfileSnapshotHashMismatchError` → `INTEGRITY_PROFILE_SNAPSHOT_HASH_MISMATCH`
- `ProfileSnapshotNotFoundError` → `INTEGRITY_PROFILE_SNAPSHOT_NOT_FOUND`

All six derive from `UserProfileError` → `AeatError`. Categories chosen from the existing closed `ErrorCategory` set (`REFUSED`, `INTEGRITY`) — no schema changes needed.

## Modified Paths

- `src/aeat/application/user_profile/__init__.py` (extended exports + lazy import for the two repositories)
- `src/aeat/application/user_profile/_repository.py` (created)
- `src/aeat/application/user_profile/test_repository.py` (created — 7 tests)
- `src/aeat/domain/user_profile/_errors.py` (six new error classes)
- `src/aeat/domain/user_profile/__init__.py` (export the six new errors)
- `src/aeat/core/errors/registry/_domain.py` (six new registry entries)
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

`pytest src/aeat/application/user_profile/` — 12 passed:

- 5 service tests (validation + preflight) from S0243.
- 7 repository tests covering: blank-input rejection for both object-key helpers, canonical composition, bucket-isolated lifecycle round-trip, `ProfileNotFoundError` on missing load, snapshot round-trip preserving the canonical SHA-256 hash, `ProfileSnapshotNotFoundError` on missing snapshot, and namespace constants.

The error-registry binding was verified with a direct `get_registered_error_code(cls).code` check for each of the six new classes.
