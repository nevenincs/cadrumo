---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:2bb603ee77aeedc1b356deaaa500abd968e8e1269afa36191c3174f8adf1371f'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S251` Review

## S251-001 | HIGH | Filter parse errors rendered raw operator values

`FilterParseError` previously formatted the full filter token into the exception message, and ledger CLI handlers passed `exc.raw_token` into localized output. Filter values can include free-text search strings and imported identifiers, so this could expose operator data in logs or terminal diagnostics. The error now uses `review.filter.errors.parse_failed`, carries only `reason` plus key-only context, and provides `safe_token` for redacted CLI output.

## S251-002 | PASS | Filter parser remains storage-free

The retired module does not read or write files, instantiate repositories, or resolve storage backends. It validates closed key catalogues and enum-bound values before the review queue or ledger query layers consume the typed spec.

## S251-003 | PASS | Validation

- the historical check passed.
- the historical check passed with 97 tests.
- the historical check passed with 9 tests and existing Click deprecation warnings.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-149` as `plaintext-exception` with the rendered plaintext leak fixed.
