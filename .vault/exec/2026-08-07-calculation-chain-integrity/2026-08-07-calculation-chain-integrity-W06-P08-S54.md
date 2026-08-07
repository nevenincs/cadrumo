---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:987ed6d725f0b0c2d67f2335f5d7f51d7a368d83309522a93044976550e099d7'
step_id: 'S54'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S54

## Outcome

Landed in code by `d893dfee6d`, verified at HEAD. Recorded here because it had no exec record; the implementation is a peer's.

## What shipped

`IvaLedgerObservation.applied_rate` — the numeric IVA rate the line was actually charged at, as a fraction, bounded `[0, 1]` and `None` when genuinely unknown (`_ledger_bindings.py:391`).

Its docstring states the load-bearing point: the rate is carried **alongside** `rate_kind`, not instead of it, because the two answer different questions. The tier says which statutory band the line falls in; the applied rate says what was charged. Those coincide until a tier's rate changes mid-year, and then they do not.

## Why the pair is necessary rather than redundant

Modelo 303 carries one box per tier; Modelo 390 carries one box per rate per window. A temporary rate change inside a year therefore splits one M303 tier across two M390 boxes, and a record holding only the tier cannot say which box a line belongs in. Collapsing to the tier loses that; collapsing to the rate loses the band a line was assessed under.

The regression is pinned by `test_the_applied_rate_survives_tier_resolution`: two lines of one tier charged at different rates stay distinguishable after tier resolution.

## Relation to S55

This is the observation half. `S55` is the selector half — a binding cannot use an axis the observation does not carry, so this had to land first. Together they let the annual form bind one box per rate per window.
