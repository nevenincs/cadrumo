---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:ebf4b067dc2fea2bb96b9fb5adf5e3c6342d49df6f0f0b4139f97773a0eac2d1'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S214` Review

## S214-001 | PASS | Plaintext is limited to operator import input

`_importing.py` reads CSV/JSON from the path supplied to the import command.
That source file is an explicit operator input, not an application persistence
backend. The module does not create local catalogue JSON files or write parsed
invoice rows to plaintext storage.

## S214-002 | PASS | Durable invoice state uses secure runtime storage

Non-dry-run imports load and save through `InvoiceCatalogueRepository`. The
repository resolves the active bucket, obtains the runtime-created secure-object
repository, and stores the catalogue as FINANCIAL secure-object payloads.

## S214-003 | FIXED | Import parse/read failures now use project error surfaces

Malformed JSON, invalid JSON shape, non-decimal flat `base_total`, invalid
invoice kind, and import file read failures now raise localized
`InvoiceValidationError` instances. The file-read failure path logs a debug
record with the file name and exception type, then raises from the original
`OSError`.

## S214-004 | PASS | Validation

- the historical check passed.
- the historical check passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for S214.

Disposition: close `AFR-112` as `plaintext-exception`.
