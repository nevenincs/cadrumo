---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S03
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P01.S03`

Exported `ProfileName` and `BucketId` from the profile domain
package.

- Modified: `src/aeat/domain/profile/__init__.py`

## Description

Added the import of `BucketId` and `ProfileName` from
`src/aeat/domain/profile/_constants.py` and inserted both names into
the package's `__all__` in alphabetical order alongside the existing
exports.

## Tests

Covered by the smoke import test in `P01.S10` / `S11` test contract
and verified by running `pytest src/aeat/domain/profile/`.
