---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S154'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s154-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S154`

Closed `AFR-052` for the secret materialisation plaintext-exception surface.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/blob_store/_materialisation.py` against the `master-key` and `plain-file` scanner signals.
- Retained materialisation as an explicit plaintext exception because some third-party consumers require a filesystem path, but kept the plaintext lifetime scoped to short-lived temp files or caller-owned cleanup.
- Replaced single-call `os.write()` with a bounded loop that writes until the complete secret payload reaches the already-opened secure tempfile descriptor.
- Added validation for materialised tempfile `prefix` and `suffix` values so callers cannot smuggle path separators or dot path tokens into the temp path shape.
- Added localized `StorageValidationError` context for invalid materialisation affixes and no-progress secure-tempfile writes.
- Replaced silent cleanup `FileNotFoundError` suppression with debug-level evidence for already-missing temp paths.
- Closed reviewer findings that write/setup failures could leave plaintext temp files behind before the cleanup scope was entered.
- Corrected explicit export cleanup so cleanup is marked complete only after unlink succeeds or the path is already missing.
- Added real materialisation/export tests for large payload integrity, unsafe affix rejection, debug cleanup evidence, and cleanup retry after unlink failure.
- Closed `W12.P26.S154` through `vaultspec-core vault plan step check`, aligned `AFR-052` to `closed`, and manually repaired adjacent S155-S157 checkbox drift introduced by the plan CLI.

## Outcome

`AFR-052` is closed as a `plaintext-exception`: secret bytes may be materialised only through the explicit temp-file API, with complete writes, path-shape validation, restrictive temp-file creation, and cleanup evidence.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py -k "materialise or export or sensitive_direct_write"` passed with 26 selected tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/blob_store/_materialisation.py src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local `Path("db://secure_objects")` construction, direct settings construction, or direct environment access.
- S154 re-review returned no findings after the write-failure cleanup and export cleanup retry fixes.

## Notes

The plan CLI again reported a successful close while mutating adjacent rows. The committed plan state is manually repaired: S154 is closed, while S155-S157 remain pending until their bucket-manifest steps execute.
