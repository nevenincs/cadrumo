---
tags:
  - '#research'
  - '#silent-zero-base-aggregation'
date: '2026-06-19'
modified: '2026-06-19'
related:
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
---

# `silent-zero-base-aggregation` research: `Silent-zero regulated-base aggregation inventory`

A registry-wide sweep for the silent under-declaration pattern: a regulated base
or volume casilla that resolves to zero on the live calculate path while its
sibling cuota aggregates from the ledger — a cuota-without-base shape AEAT
rejects. The sweep classifies every candidate as either a bounded mirror (an
existing canonical ledger-aggregation source can feed it with only a registry
binding plus selector wiring) or an ADR-scale change (a new resolver, period
semantics, classification axis, or official-form restructure), per the governing
calculation-aggregation taxonomy. Discovery used the resident RAG service plus a
structural scan of every compiled modelo revision (bound casilla source kinds vs
manual money base/volume casillas) confirmed with `rg`.

## Findings

### Method

For each compiled modelo revision the scan recorded which casillas are bound to a
ledger-aggregation source (`ledger_iva_aggregation`, `ledger_oss_aggregation`,
`ledger_renta_income_aggregation`, `ledger_renta_expense_aggregation`,
`ledger_renta_gasto_aggregation`) and which money casillas labelled as a base
imponible or volumen remain manual and unbound. A modelo with bound cuotas but
manual bases is a silent-zero candidate.

### Resolved (bounded mirror, shipped)

- Modelo 130 casilla 02 "Gastos" (estimación directa, apartado I). Previously a
  manual casilla that silently reported zero, leaving rendimiento neto = ingresos
  and a cuota with no expense side. Resolved by the new
  `ledger_renta_gasto_aggregation` source — the OUTGOING sibling of
  `ledger_renta_income_aggregation` — enrolled in the live mesh, grounded in the
  same binding provision as the income side, and verified end to end to a `.boe`.
  An untagged expense (no IVA-exclusive base) is surfaced as `missing_taxable_base`
  rather than gross-folded, which would over-declare gastos.

### Active peer work (do not duplicate)

- Modelo 303 régimen-general per-tier base casillas (e.g. 150/153/156/165 and the
  21/10/4 percent base imponible boxes) and the soportado base. A peer is binding
  these to `ledger_iva_aggregation` with the `base_amount_sum` fact (the same
  source that already feeds the cuotas, proven by the intra-community/export base
  binding). This is a bounded mirror; it is in flight and its completeness
  manifest is mid-update, so it is owned elsewhere and excluded here.

### Stop at an ADR (exceeds a bounded mirror)

- Modelo 303 prorrata volumes (`volumen anual de operaciones que originan derecho
  a deducción` and `volumen anual total de operaciones`). These are annual
  operation volumes by deductibility class, applied provisionally during the year
  and regularised in the fourth quarter; they are not a per-period devengado base
  sum. Folding the period base totals into them would omit exempt-with-right
  supplies from the numerator and exempt-without-right operations from the
  denominator and ignore the provisional/regularisation structure, yielding wrong
  regulated prorrata. Needs a new annual-volume-by-deductibility aggregation plus a
  "no exempt operations implies 100 percent" determination. On a fully-taxable
  trader the divergence from the expected 100 percent is the M303 export blocker.

- Modelo 100 actividad-económica income. The first-slice EXPENSE casillas
  (0186/0192/0199/0203) aggregate from the ledger via
  `ledger_renta_expense_aggregation`, but the income side (casilla 0171 "Ingresos
  de explotación", feeding the computed 0180 total) is manual — an income/expense
  asymmetry that silently under-declares actividad income. The M130 income
  aggregator cannot be reused: it is quarterly-cumulative-locked, whereas Modelo
  100 is annual and first-slice-mapped like the heavy M100 expense pipeline.
  Building an annual M100 income aggregation is a new resolver/aggregator with its
  own period and casilla-mapping semantics, not a bounded mirror.

- Modelo 130 casilla 08 "Volumen de ingresos del trimestre". This sits in the
  estimación objetiva agrícola/ganadera/forestal section (apartado II), a
  different regime from the estimación directa income/gasto handled above.
  Aggregating it requires distinguishing agrarian-objetiva income from
  actividad-económica directa income in the ledger — a classification axis the
  current transaction model does not carry. Reusing the directa income aggregator
  would mis-route directa receipts into the agrarian volume.

- Modelo 100 capital-income net base casillas (e.g. 0389 ganancias patrimoniales,
  0429/0430 saldos netos del rendimiento de capital mobiliario, the
  ganancias/pérdidas saldo casillas). These are capital gains/losses and
  capital-income nets derived from the Modelo 100 capital-income chain, not
  bank-ledger actividad flows; they are out of scope for ledger aggregation.

### Cross-cutting grounding observation (section-scope, pre-existing)

- Modelo 130 actividad-económica casillas 01/02/03 and their bindings all cite the
  pago-fraccionado computation provision (`rd-439-2007:art-110` and the
  accompanying retenciones/orden refs) rather than the article that establishes
  deductible gastos and rendimiento de actividades económicas in estimación
  directa (`ley-35-2006:art-30`/`art-28`, both present in the legal catalogue).
  Article 110.2 is a defensible binding provision (it defines the pago-fraccionado
  base as ingresos minus gastos), so this is a grounding-completeness observation,
  not a fabricated or wrong citation. Correcting it must sweep the section
  coherently — casillas 01/02/03, both income and gasto bindings, and the
  construct legal_refs (the validator requires the construct to cover its members'
  and bindings' refs) — with a bundled-corpus cross-check, so it is a deliberate
  section-grounding pass rather than a casilla-local edit.

### Conclusion

The only bounded-mirror silent-zero base in scope (M130 casilla 02 gastos) is
resolved and verified; the M303 régimen-general bases are an in-flight bounded
mirror owned by a peer. Every other silent-zero base or volume candidate exceeds
a bounded mirror — it needs a new aggregation mechanism, a new classification
axis, or an official-form restructure — and is therefore deferred to an ADR
rather than force-fitted into wrong regulated numbers. This research is the input
to an amendment of the calculation-aggregation taxonomy decision covering the
M303 prorrata annual-volume mechanism and the Modelo 100 annual income
aggregation, and to a separate section-grounding pass for the M130
actividad-económica legal_refs.
