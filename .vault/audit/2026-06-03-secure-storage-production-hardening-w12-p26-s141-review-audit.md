---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S141]]'
---

# `secure-storage-production-hardening` `W12.P26.S141` Review

## S141-001 | PASS | Outbound storage exceptions derive from core AEAT bases

The outbound provider failure hierarchy is rooted in `OutboundStorageError`, which derives from `AeatError`. The public storage corruption exception derives from `CoreError`, which also derives from `AeatError`.

The module-level issue was documentation drift: `_errors.py` described every backend failure as an `OutboundStorageError`, but the real local sidecar corruption path intentionally raises `StorageCorruptionError`. That distinction is correct because sidecar schema corruption is an internal data-structure failure, not a remote-provider failure.

Resolution: the module docstring now states the split explicitly. Foundation tests now prove outbound leaves remain under `OutboundStorageError` and `AeatError`, and that `StorageCorruptionError` remains a `CoreError` outside the outbound provider hierarchy. Registry-code coverage includes every public leaf.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/adapters/outbound/storage/test_local.py -k "storage_error_hierarchy_unified or every_leaf_carries or corruption"` passed with 5 selected tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_errors.py src/aeat/adapters/outbound/storage/test_foundation.py` passed.
- Source scan found no direct `Settings()`, `PROJECT_ROOT`, `os.environ`, print/echo output, `# noqa`, pragma, `type: ignore`, `except Exception`, or `except BaseException` in the S141 files.

Disposition: close `AFR-039` as `remote-mirror`.
