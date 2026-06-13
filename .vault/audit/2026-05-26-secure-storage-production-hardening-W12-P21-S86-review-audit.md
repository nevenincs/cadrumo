---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P21-S86]]'
---



# `secure-storage-production-hardening` Code Review


S86-001 | HIGH | SQL secure-object read/list APIs still bypass active-bucket route matching
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:249` makes route validation optional through `require_matching_route`, but only write/existence/quarantine paths pass `require_matching_route=True`. Read and enumeration APIs still call `_check_session_freshness()` without route matching: `iter_all_records_raw` at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:348`, `list_namespaces` at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:397`, `probe_namespace_integrity` at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:526`, `list_keys` at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:561`, `iter_records_with_failures` at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:622`, `load` at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:705`, and `peek_metadata` at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:890`. This leaves raw or injected `SecureObjectRepository(engine=...)` readers able to inspect/decrypt against a root-fallback, explicit, or mismatched SQLite route as long as any active session exists. The S86 route-guard tests cover mismatched/root-fallback writes and quarantine only (`src/aeat/adapters/persistence/storage/sql/test_secure_objects.py:265`, `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py:296`, `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py:325`), so the read-side bypass is not covered.

S86-002 | HIGH | EphemeralMasterKeyProvider still synthesizes an `ephemeral` bucket session when no active profile resolves
`src/aeat/adapters/persistence/storage/master_key/_master_key.py:983` sets `bucket_id = resolve_active_bucket_id() or "ephemeral"` before opening the test bucket session. That improves active-profile tests when `aeat_active_profile` is set, but it retains a synthetic bucket fallback when no active profile exists. Combined with direct SQL construction under a matching `buckets/ephemeral/db/aeat.db` path, this still allows non-runtime secure-object code to open a session and satisfy route matching without an operator-selected active profile. This conflicts with the S86 closeout claim that synthetic `ephemeral` route bypasses were removed from runtime/sql matching.

S86-001-RESOLUTION | RESOLVED | Secure-object read/list route guard now matches write guard
`src/aeat/adapters/persistence/storage/sql/secure_objects.py` now defaults `_check_session_freshness()` to `require_matching_route=True`, so read, list, metadata, raw iteration, and integrity probe callers inherit active-bucket SQL route validation unless a future caller explicitly weakens that contract. `src/aeat/adapters/persistence/storage/test_runtime.py` adds `test_secure_object_load_rejects_mismatched_route`, which constructs a real mismatched bucket engine under an active `bucket-a` session and verifies `load()` fails before reading.

S86-002-RESOLUTION | RESOLVED | Ephemeral test provider no longer creates a synthetic bucket
`src/aeat/adapters/persistence/storage/master_key/_master_key.py` now raises `NoActiveBucketError` when `EphemeralMasterKeyProvider.__enter__()` cannot resolve an active bucket id. `src/aeat/adapters/persistence/storage/test_runtime.py` adds `test_ephemeral_master_key_provider_requires_active_profile`, proving the provider refuses to synthesize `ephemeral` without an active profile.

S86-REREVIEW-001 | NO FINDINGS | Final re-review confirms S86-001 and S86-002 are resolved
Re-reviewed the S86-001 and S86-002 fixes after the follow-up changes. `src/aeat/adapters/persistence/storage/sql/secure_objects.py` now defaults `_check_session_freshness()` to `require_matching_route=True`, and targeted scans found no explicit `require_matching_route=False` override. The read/list callers that still invoke `_check_session_freshness()` without arguments now inherit route matching. `src/aeat/adapters/persistence/storage/master_key/_master_key.py` now resolves the active bucket id and raises `NoActiveBucketError` instead of falling back to `"ephemeral"`; targeted scans found no remaining `resolve_active_bucket_id() or "ephemeral"` or `bucket_id="ephemeral"` fallback in the reviewed storage/profile/outbound scope. Validation run: `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime.py -q` passed with 18 tests, including `test_secure_object_load_rejects_mismatched_route` and `test_ephemeral_master_key_provider_requires_active_profile`. `git diff --check` over the reviewed S86 files and audit file passed.
