---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S28'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Confirm the SQL secure_objects store is covered by the bucket-DEK rewrap rotation path and document or extend the rotation contract

## Scope

- `src/aeat/adapters/persistence/storage/_rotation.py`

## Description

- Document on `default_rotation_plan` the scope boundary: it covers only the
  master-key-encrypted `*.envelope.json` file consumers; the SQL `secure_objects`
  store is intentionally excluded.

## Outcome

Confirmed (not a gap): `secure_objects` payloads are encrypted under the per-bucket
DEK (the column layer resolves the active BucketSession DEK, not the master key),
and a custody change rewraps the DEK without changing its value, so the ciphertext
never needs re-encryption on master-key rotation. 24 rotation tests green.
Committed in `4c59248e1`.

## Notes

The file-envelope consumers and the SQL store coexist for some domains; the
master-key vs bucket-DEK key split is what determines rotation membership.
