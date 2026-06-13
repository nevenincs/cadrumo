---
tags: ["#exec", "#secure-storage-production-hardening"]
date: "2026-05-22"
modified: '2026-05-22'
step_id: "S08"
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# `secure-storage-production-hardening` `W01.P02.S08`

Enforced unsecured-backend refusal at provider activation and secure-object read/write boundaries.

- Modified: `src/aeat/adapters/persistence/storage/master_key/_master_key.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`
- Modified: `src/aeat/entrypoints/cli/test_profile_create_taxpayer_type_paths.py`

## Description

Unsecured provider activation now scans active profile buckets for persisted user-profile payloads and refuses activation when it cannot prove the profile carries only sanctioned synthetic identifiers. The literal unsecured fallback bucket remains available for isolated test storage, but real profile buckets fail closed when decrypting the profile row fails or when a real tax identifier is detected.

`SecureObjectRepository` now applies the same policy at the user-profile secure-object boundary. Writes, single-record reads, and failure-stream iteration refuse real Spanish tax identifiers when the active session is backed by `UnsecuredMasterKeyProvider`, while synthetic placeholder identifiers continue to work for tests and scrubbed fixtures.

Every public secure-object repository method now proves a live active session before touching rows. Mutating operations additionally reject a bucket-layout engine route that points at a different bucket than the active session, closing wrong-DEK cross-bucket writes while leaving explicit database URL policy to the next S09/S10 route-guard steps.

Profile payload parsing now fails closed under the unsecured backend when the profile namespace payload is malformed or does not expose an `identity.tax_id` fact. The route guard also exposed a profile-switch binding bug; switch/read helpers now bind the target active profile and target bucket database URL together so target-bucket writes do not retain the previous route.

After re-review, the route guard was tightened again: non-synthetic mutating operations now require the exact active bucket database route and reject root fallback, non-bucket, and outside-root database paths. Quarantine uses the same matching-route guard, and empty `save_many(())` now proves a live session before returning. Wizard create/edit also binds the target bucket database URL before persistence so prebuilt settings overrides cannot retain a stale root fallback route.

CLI tests that intentionally run under the unsecured backend now seed or create profiles with canonical synthetic identifiers. This keeps the test backend aligned with production privacy policy instead of weakening the storage guard.

## Tests

Validated the secure-object policy and activation guard with focused storage tests:

- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/test_profile_create_taxpayer_type_paths.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py -q`
- `uv run --no-sync ruff check` on the touched S05-S08 storage and CLI files
