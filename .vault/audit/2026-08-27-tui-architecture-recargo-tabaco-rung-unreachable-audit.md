---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:281a80e4a40e26947850e6d0da596a0314abed8a18ad03c24d452f68f38e09da'
related: []
---

# `tui-architecture` audit: `the recargo tabaco rung has a rate and boxes but no ledger path`

## Scope

## Findings

## Recommendations

## Finding

The recargo de equivalencia tabaco rung -- 1,75 %, LIVA art. 161.4 -- is
modelled everywhere except the one place that would make it reachable.

Present:
- the RATE, as a validated domain field with a registry parameter id
  (`domain/iva/_recargo_equivalencia.py`, `liva-art-161:recargo-rate-tabaco`);
- the BOXES, on both returns: M303 casilla 158 (`input_kind = "manual"`) and
  M390 boxes [41]/[42].

Absent: any way for a supply to BE tabaco. `IvaCategory` carries 21 members and
exactly one recargo member, the generic `recargo_equivalencia`. Nothing
distinguishes entregas de labores del tabaco from any other recargo supply, so
no ledger row can route to the 1,75 % rung.

Two independent registry files say the same thing, written by different work:

- M303 casilla 158: "This box stays operator-input until the tabaco population
  is modelled -- an omission, not this mis-allocation."
- M390 `0004-recargo-rate-box-layer.toml`: "The tabaco rung ... is absent
  because the IVA category it depends on is not modelled at all; that is a
  separate omission from this merge and is not repaired by adding a rung here."

## Why it matters, and which direction it fails in

This is the under-declaration direction. A recargo filer who supplies tobacco
owes 1,75 % recargo; with no category to carry it, the cuota reaches no box
from the ledger. The operator would have to know to hand-enter M303 [158], and
nothing tells them: no refusal, no advisory, no unrouted-source diagnostic --
because there is no source kind to be unrouted.

`no-silent-under-declaration` is explicit that a silent blank is the failure
mode to prevent. The rung is not blank because a value resolved to zero; it is
blank because the population it draws from does not exist as a concept.

## What is NOT wrong

Checked and sound, recorded so a later reader does not re-open them:

- M303's quarterly `cuota-devengada-total` enumerates the recargo rungs that
  each design year actually has -- 3 for 2022, 4 for 2023 and 2024-hasta-08,
  5 from 2024-desde-09 onward -- and casillas 158/170 exist exactly where the
  arg counts change. The totals track the form rather than being copied.
- M390's annual total sums the three rate-BLIND tier bindings and deliberately
  excludes the six rate-specific ones. Summing both would double count. The
  rate-blind bindings are the ones that keep a row whose IVA rate the ledger
  never recorded, which is why they and not the per-rate boxes feed the total.
- The M303 [158]/[170] mis-allocation named in the formula comment is already
  repaired: [170] carries the super-reducido binding and [158] is manual.

## Status

Open. Modelling the tabaco population is the fix; until then the rung is
operator-input with no prompt.

## Re-verification, 2026-08-28

Every claim above was re-checked against the loaded snapshot
(`bundled_authority().snapshot(...)`) rather than the TOML tree. The finding
**stands unchanged**. Three additions sharpen it.

### The gap has a precise shape: bound siblings beside a manual rung

The tabaco rung is not merely "not routed" — it sits beside siblings that *are*
routed, on both returns. From the 2025 snapshots:

| return | ordinary recargo rungs | tabaco rung |
|---|---|---|
| M303 | `[170]` `bound` | `[157]` / `[158]` `manual`, `required=False` |
| M390 | `iva.anual.repercutido.recargo.general` `bound`, `...recargo.reducido` `bound` | `...recargo.tipo-1-75.base` `manual`, `...tipo-1-75.cuota` `manual` |

`bound` is the shape the tabaco rung would take once the population is modelled.
The contrast is the finding made concrete: for every other recargo tier the
ledger feeds the box, and for this one the operator must know to fill it.

This also refines the direction. The rung is **reachable by operator input** — it
is not a dead box, and a filer who knows about it can declare the cuota by hand.
What is absent is the automatic path, and with it any signal that a tabaco supply
went unrouted. The under-declaration exposure is therefore conditional on
operator knowledge rather than unconditional, which is a weaker claim than
"unreachable" but still the unwatched direction: nothing tells an operator the
box exists or that their ledger held supplies belonging in it.

### A third registry file says the same, and it constrains the remedy

Beyond the two files already quoted, `_data/registry/aeat/iva/recargo-rates.toml`
excludes tabaco deliberately and explains why:

> TABACO IS NOT HERE, DELIBERATELY. The 1,75 % rate of art. 161 4.o attaches to
> a PRODUCT (labores del tabaco), not to the accompanying IVA rate, so it is not
> expressible on this axis and stays a legal parameter read directly.

That is a remediation constraint, not just corroboration. The operational recargo
table is keyed on the accompanying IVA rate — deliberately, because the 2023-2024
foodstuffs measures put two recargos on one tier. Art. 161.4 does not sit on that
axis at all. So modelling the population needs a **product** discriminator; adding
an `IvaCategory` member alone would not give the rate table a key to resolve, and
the rate would still have to be read directly from
`liva-art-161:recargo-rate-tabaco` (confirmed present in the legal catalogue at
`0.0175`, alongside the reviewed `0.052` / `0.014` / `0.005` siblings).

### Probe caveat: the ids do not say "tabaco"

The registry ids for these boxes are `iva.anual.repercutido.recargo.tipo-1-75.*`
and the M303 pair carries the positional roles `dr303_157` / `dr303_158`. None
contains the string "tabaco"; the word appears only in comments and in the legal
catalogue. A sweep filtering casilla `id` or `semantic_role` for "tabaco" returns
an empty set on both returns and invites the false conclusion that the boxes do
not exist. They do. Filter on the rate (`1-75`, `0.0175`) or read the comments.
This is the thirteenth filter bug of this campaign and the standing rule applies:
an implausibly empty derived set is a filter bug until proven otherwise.
