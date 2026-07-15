---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S345'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-243` for `src/aeat/domain/iva/_rates.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/iva/_rates.py`

## Description

- Reconstructed the IVA rate-table exception from closeout commit `c03d28fb34`.
- Confirmed rates derive from bundled authority and do not persist profile data.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The IVA rates remain a justified plaintext exception; targeted validation passed 21 tests.

## Notes

The classification remains code-led and current.
