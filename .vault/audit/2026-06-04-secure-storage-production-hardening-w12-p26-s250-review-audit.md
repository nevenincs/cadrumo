---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S250]]'
---

# `secure-storage-production-hardening` `W12.P26.S250` Review

## S250-001 | HIGH | Edit parse errors rendered raw operator values

`EditParseError` previously formatted the full edit token into the exception message. Review edit tokens can contain document paths, references, and operator notes, so parse failures could expose plaintext user data in logs or CLI error envelopes. The error now uses `review.edit.errors.parse_failed`, carries only `reason` plus a key-only context, and omits the supplied value from `str(error)`.

## S250-002 | PASS | Parser remains storage-free

`src/aeat/application/review/_edit.py` does not read or write files or instantiate storage repositories. It parses `--set KEY=VALUE` tokens into strict Pydantic models and returns typed `Path` objects without checking the filesystem; consuming use cases remain responsible for storage handling.

## S250-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/review/_errors.py src/aeat/application/review/_edit.py src/aeat/application/review/test_edit.py src/aeat/application/review/test_edit_helpers.py src/aeat/application/review/test_edit_iva_rate_boundary.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/review/test_edit.py src/aeat/application/review/test_edit_helpers.py src/aeat/application/review/test_edit_iva_rate_boundary.py` passed with 100 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-148` as `plaintext-exception` with the rendered plaintext leak fixed.
