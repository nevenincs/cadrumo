---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S04
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P01.S04`

Exported `BucketId` from the bucket storage-layer domain package.

- Modified: `src/aeat/domain/buckets/__init__.py`

## Description

Added the import of `BucketId` from
`src/aeat/domain/buckets/_constants.py` and inserted the name into
the package's `__all__`, reordered alphabetically by `ruff --fix`.

## Tests

Covered indirectly by the existing `src/aeat/domain/buckets/`
test suite (passes after the change) and the new alias parity test.
