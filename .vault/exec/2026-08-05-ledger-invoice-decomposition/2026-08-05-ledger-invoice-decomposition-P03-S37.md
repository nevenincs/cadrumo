---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:2a32f2b82a6510aa396d72d26107138395ada4dbc9adafadbd971b56980676b0'
step_id: 'S37'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Let an invoice record that its customer is under recargo de equivalencia, so an unrecorded surcharge stops being indistinguishable from one that does not apply

## Scope

- `src/cadrumo/domain/invoices/_models.py`
- `src/cadrumo/domain/invoices/_decomposition.py`

## Description

- Add a nullable `recargo_amount` to the invoice record and a `recargo_amount_eur` accessor mirroring the retención one.
- Move the totals identity to `grand_total == base_total + iva_total + recargo_amount`.
- Refuse a negative recargo, one exceeding the cuota it rides on, and any recargo on an all-exempt supply.
- Carry the surcharge through the decomposition contract as a required `recargo` component inside `total`, never inside `cash`.
- Correct the two module docstrings that stated the superseded identity.

## Outcome

Landed as commit `bf2a0c880a` (4 files, +290 / -20).

The defect was measured on the real model before any edit and the same three
cases re-measured after. The polarity is exactly inverted:

```
BEFORE  truthful total 1262 (base+iva+recargo)   REFUSED
        falsified total 1210 (recargo dropped)   ACCEPTED
        recargo_amount kwarg                     REFUSED  extra inputs not permitted

AFTER   truthful total 1262                      ACCEPTED
        falsified total 1210                     REFUSED  grand_total must equal
                                                          base_total + iva_total + recargo_amount
```

That inversion is the whole finding. The model did not merely lack a field: it
refused the true document and accepted the false one, so it actively selected
for wrong data. A supplier who wanted to record what a comerciante minorista was
actually charged had no representable option but to understate the total by the
surcharge.

Decomposition of the grounded record now yields
`base=1000.00 cuota=210.00 recargo=52.00 total=1262.00 cash=1262.00`.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/invoices -n 0 -q --no-header
136 passed in 5.87s
```

```
uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/domain/iva
  src/cadrumo/application/ledger src/cadrumo/application/aggregation
  src/cadrumo/domain/transactions -n 0 -q --no-header
1752 passed, 7 deselected in 100.90s (0:01:40)
```

Lint and format clean over every touched file.

Three mutations, each applied to a copy-aside and restored: dropping the recargo
term from the invoice identity reddens 9, moving it from `total` to `cash` in the
decomposition reddens 2, deleting the exempt-supply guard reddens 1. Both sources
restored byte-exact, verified by SHA-256 match rather than by trusting the copy
step.

## Notes

**Recargo and retención are deliberate opposites, and only one test can prove
it.** Retención is settlement-side, so it sits outside `grand_total`; recargo is
a price component under LIVA art. 161, so it sits inside. An invoice carrying
just one of the two balances identically whichever side that term is on, so a
future simplification moving either one would pass every single-term case. The
test carrying both is the only one that catches the swap, and the M2 mutation
confirms it does.

**Modelled as a flat nullable amount, not per-line.** Two carriers for this
concept already exist in the substrate and both are flat: the ledger transaction
and the cash-accounting payment evidence row. A per-line design would have been
more faithful to how the surcharge is actually computed, but it would have
introduced a third shape for one concept and required a recargo rate table that
does not ship in the registry — putting regulatory rate literals in a feature
module. The upper bound against `iva_total` is the loose check that survives
without such a table: every statutory tier (5.2 against 21, 1.4 against 10, 0.5
against 4) is a smaller percentage than its companion rate, so an excess is
arithmetically impossible and is far more likely to be the cuota written into the
wrong field.

**`None` and `Decimal("0")` are kept distinct**, which is the specific thing the
Step asked for. `None` is "this invoice makes no statement about recargo"; an
explicit zero is "the régimen was considered and does not apply". Defaulting the
field to zero would have collapsed the two and reproduced, in a new field, the
absence-as-signal conflation this campaign has spent its length removing.

**Scope widened by one file.** The Step named `_models.py` only. The
decomposition contract publishes the same identity and produces the components
downstream consumers read, so changing the model without it would have left the
contract silently dropping the surcharge from `total` — a smaller version of the
defect being fixed. Both moved together.

**Two production docstrings were already ahead of the code.** The Axis-A
component table and the ledger preflight refusal both told operators to record
supplier recargo through the invoice's recargo amount, which did not exist; only
the decomposition module was honest, stating the field absent and pre-specifying
that when added it joins `total`, not `cash`. That pre-specification is exactly
what was implemented, so the prose needed no correction beyond the two sites
stating the superseded identity. Prose asserting a property the code lacks is
worth treating as a defect report in its own right.

**Suplidos remain unrepresentable.** The originating finding covered two
non-base non-IVA components; this Step closes recargo only. A suplido is a
disbursement made in the customer's name and excluded from the base imponible
under LIVA art. 78.Tres.3, so it joins `total` and `cash` while joining neither
`base_total` nor `iva_total` — a third position on the identity, not a second
instance of this one. It needs its own Step and is not carried by this change.
