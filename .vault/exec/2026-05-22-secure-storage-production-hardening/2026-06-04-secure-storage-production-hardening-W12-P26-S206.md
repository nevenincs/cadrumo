---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
step_id: 'S206'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s206-review-audit]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
---

# `secure-storage-production-hardening` `W12.P26.S206`

Closed `AFR-104` for application tabular export serialization.

## Description

- Reviewed `src/aeat/application/export/_tabular.py` against the
  `plaintext-exception` classification for caller-directed export payloads.
- Regrounded the row against the 2026-06-03 modelo export evidence and workbook
  parity ADRs to avoid claiming modelo workbook, evidence, or official-layout
  parity from this generic serializer slice.
- Replaced the remaining bare SHA-256 validation `ValueError` with the existing
  core-derived `ExportFieldError` and localized refused-export-field key.
- Added a real XLSX readback test that loads the serialized workbook bytes and
  asserts row content plus returned metadata.
- Closed the plan step through the vaultspec CLI and aligned the AFR register
  entry with the recorded closure.

## Outcome

`AFR-104` is closed as a bounded plaintext exception. The module remains pure
in-memory serialization with no direct storage, settings, environment, active
profile, SQL, or secure-object repository access. Export validation failures now
carry the project export exception in the pydantic validation context instead of
a naked standard-library validation error.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/export/_tabular.py src/aeat/application/export/test_tabular.py`
- `uv run --no-sync pytest src/aeat/application/export/test_tabular.py -q`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The XLSX bytes are still an explicit operator export payload, not secure
persistence. No production file writes, direct `SecureObjectRepository`
construction, naked environment access, silent exception swallowing, raw
user-facing error string, `noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail,
or tautological test was introduced.
