---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S15
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P02.S15`

`register_active_profile` and `select_profile` now write the
plaintext active-profile pointer file on success, so a successful
orchestration call leaves the on-disk state self-consistent: the
next process invocation resolves the active profile from the
pointer file before any encrypted state row needs to load.

- Modified: `src/aeat/application/user_profile/_orchestration.py`

## Description

A new helper `_write_active_profile_pointer(bucket_id)` constructs
a `BucketPointer(bucket_id=..., schema_version=1)` and writes it
atomically via `write_pointer(settings.aeat_local_storage_root, ...)`.
The helper is called at the tail of both `register_active_profile`
and `select_profile`, after the secure-DB save / read succeeds and
the state mutation is composed.

The 1:1 bucket-id / profile-name convention (`bucket_id == profile_id`
documented in the orchestration module header) means the pointer
carries the same string the operator sees as the profile name.

## Tests

Covered by the 49-test pass in S13 (`test_orchestration.py` exercises
`register_active_profile` and `select_profile` end-to-end with a
real temporary AEAT root, so the pointer file gets written and
roundtripped without explicit assertion). The dedicated
"register writes pointer" assertion lands in P02.S24.
