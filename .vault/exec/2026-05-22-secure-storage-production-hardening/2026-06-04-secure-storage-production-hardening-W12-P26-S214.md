---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S214'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s214-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S214`

Closed `AFR-112` for invoice importing.

## Description

- Reviewed `src/aeat/application/invoices/_importing.py` against the
  `plaintext-exception` classification.
- Verified the only plaintext file read is the operator-supplied CSV/JSON import
  source; merged invoice catalogue writes go through
  `InvoiceCatalogueRepository`.
- Verified `InvoiceCatalogueRepository` persists the catalogue as FINANCIAL
  secure objects through the active bucket runtime.
- Converted import file read failures, malformed JSON, invalid JSON shape,
  invalid flat `base_total`, and invalid invoice kind failures into localized
  `InvoiceValidationError` surfaces.
- Added real-behavior tests for the localized parse/read refusals.
- Set invoice importing locale leaves through `python -m aeat.locales`.

## Outcome

`AFR-112` is closed as `plaintext-exception`. The import file itself remains
plaintext by operator intent, while any durable invoice catalogue state is
persisted through secure runtime storage.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/application/invoices/test_importing.py src/aeat/application/invoices/test_importing_helpers.py`
- `uv run --no-sync ruff check src/aeat/application/invoices/_importing.py src/aeat/application/invoices/test_importing.py src/aeat/application/invoices/test_importing_helpers.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No direct production `SecureObjectRepository` construction, naked environment
access, settings bypass, silent exception swallowing, `noqa`, `pragma`,
monkeypatch, fake, mock, skip, xfail, or tautological test was introduced.
File-read failures are debug-logged with the file name and error type only.
