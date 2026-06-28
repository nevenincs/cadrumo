---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S160]]'
---

# `secure-storage-production-hardening` `W12.P26.S160` Review

## S160-001 | PASS | Lockfile plaintext is non-sensitive coordination state

`src/aeat/adapters/persistence/storage/bucket/_lockfile.py` writes only the current process PID to `<bucket-dir>/.lock`. It does not persist taxpayer identifiers, ledger rows, secret bytes, wrapped DEKs, recovery material, secure-object payloads, or modelo export content.

The `plain-file` signal is therefore accepted as coordination metadata. The file is created with mode `0o600` and `O_CREAT | O_EXCL | O_WRONLY`, so acquisition remains atomic and the plaintext surface is bounded to the PID holder marker.

## S160-002 | PASS | Silent lockfile degradation paths now emit diagnostics

PID read outcomes are explicit: missing, unreadable, invalid, or parsed integer. Malformed and empty PID files log debug before stale reclaim; unreadable PID files and denied liveness probes log debug and are treated as held rather than reclaimable; release and atexit missing-file races log debug instead of being hidden by `contextlib.suppress`.

The debug messages do not include the lockfile path or the bucket root.

## S160-003 | PASS | Incomplete lockfile creation is cleaned up

After `O_EXCL` creates a lockfile, PID writing must complete before acquisition is considered successful. PID write failures now remove the created lockfile before re-raising the original write failure. A close failure after PID write logs a redacted debug diagnostic, attempts cleanup, and propagates the close failure so callers do not proceed with ambiguous acquisition state.

Cleanup diagnostics include reason codes and exception types, not lockfile paths or bucket roots.

## S160-004 | PASS | Settings, errors, and tests follow project conventions

The poll interval is resolved through `load_settings()` rather than `Settings()` or direct environment access. A bucket-directory file collision raises `BucketValidationError` with redacted structured context and the existing bucket validation error envelope.

The tests exercise real filesystem and subprocess behavior. They do not use fakes, stubs, mocks, monkeypatching, skip, or xfail shortcuts.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_lockfile.py src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py` passed with 48 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_lockfile.py src/aeat/adapters/persistence/storage/bucket/test_lockfile.py src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.

Disposition: close `AFR-058` as `manifest-discovery`.
