---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-07-17'
body_hash: 'sha256:fbff9393d4922e7ed81029eaa6515330225767903d0712e2dfb4dc3de492c6c3'
step_id: 'S03'
related:
  - "[[2026-06-09-codebase-performance-optimization-plan]]"
---

# Add tests verifying registry validated cache loading speed and modification invalidation

## Scope

- `src/aeat/domain/calculations/registry/tests/test_authority.py`

## Description

- Add `test_authority_uses_validation_cache_and_invalidates` unit/integration test.

## Outcome

- Done. The test runs successfully in under 1 second, verifying full cache check and invalidation correctness.

## Notes
