---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S351'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-249` for `src/aeat/domain/manuals/_verify.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/manuals/_verify.py`

## Description

- Reconstructed the manual-verification exception from closeout commit `4523bb9108`.
- Confirmed verification evaluates already-loaded public corpus evidence in memory.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The manual verifier remains a justified plaintext exception; targeted validation passed 21 tests.

## Notes

The disposition covers no mutable profile-storage path.
