---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:26f53e08efbef4c30f16d4311c7b5b4247c7a2eeb45ebdfd01d16e0ecee3482c'
step_id: 'S17'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Confirm the lock-versus-carry override semantics are unchanged by asserting the existing override-rejection suite passes against the data-driven ladder

## Scope

- `src/aeat/application/modelo/tests`

## Description

- Run the caller-override rejection suite and the iva-wallet engine integration against the data-driven ladder.

## Outcome

50 passed (conformance + test_actions + local_cross_period_carry + iva_wallet_engine_integration); lock/carry override semantics unchanged. Commit `ddda33609`.

## Notes
