---
tags:
  - '#audit'
  - '#calculation-correctness-campaign'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:3b5c2f32751f553f8c481c509934de73600213881dab2797b7927e7fa6c288d2'
related: []
---

# `calculation-correctness-campaign` audit: `M390 annual total sums three of LIVA art 161's four recargo tiers`

## Finding

`modelo-390-iva-anual-cuota-devengada-total` sums three of the four recargo de
equivalencia cuota tiers LIVA art. 161 establishes. The 1,75 % tabaco tier
(art. 161 4.º) is absent, while M303's quarterly total includes its counterpart.
The two returns therefore disagree for any filer who declares tabaco recargo, and
an exact-equality verification predicate compares them.

Verified against the loaded snapshots (`bundled_authority().snapshot(...)`,
filing year 2025), not the TOML tree:

- `modelo-390-iva-anual-cuota-devengada-total` sums 7 casillas; its recargo
  members are exactly `iva.anual.repercutido.recargo.general`,
  `...recargo.reducido` and `...recargo.super-reducido`. No `tipo-1-75` member.
- The box it omits exists: `iva.anual.repercutido.recargo.tipo-1-75.cuota`,
  `input_kind = manual` (with its `.base` sibling).
- `modelo-303-iva-cuota-devengada-total` sums 16 casillas **including `158`** —
  the tabaco cuota box, whose Tipo `[157]` the design fixes as the constant
  `00175`.

## Why it matters

The M390 formula file's own header states the rule and the stakes. It records
that the recargo tiers were once omitted from this aggregate, that this mirrored
the M303 casilla-27 defect, and that a supplier charging recargo "had its recargo
cuota silently excluded from the annual Total cuota devengada". It then names the
consequence that motivated the repair:

> from the modelo-390-cuota-devengada-total-equals-reconciliacion-303
> BLOCKING_RULE (which compares this total against the sum of the four filed
> Modelo 303 quarters' casilla 27, which DOES include recargo per the M303
> fix — a mismatch would have blocked every recargo-de-equivalencia filer's
> resumen anual).

That predicate is live and is an exact equality:

```
modelo-390-cuota-devengada-total-equals-reconciliacion-303
  equals(["iva.anual.cuota-devengada-total", "iva.anual.reconciliacion.devengada-303"])
```

The reasoning that justified adding general, reducido and super-reducido applies
unchanged to the fourth tier, and was not carried to it. The file's closing
summary says the total "covers the four devengada rungs this revision currently
models (general/reducido/super-reducido repercutido plus autorepercutido
intracomunitaria)" and enumerates the *other* known modelling gaps it is not
reopening — intragrupo, criterio de caja, bienes usados, agencias de viajes,
adquisición intracomunitaria, inversión del sujeto pasivo. The tabaco tier is not
among them. Its absence from this aggregate is undocumented, unlike its absence
from the ledger routing, which three registry files do document.

This is **not** the deliberate exclusion already checked and found sound. That one
drops the six *rate-specific* recargo bindings because they would double count
against the rate-blind tier bindings. `tipo-1-75.cuota` is `manual`: no rate-blind
binding covers it, so nothing double counts.

### Direction

Stated precisely, because the honest answer is narrower than "silent
under-declaration":

- Both sides zero (the common case today, since the tabaco population has no
  ledger path): no mismatch, no effect.
- Operator declares tabaco recargo on the quarterly M303 `[158]`: it enters
  casilla 27, the reconciliation diverges from the annual total, and the equality
  predicate **blocks the resumen anual** — precisely the outcome the header says
  the earlier fix existed to prevent.
- Were that predicate absent or downgraded, the same gap would under-declare the
  annual return against the summed quarters.

So the live failure is a hard, visible block on a filer who declared correctly,
not a silent shortfall. That is the safe direction, but it is still a defect: it
refuses a legitimate return, and the exposure is conditional on operator
knowledge in the same way as the ledger-path gap in
`[[2026-08-27-calculation-correctness-campaign-recargo-tabaco-rung-unreachable-audit]]`.

## Second defect: a stale casilla mapping in the same header

The header identifies the third tier as:

> the super-reducido 0.5pct tier (M303 casilla 158,
> `iva.anual.repercutido.recargo.super-reducido`)

That mapping is stale. The `[158]`/`[170]` repair reallocated those boxes: M303
`[158]` is now the tabaco rung, its Tipo `[157]` fixed at `00175`, and the
super-reducido binding moved to `[170]`, whose Tipo `[169]` admits `00050`. The
M303 casilla file states this in terms:

> The design fixes this rung's Tipo % [157] as the constant "00175" -- the LIVA
> art. 161.4 tabaco recargo. It previously carried the super-reducido binding, so
> the 0,5 % cuota was declared under a rate AEAT publishes as 1,75 %. That binding
> now feeds [170].

