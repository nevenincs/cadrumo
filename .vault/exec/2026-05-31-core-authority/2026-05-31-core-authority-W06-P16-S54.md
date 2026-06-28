---
step_id: S54
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#core-authority"
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W06.P16.S54

## Summary

Extracted `BucketEventHistoryRepositoryProtocol` from `domain/buckets/_event_repository.py` to a new `domain/buckets/_protocols.py`. Moved all module-scope adapter imports (`SensitivityClass`, `Envelope`, `SecureObjectWrite`, `SecureObjectRepository`, `secure_object_repository_for_active_bucket`) behind `TYPE_CHECKING` guard with deferred local imports in `__init__` and all method bodies.

## Commit

`09febdc20` — feat(buckets): extract BucketEventHistoryRepositoryProtocol to _protocols.py (MIGRATE-003 W06.P16.S54)
