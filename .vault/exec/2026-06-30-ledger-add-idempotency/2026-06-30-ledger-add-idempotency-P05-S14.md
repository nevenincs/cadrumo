---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:ed64906f444b145791051af2d390524bba75073c8a1377da6d063d4277491594'
step_id: 'S14'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Add a test proving a same-key add with differing content raises the instructive conflict error

## Scope

- `src/aeat/application/ledger/tests/`

## Description

- Add a real-repository test proving a same-key add naming a different movement raises the instructive conflict refusal and leaves the original row untouched.

## Outcome

Landed in commit `3d8a6c14b`. The guard scans by the clock-free provider id `manual:{bucket}:{key}`, so a reused key with differing content is caught regardless of which field diverges.

## Notes
