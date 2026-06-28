---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S08'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# add `ledger_iva_aggregation` bindings selecting `recargo_equivalencia` at each recargo tier for the recargo base and cuota casillas, grounded

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/`

## Description

Added the recargo aggregation to the existing `ledger_iva_aggregation` source
(reused rather than a new source kind, since recargo routes by the existing IVA
rate tier).

- Added `recargo_amount` to `IvaLedgerObservation`, threaded from
  `transaction.recargo_amount` through the IVA ledger aggregator (proportioned by
  business fraction like base/iva).
- Added the `recargo_amount_sum` fact to the `_IvaLedgerSelector`, its validator,
  and the resolve branch in `resolve_ledger_iva_aggregation_binding_values`.
- Authored three M303 recargo cuota bindings (general/reduced/super-reducido)
  selecting the matching IVA category at `recargo_amount_sum`, grounded in
  `ley-37-1992:art-161` (the bundled LIVA art-161 tier schedule:
  `liva-art-161:recargo-rate-*`).

Files: `src/aeat/domain/calculations/registry/_ledger_bindings.py`,
`src/aeat/application/aggregation/_iva_ledger.py`,
`src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/0005-recargo-cuota.part-001.toml`.

## Outcome

A regression test proves recargo aggregates by tier (general 52.00, reduced 14.00,
super 0) from observation recargo amounts; the IVA binding suite stays green.

## Notes

Tier-to-rate mapping (21% -> 5.2%, 10% -> 1.4%, 4% -> 0.5%) is the grounded LIVA
art-161 schedule, not invented.
