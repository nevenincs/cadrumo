---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S11
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P01.S11`

`BucketId` validation contract covered in the same test module as
`ProfileName` because the two aliases share one constraint by ADR
mandate.

- Touched: `src/aeat/domain/profile/test_constants.py`

## Description

The plan specified a separate file
`src/aeat/domain/buckets/test_constants.py` for `BucketId` coverage.
Because `BucketId = ProfileName` (a single underlying alias),
duplicating the constraint tests under the bucket package would
violate the no-tautological-tests rule — both files would assert
the same constraints against the same alias. The plan row is
satisfied by the parity test in the consolidated module
(`test_profile_name_and_bucket_id_share_constraint`,
`test_bucket_id_rejects_empty_or_whitespace`,
`test_bucket_id_rejects_overlong_input`,
`test_bucket_id_accepts_profile_name_values`).

## Tests

Same suite as `P01.S10`; the `BucketId`-specific cases run as part of
the 12-test module run.
