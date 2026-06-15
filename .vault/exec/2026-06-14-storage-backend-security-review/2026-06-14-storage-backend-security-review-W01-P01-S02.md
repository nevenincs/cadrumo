---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S02'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Add a strict export then import roundtrip test over the Argon2id-sealed archive with a non-default passphrase

## Scope

- `src/aeat/application/bucket_maintenance/tests/`

## Description

- Add `test_recovery_wrap_member_records_argon2id_password_kdf` (asserts the
  member declares `argon2id` with real cost params, not HKDF) and
  `test_import_recovery_archive_rejects_wrong_passphrase` (wrong passphrase fails
  closed).

## Outcome

The Argon2id seal is asserted directly, and the existing
`test_import_recovery_archive_provisions_profile_in_fresh_root` covers the full
seal->unseal roundtrip with a non-default passphrase. 6 import/export tests green.
Committed in `d8abf5673`.

## Notes

None.
