---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: S208
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W09.P41.S208 — audit secure_sql.py + add isolated_sessionless_storage_root

## Outcome

`isolated_profile_storage_root` required architectural surgery before it could
serve as a drop-in for any test that (a) asserts `has_active_bucket_session() is
False`, or (b) exercises the CLI `profile create` path. Two distinct failure modes
were identified and resolved:

**Failure mode 1 — session leak**: The prior `EphemeralMasterKeyProvider` context
manager activated a `BucketSession`, breaking `has_active_bucket_session()` checks
in cold-start and repair tests.

**Failure mode 2 — key mismatch**: `profile create` calls `get_master_key_provider()`
which reads the `aeat_secret_store_backend` setting (defaults to `file`). The
`EphemeralMasterKeyProvider` session used a different in-memory key. Decryption
attempted with the file-backend key failed.

**Resolution**:

- Introduced `isolated_sessionless_storage_root` — a new helper in
  `src/aeat/tests/secure_sql.py` that provisions a temp storage root and
  disposes the engine WITHOUT starting any master-key session. For tests that
  must assert no active session.

- Rewrote `isolated_profile_storage_root` to configure the file backend with
  the dev-test passphrase (`aeat_secret_store_backend="file"`,
  `aeat_secret_store_dir`, `aeat_secret_passphrase`) and removed the
  `EphemeralMasterKeyProvider` wrapper entirely. The CLI `profile create` path
  now resolves a working provider without key mismatch.

- `test_cold_start_no_profile.py` migrated as S208 proof: 7/7 pass.

## Commits

- `cb51d03e7` — W09.P41.S208: add isolated_sessionless_storage_root + verify cold-start tests

## Files changed

- `src/aeat/tests/secure_sql.py` — added `isolated_sessionless_storage_root`; rewrote `isolated_profile_storage_root` to use file backend + passphrase
- `src/aeat/entrypoints/cli/test_cold_start_no_profile.py` — migrated to `isolated_sessionless_storage_root`
