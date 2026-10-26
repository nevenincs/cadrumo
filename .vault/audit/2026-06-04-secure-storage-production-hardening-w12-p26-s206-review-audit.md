---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:30bfcb0a0c6ba9b01bc62415e6781ecb73d6535a8c2671f60053fc61bbd26d3c'
related:
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

## S206-005 | FIXED | Intersecting wallet constants work is validated

Shared-worktree edits in the same core constants files added typed pre303
browser-action labels and TOML values used by the IVA compensation wallet and
Cl@ve Movil auth surfaces. The wallet representation helper was missing from
the implementation while tests imported it; the helper now validates the same
HTML guard used by the async browser path and accepts only the reviewed
own-name dispatcher shape.

## S206-006 | FIXED | Deprecated diagnostics locale leaves were removed

The locale gate surfaced stale `cli.diagnostics.profile` and
`cli.diagnostics.secure_objects` strings from the removed standalone
`src/aeat/diagnostics` CLI package. The leaves were removed through the
canonical `python -m aeat.locales remove` workflow followed by
`python -m aeat.locales scaffold` to prune empty namespace parents. The stale
inventory ratchet was removed from the retired test.

## S206-007 | PASS | Validation

- the historical check passed.
- the historical check passed with 21 tests.
- the historical check passed.
- the historical check passed with 33 selected tests.
- the historical check passed with 39 selected tests.
- the historical check passed with 125 selected tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S206
slice.

Disposition: close `AFR-104` as `plaintext-exception`.
