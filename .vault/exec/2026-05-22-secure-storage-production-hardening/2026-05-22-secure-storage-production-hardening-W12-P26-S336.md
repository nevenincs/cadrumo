---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:aec1b610ea84c472273ab0cb358fbb7001c0a9989a3eb6698ca9a79e0288e34d'
step_id: 'S336'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-234` for `src/aeat/domain/deadlines/_festivos.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/domain/deadlines/_festivos.py`

## Description

- Reconstructed the public-holiday corpus exception from closeout commit `4523bb9108`.
- Confirmed the module consumes public calendar authority and does not persist profile data.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The holiday calendar remains a justified plaintext exception; targeted validation passed 21 tests.

## Notes

No secure-storage work is deferred for public legal-calendar input.
