---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P14.S49'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P14.S49 - Review storage manifest and KDF schema overlap

Scope: Reduce duplicated KDF salt codec and length checks between the bucket
manifest KDF record and the canonical master-key KDF record.

## Description

- Add `_kdf_salt.py` as the storage-local salt codec and length helper.
- Route `ManifestKdfParams` and `KdfParams` salt validation, serialization, and
  deserialization through the shared helper.
- Add direct tests for the helper plus existing manifest/KDF round-trip tests.

## Outcome

The two storage KDF parameter records now share the repeated 16-byte salt
length contract and base64 codec while preserving their distinct pydantic
models and error surfaces.

## Notes

`just audit-duplication` no longer reports the storage manifest/KDF parameter
clone. Residual clone groups belong to later W04.P14 rows or separate slices.

Follow-up test hardening adds direct coverage for `_kdf_salt.py`, including
salt byte round-trip behavior and configured `StorageValidationError`
propagation.
