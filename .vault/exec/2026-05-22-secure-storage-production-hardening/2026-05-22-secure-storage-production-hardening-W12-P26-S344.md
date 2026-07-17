---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S344'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-242` for `src/aeat/domain/iva/_catalogue.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/iva/_catalogue.py`

## Description

- Reconstructed the IVA catalogue exception from closeout commit `c03d28fb34`.
- Confirmed catalogue authority resolves from bundled reviewed resources rather than profile storage.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The IVA catalogue remains a justified plaintext exception; targeted validation passed 21 tests.

## Notes

No secure-object replacement is appropriate for bundled authority.
