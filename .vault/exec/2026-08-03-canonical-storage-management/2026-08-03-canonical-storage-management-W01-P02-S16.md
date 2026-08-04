---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:3bea710712ca3c4f434935cbf7c634956a1c73d9a1398c0c56fd484b927374b0'
step_id: 'S16'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add the missing root permission-bits test asserting the mode after ensure_storage_tree, with a positive control proving the assertion fails when the hardening is removed

## Scope

- `src/cadrumo/core/tests/test_ensure_storage_tree.py`

## Description

- Add the missing root permission-bits test asserting the mode after `ensure_storage_tree`, with a positive control proving the assertion fails when the hardening is removed.

## Outcome

Landed in commit `ceaee35e78` as `test_the_root_is_restricted_to_its_owner` (genuinely new — confirmed absent before this commit), asserting `stat.S_IMODE(root.stat().st_mode) == 0o700` with a positive control (`root.chmod(0o755)` then re-asserting the mode differs, guarding against a platform that accepts `chmod` without applying it).

## Notes

Code and gate exist, but per W05.P21.S81 this test's assertions have not yet actually executed on a real POSIX host — that verification remains separately open and is not a gap in this Step.
