---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S349'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-247` for `src/aeat/domain/manuals/_fetch.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/manuals/_fetch.py`

## Description

- Reconstructed the manual-fetch exception from closeout commit `4523bb9108`.
- Confirmed the boundary reads public corpus material rather than sensitive bucket data.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The manual fetcher remains a justified public-corpus exception; targeted validation passed 21 tests.

## Notes

This closeout does not authorize persistence of fetched material outside its established corpus rules.
