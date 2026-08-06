---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-07-17'
body_hash: 'sha256:c9b00899871b5eec86046d2abb2a8a08b4c25cfeb91fda3c61306cdf64dc4fa4'
step_id: 'S205'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# consolidate UserProfileLifecycleRepository.__init__ and UserProfileSnapshotRepository.__init__ identical signatures into shared base class or factory

## Scope

- `Wave-1 drift sweep DUPLICATE finding`
- `src/aeat/application/user_profile/_repository.py`

## Description

Introduced `_BucketBoundRepository` base class in
`src/aeat/application/user_profile/_repository.py` that holds the
shared bucket-binding `__init__` logic. Both
`UserProfileLifecycleRepository` and
`UserProfileSnapshotRepository` now inherit from it; their
identical `__init__` bodies are deleted (the inherited one
validates `bucket_id`, raises `BucketValidationError` on blank, and
either accepts an injected `SecureObjectRepository` or builds one
via `_secure_objects_for_bucket`).

## Outcome

Real refactor. 14 repository tests
(`test_repository.py` 10 + `test_repository_anti_tautology.py` 1 +
`test_repository_roundtrip.py` 3) continue to pass after the
hoist. No behaviour change; the `bucket_id` / `objects` contract
is unchanged.

## Notes

W09-P41 Wave-1 drift sweep DUPLICATE finding closed.
