---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S352'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-250` for `src/aeat/domain/manuals/errors.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/manuals/errors.py`

## Description

- Reconstructed the manuals error-taxonomy exception from closeout commit `c03d28fb34`.
- Confirmed the historic `errors.py` module relocated atomically to `_errors.py` in `fd09b538d0` without a compatibility shim.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The error taxonomy remains a justified plaintext exception; targeted validation passed 21 tests and the path change is a completed code-led relocation.

## Notes

No work is deferred under the obsolete historic filename.
