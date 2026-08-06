---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-07-17'
body_hash: 'sha256:15607aa9530670f01cebeb13fb7f1df97e3a0c107c84966c20c4dacf49b9a2b6'
step_id: 'S09'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

# Add a row-substitution and corrupted-hash anti-tautology test proving read-time refusal

## Scope

- `src/aeat/adapters/persistence/storage/sql/tests/`

## Description

- Add `test_secure_object_row_substitution_fails_closed`: save two rows, copy the
  first row's ciphertext into the second via raw sqlite3, and assert
  `repo.load` raises `DecryptionError` (the substituted ciphertext fails the AEAD
  tag under the target row's identity).

## Outcome

The anti-tautology proof for H3's row-substitution gap is in place and green.
Committed in `19d1ac86e`. The pre-existing CANARY test continues to prove the
payload is ciphertext at rest.

## Notes

`load` raises on the AAD mismatch; the fail-closed `list_records` path reports the
row unreadable. The test uses `load` for an unambiguous assertion.
