---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:3fd2a7973466bcd1a44a6e5f03969ba6f0d9856a54eb75ec36b105768a9905e5'
step_id: 'S11'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Update the --idempotency-key CLI help text through the locale CLI to state that a stable key is required per logical add and the keyless path is append-only

## Scope

- `src/aeat/locales/`

## Description

- Rewrite `cli.ledger.add.idempotency_key_help` in en/es/ca/hu to state the retry-safety contract: passing the same key again is a safe no-op so retries do not duplicate the row, and omitting the key appends a deliberate duplicate.

## Outcome

Landed in commit `c8b592971`. Hand-edited at the existing key (the locale CLI's full reconciliation would otherwise pull unrelated peer-campaign keys into the commit); parity and honesty gates pass.

## Notes
