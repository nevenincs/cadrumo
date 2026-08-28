---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:ceaf4ea2af167798ef34b5ff0c477e1399623fba26a4263a64ea78bfea351592'
related:
  - "[[2026-08-28-tui-architecture-m210-pension-scale-corpus-row-audit]]"
---

# `tui-architecture` audit: `Murcia 2022 autonomic scale over-states accumulated cuota above 60.000 euros`

## Scope

## Findings

## Recommendations

## Finding

`renta-2022-escala-autonomica-murcia-base-general` over-states its accumulated
cuota at the top rung by **90,83 €**. The runtime computes

```
cuota = fixed_addition + marginal_rate * (base - lower_bound)
```

(`domain/calculations/registry/formula_runtime_ops.py:248`), so every Murcia 2022
filer with base liquidable general above 60.000 € receives an autonomic cuota
90,83 € **higher** than the scale's own lower tranches produce.

| lower_bound | rate | fixed_addition | implied by the rows beneath | gap |
|---|---|---|---|---|
| 0 | 0,096 | 0 | — | — |
| 12.960,45 | 0,1146 | 1.244,20 | 1.244,2032 | ok |
| 21.028,20 | 0,1374 | 2.168,76 | 2.168,7642 | ok |
| 35.394,00 | 0,1822 | 4.142,62 | 4.142,6209 | ok |
| 60.000,00 | 0,227 | **8.716,67** | **8.625,84** | **+90,83** |

Rows one to four are mutually exact. Only the top rung breaks.

## The cause is provable from the table itself

Murcia deflated its 2022 scale by **4,1 %**. The three lower bounds are the
standard bounds multiplied by exactly 1,041:

| standard | encoded | factor |
|---|---|---|
| 12.450 | 12.960,45 | **1,041** |
| 20.200 | 21.028,20 | **1,041** |
| 34.000 | 35.394,00 | **1,041** |
| 60.000 | 60.000,00 | 1,00 — not inflated |

Recomputing the accumulated cuota at the top rung with the **same rates** but the
**un-deflated** bounds gives `8.716,67` — the encoded value, exact to the cent.
With the deflated bounds actually in the table it is `8.625,84`.

So the top rung's `fixed_addition` was carried over from the un-deflated version
of the scale while rows two to four were recomputed for the deflactación. The
table carries the accumulated cuota of a version it is not — the same shape as the
M210 pension excerpt recorded alongside this, and here it is live arithmetic
rather than evidence.

## Direction — over-payment, and nothing watches it

The taxpayer is charged **more** than the scale prescribes. Over-payment produces
a valid return, no refusal and no signal, which is precisely the direction this
campaign's organising question was written for. An under-declaration of the same
size would have had several guards to trip; this had none.

**Nothing pins the value.** `8716.67` appears in no Python file in the tree, so no
test would notice the repair or the defect. The table *is* engine-reachable —
`test_modelo_100_autonomic_chain.py:57` drives murcia — but the chain test checks
wiring, not the accumulated column.

## This escalates an already-open finding

The row cites only `ley-35-2006:art-74`, the framework article that states no
Murcia figure, and its `required_text` is `["Región de Murcia", "escala
autonómica"]` — pinning no number. It is one of the 90 ungrounded autonomic
tables already recorded, and one of the 99 parameters whose `required_text` pins
no number.

Those were carried as reviewability findings. This one shows the gap is not
cosmetic: an ungrounded scale concealed a real arithmetic error that
over-charges taxpayers, and the error survived because neither a citation nor a
test nor a comment stood between it and the engine.

## Remediation — owner's decision, not taken here

Two repairs are each internally self-consistent, and choosing between them needs
the official Murcia 2022 scale, which I did not have and did not invent:

1. the deflated table is correct → `fixed_addition` becomes `8.625,84`;
2. the top bound should also have been inflated → `60.000,00` becomes
   `62.460,00` (= 60.000 × 1,041), with its `fixed_addition` recomputed.

Many autonomic deflactaciones deliberately leave the top threshold at 60.000, so
(1) is the more likely reading — but that is a tax review against the Región de
Murcia's published scale, not an inference to be made here.

Whichever bound is correct, `8.716,67` is not consistent with the rows beneath it
and cannot be right as it stands.

A fix should land with a grounded citation and a regression pinning the
accumulated column, so the next such break is caught by more than an invariant
sweep.

## How it was found

