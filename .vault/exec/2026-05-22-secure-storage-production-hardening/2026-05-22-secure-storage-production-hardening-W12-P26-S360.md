---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S360'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-258` for `src/aeat/domain/normatives/_loader.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/normatives/_loader.py`

## Description

- Reconstructed the normative-loader exception from closeout commit `4523bb9108`.
- Confirmed the historic package was retired in `7c79f1a225` when corpus ownership moved to the calculations-registry architecture.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The historic loader has been deliberately retired under the code-led architecture, with no compatibility shim and no outstanding implementation work. Targeted validation passed 21 tests.

## Notes

This evidence records retirement rather than asserting the deleted path remains present.
