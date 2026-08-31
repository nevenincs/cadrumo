---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:4f81b3cd507a4c3437c514fc0ceb7e86c379aa3c231e51599b01829ba044f305'
step_id: 'S149'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Census the rate scales, clear the unbounded evidence-draft rate as taxonomy-bounded rather than unguarded, and make the inventory wire bounds read the scale constants instead of respelling them

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`
- `verify:` probed `resolve_iva_rate_slot` at None / 21 / 0.21 / 210 / -5 / 10
- `verify:` `pytest cli/tests -k ledger_business -n 0 -m ""` -> pass (2)

## Notes

The rate-scale census found `iva_rate` carrying four encodings under one name:
a fraction [0,1] on `Transaction`, a percentage 0-100 on the asset and inventory
ledgers, a percentage on the CLI wire mirror of those, and a whole-number
percentage on the evidence draft with no bound declared at all. The codebase had
already written the hazard down -- `_iva_rate_is_a_fraction_not_a_percentage`
says an operator moving between those surfaces "has two conventions under one
option name and no signal telling them which applies".

The unbounded evidence-draft field was reported as unclear and is NOT a defect.
Its values pass through `resolve_iva_rate_slot`, which maps against a closed slot
taxonomy rather than a range, so a mis-read `210` is refused with the accepted
set named -- and so is `0.21`, which is the fraction-scale value arriving on a
percentage-scale path. Probed rather than taken from the docstring. A bound
expressed as a closed SET is still a bound, and a scan looking for numeric
constraints will not see it.

What was worth fixing is smaller. The wire mirror spelled its two scale bounds as
local `_HUNDRED` and `_ONE` constants, re-deriving them outside the commit that
centralised the percentage scale. They now read `PERCENTAGE_MIN`/`PERCENTAGE_MAX`
and `UNIT_PROPORTION_MIN`/`UNIT_PROPORTION_MAX`. The saving is not the two lines:
this one module carries a percentage-scale rate and a share-scale ratio side by
side, and a local `_HUNDRED` beside a local `_ONE` is precisely the pairing that
lets one field quietly take the other convention. The named constants say which
scale is meant.