A sweep of the accumulated-cuota continuity invariant
`fixed_addition[i] == fixed_addition[i-1] + rate[i-1] * (lower[i] - lower[i-1])`
over all 133 registry bracket tables. The invariant is a property of any
progressive scale and is not derived from the formula under test, so it is not
tautological.

Raw equality flagged 113 of 126 groups, which was implausible and was an
over-strict invariant rather than 113 defects: official scales publish the
accumulated column rounded to cents. Classified by magnitude the picture is
clean — **570 exact, 106 within half a cent, 6 at a one-cent rounding convention,
and exactly one gap above 1,5 cents**, which is this row at 90,83 €.

No production code, registry data or test was changed by this audit.

## The break is a cliff at the boundary, not a gentle drift

`_resolve_bracket_entry` returns the first bracket, in ascending `lower_bound`
order, satisfying `lower_bound <= base <= upper_bound`. Both ends are inclusive,
so at an exact boundary two brackets match and the **lower** one wins. Across
Murcia 2022's top boundary:

| base | cuota | bracket |
|---|---|---|
| 59.999,99 | 8.625,8314 | row 4 |
| 60.000,00 | 8.625,8332 | row 4 |
| **60.000,01** | **8.716,6723** | row 5 |

**One cent of extra base costs 90,84 €.** A contiguous progressive scale must be
continuous at its boundaries; this one steps.

That also explains why the inclusive-inclusive overlap at every boundary in the
registry is harmless *everywhere else*: when accumulated-cuota continuity holds,
the two matching brackets return the identical value, so which one wins cannot
matter. Continuity is what makes the selection rule safe, and Murcia 2022 is the
single row where it does not hold.

## The structural axes are clean, which narrows where a bracket defect can hide

The same sweep checked three further properties over the same 126 multi-row
groups. All are clean:

| property | if violated | count |
|---|---|---|
| gap between brackets | base in the gap raises `bracket_no_coverage` — fail-closed, loud | **0** |
| real overlap (`upper[i] > lower[i+1]`) | lowest bracket silently wins → under-charge | **0** |
| closed top bracket | base above it raises — fail-closed, loud | **0** |
| non-monotonic rates | a progressive scale that falls back | **0** |

Not vacuous: 683 bracket rows carry an `upper_bound` and every one chains exactly
to the next row's `lower_bound`; the 148 without one are the open top rows. The
checks had something to compare.

So bracket-table structure is sound registry-wide, and the two failure modes that
would have been *silent* — a real overlap, and a wrong accumulated cuota — are now
both measured. Only the second has an instance, and this audit is it.

Note the asymmetry worth keeping: the structural failures are all fail-closed and
loud, while the accumulated-cuota column has no guard at all. The registry is well
defended against the errors that would refuse a filing and undefended against the
one that quietly changes the amount.

## The finding survives an independent formulation of the invariant

The gate compares each row against its immediate predecessor's *encoded*
`fixed_addition`. That inherits whatever rounding the predecessor carries, so it
is worth asking whether the one break is an artefact of that choice. It is not.

Recomputing every table by accumulating **exactly from the first row**, never
re-reading a rounded value, gives the same single answer:

| | incremental (shipped gate) | exact-from-zero |
|---|---|---|
| exact match | 570 | 479 |
| within half a cent | 106 | 165 |
| 0,5 – 2 cents | 6 | 38 |
| **beyond 2 cents** | **1** | **1** |
| the break | Murcia 2022, 90,8368 | Murcia 2022, 90,8285 |

Neither formulation is uniquely correct — the two disagree on 32 rows in the
sub-cent bands because regions were authored under different rounding
conventions, some rounding the accumulated total once and some carrying rounded
tranches forward. What matters is that both agree on the only figure large enough
to be a defect, and they agree on its size to within a hundredth of a cent.

The shipped gate keeps the incremental form because it produces the tighter
distribution against this registry's actual authoring (6 rows in the sub-cent
band rather than 38), so its two-cent tolerance sits further from real data.

## What the sub-cent band actually contains

All six rows inside the shipped gate's band are the **same row** — the Asturias
70.000 rung — across filing years 2020 to 2025, each 0,008 € high. That is a
convention, not drift: the encoded values are the exact accumulation from zero
rounded once, so comparing against a rounded predecessor loses the fraction the
predecessor discarded.

Checked rather than waved through, because a tolerance is only honest if what it
absorbs has been looked at. Nothing in the band is a defect, and no row in it is
within two orders of magnitude of the Murcia break.
