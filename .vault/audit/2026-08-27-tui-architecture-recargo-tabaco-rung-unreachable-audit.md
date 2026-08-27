---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:696468bcdc7bc86e1689f6e7140bdd281096d14be3ce24d5fd4ad99c18c517fa'
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
