---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S157]]'
---

# `secure-storage-production-hardening` `W12.P26.S157` Review

## S157-001 | PASS | Export header carries plaintext manifest metadata only

`src/aeat/adapters/persistence/storage/bucket/_export_header.py` defines `ExportArchiveHeader`, a strict frozen pydantic record for sealed bucket-export archive frontmatter. The record carries the bucket identifier, manifest digest, recovery-wrap presence flag, archive schema version, and creation timestamp.

The scanner's `manifest-bucket` signal is expected: the header references the bucket manifest digest so an archive can identify the manifest it seals. It does not carry NIF, financial ledger rows, secret bytes, wrapped DEK material, recovery wrap bytes, or secure-object payloads.

## S157-002 | PASS | Validation remains record-local and non-persistent

The module performs no filesystem IO, settings/env lookup, master-key access, archive writing, exception swallowing, or export transport work. Digest and timestamp validators are pure record guards.

The `ValueError` raises are pydantic field-validator signals; pydantic wraps them into `ValidationError`. They are not project-level runtime exceptions escaping the storage boundary and do not bypass the AEAT exception hierarchy for application errors.

S157 hardened the test surface to assert the shared strict/frozen contract directly: instances are immutable, `archive_schema_version` is not accepted as a string, and `recovery_wrap_present` is not accepted as an integer.

## S157-003 | FIXED BEFORE COMMIT | Manifest digest validation rejects sign and whitespace spellings

Review found that the validator used `int(value, 16)`, which accepts leading signs and surrounding whitespace even though the contract requires exactly lowercase SHA-256 hex.

Resolution: digest validation now checks every character against an explicit lowercase hex alphabet after the length check. Regression tests cover leading `+`, leading space, and trailing newline spellings.

## S157-004 | PASS | Export parity ADRs do not change this storage classification

The 2026-06-03 export/parity ADRs constrain modelo calculation/export evidence and workbook/fichero parity. This header belongs to bucket export packaging, not modelo workbook or fichero content. It remains a plaintext metadata exception/discovery surface for sealed bucket archives, while export content and evidence parity remain governed by the modelo export plans.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_export_header.py` passed with 16 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_export_header.py src/aeat/adapters/persistence/storage/bucket/test_export_header.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` reported `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` ok.
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.
- Plan state was reconciled after the CLI checked S157 but left `AFR-055` pending; the repaired state is `AFR-055`/`S157` closed and `AFR-056` through `AFR-058` / `S158` through `S160` pending.

Disposition: close `AFR-055` as `manifest-discovery`.
