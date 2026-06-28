---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S162]]'
---

# `secure-storage-production-hardening` `W12.P26.S162` Review

## S162-001 | PASS | Manifest I/O failures now use the AEAT storage hierarchy

`src/aeat/adapters/persistence/storage/bucket/_manifest_io.py` no longer lets a missing manifest escape as `FileNotFoundError` from the public `read_manifest` boundary. Missing, unreadable, invalid, and missing-status manifests now raise `StorageValidationError`, which derives from the core AEAT error hierarchy.

The typed error carries `translated_message="errors.integrity.integrity_storage_bucket_validation"`, reusing the existing locale-covered bucket validation key. `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

## S162-002 | PASS | Manifest write failures are typed and path-redacted

`write_manifest` now wraps `OSError` from staging or replacing `manifest.toml` in `StorageValidationError` and removes any temporary manifest sibling when possible. Cleanup failures are logged at debug level by error type only, without logging the bucket root or local path.

Tests verify both missing-read and missing-write cases through real filesystem behavior. The error string and JSON envelope do not contain the temporary root path, and the original `FileNotFoundError` remains available as `__cause__` for diagnostics.

## S162-003 | PASS | Legacy/default missing-manifest callers remain explicit

The two master-key fallback callers that intentionally treated an absent manifest as "legacy/default" now check the exported `MISSING_BUCKET_MANIFEST_MESSAGE` marker on `StorageValidationError`. Malformed or unreadable manifests still re-raise, so the typed conversion does not broaden fallback behavior.

## S162-004 | OBSERVATION | Broader `_master_key.py` exception debt remains assigned to AFR-075

The hunk in `src/aeat/adapters/persistence/storage/master_key/_master_key.py` does not introduce broad catches, suppression, environment access, or monkeypatch patterns. A file-level hygiene scan still reports pre-existing broad exception/suppression patterns elsewhere in `_master_key.py`; that file is already tracked by `AFR-075` / `W12.P26.S177` for `bootstrap-custody`, so it should be cleared in that row rather than folded into the manifest I/O closure.

The reviewed bucket manifest I/O tests now route text reads and writes through `UTF_8_ENCODING`, so the touched test surface no longer carries direct encoding literals.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py` passed with 76 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/master_key/_master_key.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Scoped hunk review found no broad exception catch, suppression, direct environment access, direct settings construction, direct encoding literals, fake/stub test, monkeypatch, skip, xfail, or path-bearing error context introduced by this row.

Review-agent note: a reviewer subagent was unavailable in this session due the current usage limit, so the supervisor completed the same checklist locally.

Disposition: close `AFR-060` as `manifest-discovery`.
