---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S09'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Re-save every carried secure object through the substrate save path under the recipient DEK in deserialize_profile_bundle

## Scope

- `src/aeat/application/user_profile/_bundle.py`

## Description

- Restore every carried secure-object row by saving it through the raw secure-object repository in the target bucket.
- Carry and restore natural object keys, not source-bucket HMAC lookup digests.
- Preserve classification, schema version, timestamp, and decrypted payload bytes.
- Harden imports to source modules for the restore path.

## Outcome

- Complete. Carried rows are re-digested and re-encrypted under the recipient bucket DEK.
- Verified by sealed archive recovery tests and the custody store matrix noted in the audit closeout.

## Notes

- The audit records the key correction: source-bucket HMAC lookup digests are not portable across DEKs, so natural object keys are the authority for recovery.
