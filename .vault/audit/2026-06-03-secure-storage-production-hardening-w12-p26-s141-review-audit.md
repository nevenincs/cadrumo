---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-10-03'
body_hash: 'sha256:39d1e5e0970abe7a02b42226a6d59b5df5953a82abd2444ccbe7bcd510213f59'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S141` Review

## S141-001 | PASS | Outbound storage exceptions derive from core AEAT bases

The outbound provider failure hierarchy is rooted in `OutboundStorageError`, which derives from `AeatError`. The public storage corruption exception derives from `CoreError`, which also derives from `AeatError`.

The module-level issue was documentation drift: `_errors.py` described every backend failure as an `OutboundStorageError`, but the real local sidecar corruption path intentionally raises `StorageCorruptionError`. That distinction is correct because sidecar schema corruption is an internal data-structure failure, not a remote-provider failure.

Resolution: the module docstring now states the split explicitly. Foundation tests now prove outbound leaves remain under `OutboundStorageError` and `AeatError`, and that `StorageCorruptionError` remains a `CoreError` outside the outbound provider hierarchy. Registry-code coverage includes every public leaf.

Validation:

- the focused test run passed with 5 selected tests.
- the focused test run passed.
- Source scan found no direct `Settings()`, `PROJECT_ROOT`, `os.environ`, print/echo output, `# noqa`, pragma, `type: ignore`, `except Exception`, or `except BaseException` in the S141 files.

Disposition: close `AFR-039` as `remote-mirror`.
