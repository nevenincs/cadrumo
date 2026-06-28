---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S02
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P01.S02`

Introduced the `BucketId` typed alias as a storage-layer-facing
re-export of `ProfileName`, in line with the May-14 ADR's 1:1
profile / bucket cardinality mandate.

- Created: `src/aeat/domain/buckets/_constants.py`
- Modified: `src/aeat/domain/buckets/_event.py`

## Description

`BucketId` is a `TypeAlias` for `ProfileName` so the two names share
one constraint by construction. The historical module-private
`_BucketId` alias in `src/aeat/domain/buckets/_event.py` is removed
and replaced by a public import of the shared alias under the same
private rebinding, preserving callsite behaviour.

## Tests

Covered by `P01.S11` test contract in
`src/aeat/domain/profile/test_constants.py` (the alias parity check
covers `BucketId` since it shares the underlying constraint).
