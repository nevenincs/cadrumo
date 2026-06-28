---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S181'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s181-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S181`

Closed `AFR-079` for the master-key zeroisation primitive.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/_zeroise.py` and its tests against the `master-key` bootstrap-custody contract.
- Enrolled invalid zeroise input failures in the registered `MasterKeyTypeError` locale key instead of a raw hand-built type error message.
- Added structured redacted context carrying only the received type name for invalid inputs.
- Extended real-behavior zeroise tests to assert the typed exception, translated message key, structured context, and absence of supplied secret text in the rendered message.
- Closed `AFR-079` and `W12.P26.S181`.

## Outcome

`AFR-079` is closed. The zeroise primitive still wipes mutable `bytearray` buffers in place, and invalid callers now receive a central storage exception carrying `errors.internal.internal_master_key_type`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_zeroise.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py src/aeat/adapters/persistence/storage/master_key/test_cluster_envelopes.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_zeroise.py src/aeat/adapters/persistence/storage/master_key/test_zeroise.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The primitive remains honest best-effort Python zeroisation: it clears the canonical `bytearray` buffer but cannot revoke transient immutable `bytes` copies that callers may have materialised.
