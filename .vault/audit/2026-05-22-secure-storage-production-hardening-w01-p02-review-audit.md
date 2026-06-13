---
tags: ["#audit", "#secure-storage-production-hardening"]
date: "2026-05-22"
modified: '2026-05-22'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
  - "[[2026-05-22-secure-storage-production-hardening-architecture-adr]]"
  - "[[2026-05-22-secure-storage-production-hardening-W01-P02-S05]]"
  - "[[2026-05-22-secure-storage-production-hardening-W01-P02-S06]]"
  - "[[2026-05-22-secure-storage-production-hardening-W01-P02-S07]]"
---

# `secure-storage-production-hardening` Code Review


W01P02-001 | HIGH | Missing bucket DEK can silently degrade to legacy key schedule

The first S05 implementation treated any registered manifest without `bucket.dek.json` as a legacy bucket and returned the provider KEK as the data key. Because the manifest carried no explicit key-schedule marker, a current bucket whose wrapped DEK file was deleted or torn could degrade to the legacy path and start mixed-key writes instead of failing closed.

Required repair: add a durable manifest key-schedule marker or schema bump. Only explicit legacy manifests may use the legacy KEK-as-DEK path; bucket-DEK manifests must refuse missing or invalid wrapped DEK state.

W01P02-002 | HIGH | Fallback bucket id authorized DEK minting outside explicit enrollment

The first S05 implementation used `fallback_bucket_id == bucket_id` as permission to mint a missing bucket DEK. Several non-create paths use fallback bucket ids to resolve the target bucket, so missing or corrupt manifests could create custody material outside the profile-create enrollment path.

Required repair: separate bucket resolution from enrollment permission. Only profile-create enrollment may mint a bucket DEK; read, switch, import, repair, and other fallback-targeted paths must refuse missing manifests or missing DEK state without writing key material.

W01P02-003 | MEDIUM | Keyring provisioning has no cross-process first-create lock

Keyring provisioning still performs read-then-set without a durable interprocess lock. Two concurrent first profile creates can both observe absent key material and mint different master keys, potentially wrapping bucket DEKs under a key that is immediately overwritten.

Required repair: serialize keyring provisioning with the same durable lock discipline as the file backend, then re-check key existence inside the lock before minting.

W01P02-004 | MEDIUM | Unsecured-backend real-tax-id refusal leaks raw tax identifier

The unsecured backend refusal includes the raw tax identifier in its operator-facing diagnostic. The architecture forbids tax identifiers escaping through diagnostics.

Required repair: remove the raw identifier from the message or pass it through the project redaction helper before formatting.

W01P02-005 | INFO | Repair pass applied for S05-S07 review findings

Repair changes added an explicit `key_schedule` manifest marker, made current `bucket-dek-v1` manifests fail closed when the wrapped DEK is missing, preserved explicit legacy manifests on the old KEK-as-DEK path, separated fallback bucket resolution from `allow_bucket_dek_enrollment`, serialized keyring provisioning behind a durable lock, and removed the raw tax identifier from the unsecured-backend refusal text.

Validation after repair: focused storage and manifest tests passed, profile lifecycle CLI tests passed, real subprocess custody profile-create test passed, setup bucket provisioning tests passed, and scoped Ruff checks passed. A narrow re-review is pending before continuing to S08.

W01P02-006 | MEDIUM | Existing wrapped DEK can authorize activation before manifest validation

The first repair still unwrapped an existing `bucket.dek.json` before requiring a valid bucket manifest. A non-create fallback path could therefore activate an unregistered or torn bucket when the manifest was missing but the keystore file remained.

Required repair: make manifest state authoritative. No manifest means no non-enrollment activation even if a wrapped DEK exists. Only explicit enrollment mode may mint or reuse staged DEK material before the manifest exists.

W01P02-007 | INFO | Manifest-authority repair re-review passed

Narrow re-review reported no remaining findings for S05-S07 after the manifest-authority repair. The reviewed surface now requires manifest state for non-enrollment activation, permits pre-manifest DEK staging only in explicit enrollment mode, fails closed for `bucket-dek-v1` manifests missing `bucket.dek.json`, keeps explicit legacy manifests readable, and did not reintroduce `config init` or retired `security` custody command guidance.

W01P02-008 | HIGH | SecureObjectRepository mutating routes can target a different bucket than the active session

The first S08 implementation checked unsecured profile payloads but did not bind mutating secure-object operations to the active `BucketSession` route. An injected repository engine could target bucket B while bucket A's session was active, causing wrong-DEK writes or bypassing activation-time unsecured scans.

Required repair: make mutating repository operations validate that a bucket-layout engine path matches the active session bucket id. Leave explicit/root fallback route rejection to S09/S10, but fail closed on active-bucket-to-different-bucket writes now.

W01P02-009 | MEDIUM | Secure-object metadata and raw iteration methods bypass session freshness

