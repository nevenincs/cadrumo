---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:e95b66af83c8bc598196b8501b048f8d63853f1bc4d250bd846aff15239ab1ef'
step_id: 'S10'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# Add the accepted M210 IRNR ledger binding source and registry selector for the gross-income target, with exclusive source ownership

## Scope

- `src/aeat/core/aggregation.py + src/aeat/_data/registry/aeat/modelos/210`

## Description

- Add the `M210_IRNR_INCOME_LEDGER` binding source kind and a typed selector for the selected official income code.
- Register the Modelo 210 `[5]` ledger resolver and make manual and ledger ownership mutually exclusive.
- Carry binding values, provenance, and ledger-derived annual grouped-renta rows through the calculation boundary.

## Outcome

The registry selects an admitted M210 official code without collapsing it into the conceptual formula rate token. Ledger mode resolves casilla `[5]` from the owned source and refuses a manual `[5]` value or manual grouping rows. The binding taxonomy remains mechanically derived and its registry tests pass. Landed in `8f5f690ed0`.

## Notes

No parallel write path was added: source ownership is resolved at the calculation boundary.
