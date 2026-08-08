---
tags:
  - '#reference'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b3e1c2c686a3cf946b052db9c98f3875d2b897630876256cfd4492e2300ffcba'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# `synced-history-consumption` reference: `calculation input, reconciliation target, or display only`

## Summary

The census established 81 bindings a pulled AEAT filing could feed. This
classifies each of them, and it does so from each row's OWN registry declaration
rather than by analogy to a sibling modelo, because the registry already carries
a per-dependency classification axis for exactly this question.

`DependencyClassificationDefinition.treatment` is a closed three-value field —
`direct_annual_settlement`, `factual_evidence`, `non_dependency` — declared once
per source modelo per revision, each instance carrying its own required
`legal_refs` and `source_refs`. It is the non-analogical grounding this
classification needs: modelo 100's dependency on modelo 130 is declared by
modelo 100's own revision and cites modelo 100's own provisions, and nothing in
it is inherited from how a sibling treats a similar-looking source.

## The classification

Joining every one of the 81 carry bindings to the treatment governing it, via
`relation_refs` for a `relation_prefill` slot and via the dependency on the
selector's source modelo for a `previous_filing` binding:

| declared treatment | bindings | classification |
| --- | --- | --- |
| `direct_annual_settlement` | 52 | calculation input |
| `factual_evidence` | 12 | reconciliation target only |
| no treatment declared | 17 | UNCLASSIFIABLE from its own declaration |

Nothing lands in "display only". No pulled fact on this list exists purely to be
shown: every one of the 81 is wired into a binding a formula reads, so the
display-only bucket is empty by measurement rather than by choice.

## Calculation input: 52 bindings

Declared `direct_annual_settlement`. The registry's own words for this treatment
are that the source modelo's figure settles directly into the target's
liquidation, which is a calculation input by declaration and needs no analogy.

The grounding is per-row and real. Modelo 100's dependency on modelo 130 cites
`rd-439-2007:art-109` (the pago fraccionado of actividades económicas) and
`orden-hac-277-2026:art-3`. Modelo 390's dependency on modelo 303 cites eleven
provisions including `ley-37-1992:art-99`, `art-115`, `art-116` and
`orden-eha-3111-2009:art-1`. Each is the provision that makes the prior filing's
own figure the one the annual return settles against.

Two of the 52 are unreachable by pull, both on modelo 200 fed by modelo 202,
because the declarations register does not serve Sociedades. The other 50 are
reachable and, per the executed regression, actually arrive.

## Reconciliation target only: 12 bindings

Declared `factual_evidence`. The registry says the prior filing is a fact to
reconcile against, not a figure that settles the current return.

Modelo 303's dependency on its own prior quarter is `factual_evidence`, citing
`ley-37-1992:art-99`, `art-115`, `art-116` and `rd-1624-1992:art-71`, `art-29`,
`art-30`. Modelo 200's dependency on its own prior-year bases imponibles
negativas is `factual_evidence`, citing `ley-27-2014:art-26`, `art-25`, `art-13`.
Modelo 100's dependency on modelo 193 is `factual_evidence`, citing
`ley-35-2006:art-99`, `rd-439-2007:art-108` and `orden-eha-3377-2011:art-1` — the
retención the taxpayer SUFFERS and the payer files, evidenced by the income
certificate rather than settled from a return the taxpayer never filed.

Three of the 12 are pull-reachable; the other 9 are the Sociedades slots the
register cannot serve.

## The resolver does not distinguish the two classes

This is the finding that matters for the ruling.

`relation_source_requirements` in
`src/cadrumo/domain/calculations/registry/_relations.py` reads
`classification.treatment` and folds it into the requirement's GROUPING KEY. That
is the only production use of the field on the resolution path: it discriminates
which requirements bucket together. It gates nothing.

So a `factual_evidence` relation and a `direct_annual_settlement` relation
resolve identically into binding values, and the engine consumes both the same
way. The registry draws a distinction between a figure that settles and a fact to
reconcile against, and the calculation layer does not act on it. A pulled modelo
193 retención — declared evidence, suffered rather than filed by this taxpayer —
reaches the annual return by the same path a pulled modelo 130 pago fraccionado
does.

Whether that is wrong is a ruling, not a measurement. What is measured is that
the distinction exists in the data and has no effect in the code.

## The 17 that cannot be classified from their own declaration

15 `previous_filing` bindings and both `iva_compensation_annual_partition`
bindings are governed by no dependency classification at all, so there is no
declared treatment to read:

- modelo 100 base liquidable negativa general anterior, 2024 and 2025 revisions
- modelo 130 previous-year economic-activity net income, prior pagos
  fraccionados, and prior negative results
- modelo 131 prior negative results, on all four revisions
- modelo 353 prior modelo 322 cuota devengada, cuota deducible and resultado
- modelo 720 prior-year valuation baselines for cuentas, inmuebles and valores
- modelo 390's two compensación partition slots

Classifying these would require reasoning by analogy from a sibling modelo, which
this step is forbidden to do and which would be wrong on the merits: modelo 720's
prior-year valuation baseline and modelo 130's prior negative results are not the
same kind of carry, and AEAT surfaces do not transfer between modelos.

The honest disposition is that the registry is silent on 21 % of the carry
surface. This is not a defect discovered in passing — it is the gap the ruling
has to close, because a treatment that is undeclared cannot later be cited as
authority for having consumed the value.

Note on reachability for the two modelo 390 partition slots: the joining probe
reports them as not-pullable, which is an artefact of the probe deriving the
source modelo from a relation or a previous-filing selector, and these slots
carry neither. They read filed modelo 303 history, and modelo 303 IS pullable, so
the census's reachable verdict for them stands and this table's reachability
column should not be read for those two rows.

## What this does not establish

It does not rule. It records what the registry declares, what the code does with
that declaration, and where the declaration is missing. Whether a
`factual_evidence` pulled fact MAY be a calculation input, and what the 17
undeclared rows should be, are the ruling's questions.

It also does not re-examine the non-official-evidence boundary, which is
untouched by any of this: an observation persisted by the local filing flow
carries a non-official source kind and still cannot satisfy the gate external
AEAT filing evidence satisfies. That boundary governs whether a filing is proven;
this classification governs what a proven filing's figures are FOR. The two are
independent, and a ruling that promotes a pulled fact to a calculation input must
say why the promotion does not erode the first.
