---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S206]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
---

# `secure-storage-production-hardening` `W12.P26.S206` Review

## S206-001 | PASS | Tabular export is a bounded plaintext exception

`serialize_tabular_rows()` returns bytes plus integrity metadata to the caller.
It does not read or write paths, construct storage repositories, inspect active
profiles, open SQL routes, or persist side-store state. The plain-file signal is
therefore the caller-directed export payload, not default sensitive persistence.

## S206-002 | FIXED | Digest validation now uses the export error hierarchy

`TabularExportResult` no longer raises a bare digest `ValueError` for malformed
SHA-256 values. The digest validator now raises `ExportFieldError` with the
registered `errors.refused.refused_export_field` message key and structured
`sha256_invalid` reason. Pydantic wraps that exception in its validation error,
following the existing domain-error-in-`ctx.error` convention used elsewhere in
the codebase.

## S206-003 | PASS | XLSX payload shape is pinned by real readback

The XLSX branch is covered by a real openpyxl readback test. The test loads the
generated workbook bytes, asserts the header and rows survive, and verifies the
returned media type, extension, byte size, and SHA-256 metadata. No file-system
write, fake workbook object, monkeypatch, skip, or xfail is used.

## S206-004 | PASS | Export parity ADRs do not widen this row

The 2026-06-03 evidence/workbook parity ADRs were reviewed before closure. This
row covers only the generic application tabular serializer. It does not build
modelo calculation workbooks, the `Evidencia` surface, online/offline workbook
parity, visual styling facets, official-layout parity gates, or BOE fichero
byte-shape exports. Those remain owned by the modelo export parity workstreams.

## S206-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/export/_tabular.py src/aeat/application/export/test_tabular.py` passed.
- `uv run --no-sync pytest src/aeat/application/export/test_tabular.py -q` passed with 21 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S206
slice.

Disposition: close `AFR-104` as `plaintext-exception`.
