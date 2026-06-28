---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S45'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w06-p11-s45-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S45`

Added adverse-condition coverage for bucket session activation failures.

## Description

- Added locked-session coverage proving active master-key reads refuse with
  `BucketLockedError`.
- Added expired-session coverage proving active reads seal the session before
  refusing.
- Added wrong-passphrase activation coverage proving file-backed provider
  activation fails with `MasterKeyPassphraseMismatchError` without opening or
  leaking an active bucket session.
- Added torn-manifest activation coverage proving malformed bucket manifests
  fail at the strict read boundary with `StorageValidationError` before opening
  a session.
- Kept settings centralized through `Settings` and `override_settings`.

## Outcome

`W06.P11.S45` now covers locked, expired, wrong-passphrase, and torn-manifest
session states with real production storage objects and typed AEAT storage
exceptions.

Modified files:

- `src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py`

Review audit:

- `2026-06-02-secure-storage-production-hardening-W06-P11-S45-review`

Validation:

- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py -q`
- `git diff --check -- src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py`

## Notes

Mandatory review found no HIGH or CRITICAL findings and no remediation
findings. The broader lint run including `bucket/test_manifest_io.py` still
surfaces a pre-existing import-order warning in that untouched file, so the
S45 ruff gate was scoped to the new test module and directly related
master-key tests.
