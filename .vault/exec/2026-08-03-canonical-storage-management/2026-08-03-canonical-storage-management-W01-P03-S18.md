---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:601405f10067ee32e115391a825d747eb8a7bb0ec71aaec99d63e5edcacca18c'
step_id: 'S18'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the bucket-layout and keystore members in the core taxonomy with fixed override policy and bucket-relative or keystore-relative scope, gated by a test asserting an operator override of a fixed member refuses

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Declare the bucket-layout and keystore members in the core taxonomy with fixed override policy and bucket-relative or keystore-relative scope.

## Outcome

Landed in commit `08c61859c0` (the same foundational commit as S01-S09). All ten bucket/keystore members declared with `override_policy=FIXED`.

## Notes

The gate (`test_bucket_and_keystore_layout_is_fixed_not_operator_overridable`) is structural only: it asserts `override_policy is FIXED` and `settings_field is None`, not a behavioural override-and-catch-refusal. There is no override seam to attempt through `Settings`/`override_settings` for a fixed member with no settings field, so a structural assertion is the correct shape — but the Step's "refuses" wording should be read as architectural absence-of-a-seam, not a caught exception.
