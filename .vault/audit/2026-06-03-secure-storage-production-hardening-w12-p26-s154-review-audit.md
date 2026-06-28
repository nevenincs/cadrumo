---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S154]]'
---

# `secure-storage-production-hardening` `W12.P26.S154` Review

## S154-001 | PASS | Plaintext exception is explicit and bounded

`materialise_secret()` and `export_to_temp_path()` still materialise decrypted secret bytes only because downstream consumers require a real path. The helpers create private temp files through `mkstemp`, write through the returned descriptor, and either unlink on context exit or return an explicit cleanup callback.

## S154-002 | FIXED BEFORE COMMIT | Secure tempfile writes now handle short writes

`_write_bytes_secure_fd()` previously called `os.write()` once. Low-level writes return the number of bytes written, so a single call is not a durable complete-write contract.

Resolution: `_write_bytes_secure_fd()` now loops over a `memoryview` until all bytes are written and raises localized `StorageValidationError` if a write makes no progress. A real large-payload materialisation test verifies the full payload is read back.

## S154-003 | FIXED BEFORE COMMIT | Tempfile affixes cannot reshape paths

The helper accepted caller-supplied `prefix` and `suffix` values directly into `tempfile.mkstemp()`.

Resolution: prefix and suffix values are validated before secret lookup and temp-file creation. Separators, NUL bytes, and dot path tokens raise localized `StorageValidationError` with structured context. Real context-managed and explicit-export tests cover the rejection path.

## S154-004 | FIXED BEFORE COMMIT | Cleanup misses are no longer silent

Cleanup previously used silent `FileNotFoundError` suppression. That made idempotent cleanup safe but invisible when another process or earlier caller removed the temp file.

Resolution: already-missing temp paths now emit debug-level evidence. Real tests exercise both context-managed and explicit cleanup misses.

## S154-005 | FIXED BEFORE COMMIT | Write failures unlink plaintext temp files

Review found that write/setup failures before the context or cleanup callback was returned could leave partially written plaintext temp files behind.

Resolution: temp-file creation is now centralized. Any failure while writing or closing the descriptor before handoff closes the descriptor when possible, unlinks the materialised temp path, and re-raises the original failure.

## S154-006 | FIXED BEFORE COMMIT | Explicit cleanup retry is preserved after unlink errors

Review found that `export_to_temp_path()` marked cleanup complete before `Path.unlink()` succeeded. A real unlink failure could therefore prevent a later cleanup retry from removing plaintext.

Resolution: cleanup now marks completion only after unlink succeeds or the path is already missing. A real filesystem test replaces the exported file path with a directory, verifies cleanup raises, removes the directory, and verifies a later cleanup call still completes.

## S154-007 | PASS | Plan state matches the AFR register

The plan CLI again mutated adjacent rows while reporting success. The plan has been repaired so `AFR-052` / `W12.P26.S154` are closed and `AFR-053` through `AFR-055` / `W12.P26.S155` through `W12.P26.S157` remain pending.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py -k "materialise or export or sensitive_direct_write"` passed with 26 selected tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/blob_store/_materialisation.py src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local `Path("db://secure_objects")` construction, direct settings construction, or direct environment access.
- Final S154 code review returned no findings. Residual risk is limited to direct OS write-failure injection being covered by inspection rather than patched fault injection, consistent with the no fake/monkeypatch test constraint.

Disposition: close `AFR-052` as `plaintext-exception`.
