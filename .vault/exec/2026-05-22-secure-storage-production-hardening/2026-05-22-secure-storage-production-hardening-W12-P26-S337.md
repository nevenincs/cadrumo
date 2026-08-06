---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:8dfd5b5a7218307f109e9f994c4d41eecfb955a7e5a6af4f64f92f0afaee4a69'
step_id: 'S337'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-235` for `src/aeat/domain/deadlines/_recargo.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/deadlines/_recargo.py`

## Description

- Reconstructed the surcharge-rule exception from closeout commit `4523bb9108`.
- Confirmed the module derives public legal rules in memory and creates no persistence surface.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The surcharge-rule module remains an accepted plaintext exception; targeted validation passed 21 tests.

## Notes

No persistence migration is warranted.
