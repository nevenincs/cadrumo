---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:3b80d10d436532120c4a39c3a127dc5c441fa3c508a174dbeb2a8134fe64ed97'
step_id: 'S26'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Correct WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH to 155 by including the missing outbound namespace segment (ledger_transaction, a real BucketEventObjectType value with no enforced length cap), fix the anti-tautology guard in test_paths.py to recompute the namespace-inclusive shape with a positive control proving it catches the dropped segment, and correct the docstring's citation of the superseded _namespace_registry module to STORAGE_NAMESPACE_REGISTRY

## Scope

- `src/cadrumo/core/paths.py`
- `src/cadrumo/core/tests/test_paths.py`

## Description

## Outcome

Landed in `531db72902` ("fix(core): correct the Windows worst-case path suffix to include the outbound namespace (S26)"), confirmed at HEAD. `WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH` in `src/cadrumo/core/paths.py:131-141` is now `len(...)` over a literal that includes `"ledger_transaction"` (the longest real `BucketEventObjectType` value, no enforced length cap) between the bucket and blob segments — 155 characters, not the prior 136. The anti-tautology guard landed as two tests in `test_paths.py`: `test_windows_worst_case_suffix_covers_the_real_bucket_layout_shape` (line 259) and `test_windows_worst_case_suffix_guard_catches_a_dropped_namespace_segment` (line 309, the positive control proving the guard reds when the namespace segment is dropped). The docstring's stale citation of `_namespace_registry` is corrected to `STORAGE_NAMESPACE_REGISTRY` (`paths.py:106`).

## Notes
