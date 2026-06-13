---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S162'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s162-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S162`

Closed `AFR-060` for plaintext bucket manifest I/O.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py` against the `manifest-bucket` and `plain-file` scanner signals.
- Converted missing, unreadable, invalid, and missing-status manifest reads to localized `StorageValidationError` failures.
- Converted manifest write `OSError` failures to localized `StorageValidationError` failures and added debug-observable temporary-file cleanup.
- Preserved legacy/default master-key behavior by switching intentional missing-manifest fallbacks to the exported typed marker.
- Routed manifest I/O test file reads and writes through `UTF_8_ENCODING` instead of direct encoding literals.
- Added real filesystem tests for missing manifest reads and missing bucket-directory writes, asserting typed causes, locale keys, and path-redacted envelopes.
- Recorded broader pre-existing `_master_key.py` broad-exception debt under pending `AFR-075` / `W12.P26.S177`.
- Closed `S162` through `vaultspec-core vault plan step check` and updated `AFR-060` to closed.

## Outcome

`AFR-060` is closed as `manifest-discovery`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/master_key/_master_key.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, direct encoding literals, local secure-object marker construction, direct settings construction, or direct environment access in the reviewed bucket manifest I/O surface.

## Notes

No modelo export evidence or workbook parity behavior is implemented in this row. The new export ADR constraints remain applicable to later export rows; this row only governs local plaintext bucket manifest I/O.
