---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S334'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-232` for `src/aeat/domain/categories/_registry.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/categories/_registry.py`

## Description

- Reconstructed the category-registry exception from closeout commit `c03d28fb34`.
- Confirmed bundled authority is resolved through the resource boundary rather than mutable profile storage.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The registry remains a package-bundled authority input, not a secure-object alternative. Targeted validation passed 21 tests.

## Notes

No deferred storage migration remains for this exception.
