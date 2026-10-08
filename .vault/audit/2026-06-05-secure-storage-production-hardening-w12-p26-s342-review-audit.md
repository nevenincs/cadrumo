---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-10-03'
body_hash: 'sha256:acd166f9a2d5915fc6dd6c8de6d3cf93c16dacbf9d1e5bdae2ee81c8567b6c70'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S342` Review

## S342-001 | PASS | Invoice models are manifest records, not persistence authorities

The retired module defined strict frozen invoice records, catalogue
mapping behavior, stable identity derivation, and validation. It performs no file IO,
secure-object write, active-profile lookup, remote provider call, settings resolution,
or environment access. The adjacent `InvoiceCatalogueRepository` remains the encrypted
SQL secure-object persistence boundary for the invoice catalogue, so `AFR-240` closes
as `manifest-discovery`.

## S342-002 | PASS | Validation failures now stay under the invoice-domain exception boundary

Date parser and enum conversion failures are wrapped in `InvoiceValidationError`
before crossing the pydantic model boundary. This removes the prior raw `TypeError`
escape for non-date `issued_at` inputs and prevents enum `ValueError` from becoming
the authored domain failure for malformed invoice payloads.

## S342-003 | PASS | Export and parity ADRs do not broaden this slice

The Google OAuth taxonomy and two-way ADRs split operator-facing invoice export and
reverse-merge work into purchase-invoice-evidence, payable-invoice, and
collectible-invoice source kinds. The calc-sheets parity ADR owns modelo calculation
Sheets behavior. S342 does not add export, Drive mirror, Sheets pull, reverse-merge, or
plaintext exception behavior.

## S342-004 | PASS | Validation

- the historical check passed.
- the historical check passed with 34 tests.
- the historical check passed with 54 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-rag search "invoice models manifest bucket InvoiceCatalogue pydantic strict frozen secure object repository invoice catalogue no plaintext file" --type code --port 8766 --max-results 8` returned `_models.py` and `_repository.py` as the relevant split.
- `uv run --no-sync vaultspec-rag search "InvoiceCatalogueRepository secure object financial classification invoice models manifest discovery active profile bucket" --type code --port 8766 --max-results 8` returned the secure-object repository and source-resolver surfaces.

Reviewer note: no critical, high, medium, or low storage-routing findings remain for
the S342 slice.

Disposition: close `AFR-240` as `manifest-discovery`.
