---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S346'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-244` for `src/aeat/domain/iva/_recargo_equivalencia.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/iva/_recargo_equivalencia.py`

## Description

- Reconstructed the recargo-equivalencia exception from closeout commit `4523bb9108`.
- Confirmed the module derives public tax-rule inputs in memory and creates no persistence path.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The recargo-equivalencia rules remain a justified plaintext exception; targeted validation passed 21 tests.

## Notes

No profile-data migration is pending.
