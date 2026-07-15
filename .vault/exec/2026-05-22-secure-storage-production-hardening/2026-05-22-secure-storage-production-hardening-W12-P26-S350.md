---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S350'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-248` for `src/aeat/domain/manuals/_loader.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/manuals/_loader.py`

## Description

- Reconstructed the manual-loader exception from closeout commit `4523bb9108`.
- Confirmed the loader is a public corpus and manifest authority boundary.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The manual loader remains a justified plaintext exception; targeted validation passed 21 tests.

## Notes

No secure-object alternative is required for bundled corpus loading.