The M390 formula itself sums the semantic id
`iva.anual.repercutido.recargo.super-reducido`, so the computation is not wrong —
only the prose that documents which quarterly box it corresponds to. But that
prose is the reconciliation's stated basis, so anyone auditing the M390/M303
correspondence from this comment is pointed at the tabaco box while reading about
super-reducido. This is the cross-modelo form of the standing hazard: **never
join on a casilla id across revisions or returns** — ids are reallocated, and this
one was, by a repair already landed in this campaign.

## Remediation — owner's decision, not taken here

Two questions, deliberately left open:

1. Should `iva.anual.repercutido.recargo.tipo-1-75.cuota` join the annual total?
   The symmetry argument with M303 casilla 27 says yes, and the header's own
   reasoning says yes. Confirm against the official M390 box [47] "Total cuotas
   IVA y recargo de equivalencia" design before adding a member, and note that the
   AEAT Manual práctico worked example the current tiers were grounded against
   charges no tabaco recargo, so it cannot settle this the way it settled
   general/reducido. A `test_m390_super_reducido_recargo_delta`-shaped structural
   proof is the available instrument, as it was for the third tier.
2. Correct the header's `casilla 158` reference to `[170]`.

Neither is applied here: the first changes a declared total and must be grounded
before it ships, per the standing rule that the oracle follows the fix.

No production code, registry data or test was changed by this audit.

## Blast radius and sibling sweep, same day

Two follow-up checks against the loaded snapshots, both narrowing the finding to
exactly one aggregate and widening its consequence by one predicate.

### No base-side sibling

Enumerating every formula on both returns and filtering for recargo members:
exactly one aggregate per return reaches them —
`modelo-390-iva-anual-cuota-devengada-total` (3 recargo members, no `tipo-1-75`)
and `modelo-303-iva-cuota-devengada-total` (`18`, `21`, `24`, `158`, `170`,
tabaco present). There is no base-side total that omits `tipo-1-75.base`, because
no computed aggregate sums the recargo *bases* at all. The defect is confined to
the single cuota total, and the standing "check whether it has siblings" question
is answered: it does not.

### The omission propagates to the annual result, and to a second predicate

`modelo-390-iva-anual-resultado-regimen-general` computes
`iva.anual.resultado-regimen-general` from exactly two members:

```
[iva.anual.cuota-devengada-total, iva.anual.cuota-deducible-total]
```

So the missing tier flows straight into the annual result. That matters because a
second exact-equality predicate guards it:

```
modelo-390-resultado-regimen-general-equals-reconciliacion-303
  equals(["iva.anual.resultado-regimen-general", "iva.anual.reconciliacion.resultado-303"])
```

The finding above cited one blocking equality
(`...cuota-devengada-total-equals-reconciliacion-303`). There are two: the total
and the result are each compared against their M303-derived reconciliation, and a
tabaco-declaring filer diverges on both. This is the propagation path the formula
header predicted in prose — "and therefore from
`iva.anual.resultado-regimen-general`" — now confirmed structurally rather than
read from a comment.

Neither check changes the remediation question, which remains the owner's.

## Structural confirmation: tabaco falls through both categories

A reasonable objection to this finding would be that tabaco's absence from the
total is just the *same* deliberate exclusion already checked and found sound —
the one that drops the rate-specific recargo bindings so they do not double count
against the rate-blind tiers. Enumerating the revision's 24 recargo casillas
shows it is not.

| group | casillas | `input_kind` |
|---|---|---|
| rate-blind tiers **summed by the total** | `recargo.general`, `recargo.reducido`, `recargo.super-reducido` | all **bound** |
| rate-specific cuotas **excluded as duplicates** | `tipo-5-2`, `tipo-1-4`, `tipo-0-5`, `tipo-0-62`, `tipo-0-26`, `tipo-1` | all **bound** — six, exactly the recorded set |
| **tabaco** | `tipo-1-75.cuota` | **manual** |
| zero-rate transitional | `tipo-0.cuota` | manual (a 0 % recargo yields no cuota) |

So the exclusion rationale does not reach tabaco. The six excluded rungs are
excluded **because they are bound** and would double count the three bound
rate-blind tiers that the total does sum. `tipo-1-75.cuota` is the only
rate-specific cuota box that is *not* bound — it has no binding and no ledger
route, consistent with the separately recorded tabaco-rung finding — so it cannot
double count anything.

And there is **no rate-blind tabaco tier box** for the total to reach instead.
LIVA art. 161 has four tiers; M390 carries rate-blind boxes for three of them.

Tabaco therefore falls through both categories: not a bound duplicate to exclude,
and not one of the three rate-blind tiers to include. Its cuota reaches the annual
total by no path at all. That is the finding, now confirmed from the casilla
structure rather than from the formula alone.
