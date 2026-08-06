---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-07-17'
body_hash: 'sha256:0bd50fd0ec2253135e5be5f0bbfd340a26dcf51ba0c3d8572afc6a33d1e206e0'
step_id: 'S15'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

# Replace the resolved absolute source_path provenance with a relative filename or sha-only reference in the raw transaction model

## Scope

- `src/aeat/domain/transactions/_raw_transaction.py`

## Description

- Replace the `_resolve_source_path` validator (which called `.resolve()`) with
  `_basename_source_path`, storing only `value.name`; update the field and
  validator docstrings.

## Outcome

`RawProvenance.source_path` now persists a basename, not a host-specific absolute
path: no directory/username leak in the persisted or exported record, and no
cross-OS `.resolve()` mutation on rehydration. The live import file-read uses its
own path parameter, so file access is unaffected. 164 transaction/import/invoice
tests plus 18 ledger/workflow tests green. Committed in `d7b001fa6`.

## Notes

source_sha256 already carried the content identity, so no information is lost.
