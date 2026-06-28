---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S251'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s251-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S251`

Closed `AFR-149` for the review filter parser.

## Description

- Reviewed `src/aeat/application/review/_filter.py` as a typed filter parser boundary.
- Hardened `FilterParseError` so rendered messages and structured context do not echo operator-supplied filter values.
- Added `safe_token` for CLI recovery messages that need a key-only redacted token display.
- Updated ledger CLI filter parse handlers to pass the redacted token into localized output.
- Enrolled `review.filter.errors.parse_failed` through `python -m aeat.locales`.
- Added parser and translated-message regression coverage for redacted filter failures.
- Closed `S251` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-149` is closed as `plaintext-exception` disposition for the review filter surface. The filter parser remains storage-free and operates over strict typed models, while filter parse diagnostics no longer expose free-text search strings or imported identifiers in application or CLI error output.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/review/_errors.py src/aeat/application/review/_filter.py src/aeat/application/review/test_filter.py src/aeat/application/review/test_filter_helpers.py src/aeat/application/review/test_edit.py src/aeat/entrypoints/cli/_ledger.py`
- `uv run --no-sync pytest -q src/aeat/application/review/test_filter.py src/aeat/application/review/test_filter_helpers.py src/aeat/application/review/test_edit.py`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_ledger_list_filter.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

`FilterParseError.raw_token` remains available as an internal compatibility attribute. CLI rendering now uses `safe_token` so the public message preserves the failing key without exposing the supplied value.
