---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S251]]'
---

# `secure-storage-production-hardening` `W12.P26.S251` Review

## S251-001 | HIGH | Filter parse errors rendered raw operator values

`FilterParseError` previously formatted the full filter token into the exception message, and ledger CLI handlers passed `exc.raw_token` into localized output. Filter values can include free-text search strings and imported identifiers, so this could expose operator data in logs or terminal diagnostics. The error now uses `review.filter.errors.parse_failed`, carries only `reason` plus key-only context, and provides `safe_token` for redacted CLI output.

## S251-002 | PASS | Filter parser remains storage-free

`src/aeat/application/review/_filter.py` does not read or write files, instantiate repositories, or resolve storage backends. It validates closed key catalogues and enum-bound values before the review queue or ledger query layers consume the typed spec.

## S251-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/review/_errors.py src/aeat/application/review/_filter.py src/aeat/application/review/test_filter.py src/aeat/application/review/test_filter_helpers.py src/aeat/application/review/test_edit.py src/aeat/entrypoints/cli/_ledger.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/review/test_filter.py src/aeat/application/review/test_filter_helpers.py src/aeat/application/review/test_edit.py` passed with 97 tests.
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_ledger_list_filter.py` passed with 9 tests and existing Click deprecation warnings.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-149` as `plaintext-exception` with the rendered plaintext leak fixed.
