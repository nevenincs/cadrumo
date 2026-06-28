---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S250'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s250-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S250`

Closed `AFR-148` for the review edit parser.

## Description

- Reviewed `src/aeat/application/review/_edit.py` as a plaintext-exception parser boundary.
- Hardened `EditParseError` so rendered messages and structured context do not echo operator-supplied edit values.
- Preserved the stable `reason` contract and key-only diagnostic context for CLI handling.
- Enrolled `review.edit.errors.parse_failed` through `python -m aeat.locales`.
- Added real parser/spec regression coverage for redacted edit parse failures.
- Closed `S250` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-148` is closed as `plaintext-exception`. Review edit parsing remains an in-memory typed parser with no direct storage IO, while parse-failure envelopes now avoid rendering sensitive values such as document paths, references, or operator comments.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/review/_errors.py src/aeat/application/review/_edit.py src/aeat/application/review/test_edit.py src/aeat/application/review/test_edit_helpers.py src/aeat/application/review/test_edit_iva_rate_boundary.py`
- `uv run --no-sync pytest -q src/aeat/application/review/test_edit.py src/aeat/application/review/test_edit_helpers.py src/aeat/application/review/test_edit_iva_rate_boundary.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

`EditParseError.raw_token` remains available as an internal compatibility attribute. It is intentionally excluded from the default error message and context because values can carry file paths or operator notes.