The first S08 implementation refreshed sessions only on `load`, `save`, `save_many`, and `delete`. Raw iteration, metadata, existence, namespace, and integrity methods could run without proving a live session and without extending the idle window.

Required repair: call the active-session freshness guard at every public secure-object repository boundary.

W01P02-010 | MEDIUM | Unsecured profile canary fails open on malformed profile payloads

The first S08 implementation returned an empty tax-id set for malformed, legacy-shaped, future-shaped, or tax-id-missing profile payloads. Under the unsecured backend this allowed a profile namespace row when the system could not prove the payload was synthetic.

Required repair: treat unparseable or tax-id-missing user-profile payloads as unprovable under the unsecured backend and refuse without echoing identifiers.

W01P02-011 | LOW | Missing real CIF refusal regression coverage

The first S08 tests covered a real NIF refusal and synthetic CIF allowance, but did not prove that realistic company tax IDs are refused at the repository boundary.

Required repair: add a real CIF refusal regression and keep the refusal diagnostic identifier-free.

W01P02-012 | INFO | S08 repair applied for review findings

Repair changes made all public `SecureObjectRepository` methods call the session freshness guard, required mutating operations to reject active bucket sessions whose engine points at a different bucket database, made unsecured profile payload parsing fail closed when the tax-id fact cannot be proven synthetic, added real CIF and malformed-payload refusal tests, and added an active-session/no-session boundary test.

During repair the route guard exposed an existing switch-path bug: `override_settings(aeat_active_profile=...)` did not recompute `aeat_database_url`, so profile-switch writes could retain the prior bucket route. The switch/read helpers now bind the target active profile and target bucket database URL together, and the profile-activation event test now reads the bucket-local event catalogue explicitly.

Validation after repair: focused secure-object/master-key tests passed, profile lifecycle and taxpayer-type CLI tests passed, file-custody profile lifecycle tests passed, manifest IO tests passed, and scoped Ruff checks passed. A narrow S08 re-review is pending before closing the step.

W01P02-013 | HIGH | Mutating route guard still permits root fallback and outside-root databases

The first S08 repair still returned success for root fallback databases, non-bucket files under the storage root, and database paths outside the storage root. Mutating methods could therefore write with an active bucket session while the engine pointed somewhere other than that bucket's database.

Required repair: for non-synthetic active sessions, mutating methods must require the exact `<storage_root>/buckets/<bucket_id>/db/aeat.db` route and reject every other path.

W01P02-014 | MEDIUM | Quarantine mutation missed route matching

`quarantine_unreadable_rows()` creates a quarantine table, inserts rows, and deletes rows from `secure_objects`, but it only checked session freshness. It needed the same exact-route guard as other mutating methods.

Required repair: require matching active bucket route before quarantine mutations.

W01P02-015 | LOW | Missing empty-write and malformed-payload regression coverage

`save_many(())` returned before proving an active session, and S08 tests only covered one no-tax-id malformed profile payload. Malformed JSON and future-shaped profile payloads needed explicit fail-closed coverage.

Required repair: make empty batch writes prove session freshness, add malformed JSON and future-shaped profile payload tests, and add route mismatch tests for root fallback and quarantine.

W01P02-016 | INFO | S08 second repair applied and validated

Repair changes now make non-synthetic mutating secure-object operations require the exact active bucket database route. Root fallback, outside-root, and non-bucket database paths are rejected for active bucket mutations. Quarantine now uses the matching-route guard. Empty `save_many(())` proves an active session before returning.

The stricter route policy exposed a second settings-copy bug in wizard profile create/edit: a prebuilt settings override did not recompute `aeat_database_url` after writing the active pointer. Wizard persistence now binds `aeat_active_profile` and the profile bucket database URL together before opening the provider session.

Additional tests cover root fallback write refusal, quarantine route mismatch refusal, empty batch session requirement, malformed JSON profile payload refusal, future-shaped profile payload refusal, and real CIF refusal without identifier leakage.

Validation after second repair:

- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/test_profile_create_taxpayer_type_paths.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py -q`
- `uv run --no-sync ruff check` on touched S08 storage, wizard, and CLI files

W01P02-017 | INFO | S09-S10 explicit database route guard applied

The root active-gate now refuses guarded profile-bound mutation verbs when `classify_storage_route()` reports `EXPLICIT_DATABASE_URL`, matching the existing root-fallback refusal behavior. Bootstrap and recovery surfaces remain open through the existing bootstrap-exempt registry.

Regression tests now exercise both route classes through real entrypoint subprocess harnesses. The explicit database harness asserts route classification as `EXPLICIT_DATABASE_URL`, invokes guarded write verbs, checks for the explicit-route refusal, and verifies the explicit SQLite file was not created.

Validation:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_root_fallback_write_guard.py -q`
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py`
