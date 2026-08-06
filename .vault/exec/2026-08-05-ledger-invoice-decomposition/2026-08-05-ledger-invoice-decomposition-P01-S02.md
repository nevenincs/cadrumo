---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:0d4f7dd5fcc478ea5287568ae200a56140d4387df1b8bb9d2376e8a64f35a53c'
step_id: 'S02'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Remove the divergent fact default from the impatriado income selector so both siblings are required

## Scope

- `src/cadrumo/domain/calculations/registry/_ledger_impatriado_bindings.py`

## Description

- Remove the divergent `fact` default from `_ImpatriadoLedgerIncomeSelector`.
- Mirror the renta sibling's before-validator so both families refuse an omitted `fact` identically.

## Outcome

Landed in commit `73ea70ea41`, alongside S01.

Both income selectors now require `fact`. This is the half that actually closes the finding: the renta selector defaulted to the cash measure and the impatriado one to the ingresos-integros measure, so one concept carried two silent defaults that disagreed on the figure determining a taxpayer's declared income. Leaving a default on one sibling would have re-created the divergence.

Zero behaviour change: both committed M151 bindings (revisions 2015-y-siguientes and 2025-y-siguientes) declare the ingresos-integros fact explicitly, verified at HEAD.

Test evidence: the impatriado income-binding module passes within the 14-test income-binding run; registry suite counts as recorded in S01.

## Notes

The impatriado default was the STRONGER measure, so removing it changes nothing about correctness on its own. It was removed because a default on one sibling and not the other is exactly the asymmetry that let the divergence survive review.
