---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:dbf1afa210ccc4d3336b829d9bf135bcb669894851b0002e873c0c753814dbaf'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S250` Review

## S250-001 | HIGH | Edit parse errors rendered raw operator values

`EditParseError` previously formatted the full edit token into the exception message. Review edit tokens can contain document paths, references, and operator notes, so parse failures could expose plaintext user data in logs or CLI error envelopes. The error now uses `review.edit.errors.parse_failed`, carries only `reason` plus a key-only context, and omits the supplied value from `str(error)`.

## S250-002 | PASS | Parser remains storage-free

The retired module does not read or write files or instantiate storage repositories. It parses `--set KEY=VALUE` tokens into strict Pydantic models and returns typed `Path` objects without checking the filesystem; consuming use cases remain responsible for storage handling.

## S250-003 | PASS | Validation

- the historical check passed.
- the historical check passed with 100 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-148` as `plaintext-exception` with the rendered plaintext leak fixed.
