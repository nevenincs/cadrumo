---
tags:
  - '#adr'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
related:
  - "[[2026-06-04-m130-casilla-15-override-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-05-19-modelo-130-relation-regression-adr]]"
  - "[[2026-06-13-first-filer-attestation-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace modelo-130-pagos-fraccionados-carry with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->


# `modelo-130-pagos-fraccionados-carry` adr: `casilla 05 cumulative pagos-fraccionados carry (target-relative same-ejercicio sum)` | (**status:** `proposed`)

## Problem Statement

<!-- Briefly describe the architectural problem or concern.
Describe why the ADR is being persisted. Is this a new feature? Result of an audit? -->

Modelo 130 (IRPF pago fraccionado, estimacion directa) accumulates from the
start of the ejercicio: casilla 01 (Ingresos) is a year-to-date cumulative sum,
so casilla 04 (Importe del pago fraccionado) is the cumulative 20% pago
fraccionado on the YTD rendimiento neto. To stop the taxpayer from re-paying
what each prior quarter already paid, the official resultado of apartado I nets
out the prior payments: casilla 07 = casilla 04 - casilla 05 - casilla 06
(AEAT instrucciones, casilla 07: "restar el importe de la casilla 05 y 06 al
importe de la casilla 04"; RD 439/2007 art. 110). Casilla 05 ("Pagos
fraccionados anteriores") is the deduction that carries the prior quarters
payments forward.

In the committed registry, casilla 05 is `input_kind = "manual"` with no
binding (`casillas/0001-casillas.toml`, casilla id `05`). A cumulative
2T / 3T / 4T `calculate` therefore leaves casilla 05 at zero, casilla 07 fails
to deduct the prior payment, and the resultado over-states the amount owed.
Operator testing reproduced this as a silent over-payment: the engine returns a
higher resultado than the law requires, and (before Stage 1) emitted no finding
- a `no-silent-under-declaration` sibling defect in the over-declaration
direction.

Stage 1 already shipped (commit `75504fb4e`): a non-blocking
`CalculationSourceDiagnostic` (reason `prior_payment_not_deducted`) fires when a
non-first trimestre has a positive casilla 01, a zero casilla 05, and a real
prior-trimestre M130 filing for the same ejercicio in the local catalogue. That
made the contradiction visible but left the operator to enter the number by
hand. This ADR scopes Stage 2: compute casilla 05 from the prior filings so the
deduction is populated automatically and the resultado is correct.

The decision needs an ADR rather than a one-line binding because the quantity
casilla 05 carries is a cumulative recurrence - a sum over a target-relative
span of prior quarters - and the existing same-modelo carry primitive
(`_bindings_previous_filing.py`) can reach a single prior period (offset -1) or
sum a static list of periods, but cannot sum "every prior quarter of this
ejercicio" because that span shrinks and grows with the target period
(2T to {1T}, 3T to {1T,2T}, 4T to {1T,2T,3T}). The exact quantity summed was
also an open AEAT question on entry to this work; it is now resolved (see
Rationale) and is not the naive "sum of prior casilla 07".

## Considerations

<!-- Key factors, constraints, requirements. Tech/libraries considered. -->

The AEAT-grounded accumulation rule (resolved). The official Modelo 130
instrucciones (AEAT sede, `aeat-modelo-130-instructions`) define casilla 05
verbatim:

> "Aqui debe reflejarse la suma de las cantidades positivas consignadas en la
> casilla 07 de las autoliquidaciones, modelo 130, correspondientes a los
> trimestres anteriores del mismo ejercicio, minorada en el importe de la suma
> de las cantidades consignadas en la casilla 16 de las citadas
> autoliquidaciones."

Read precisely, for a target quarter N within ejercicio Y:

> casilla 05(N) = SUM over prior quarters q before N in Y of max(0, casilla 07_q)
>                 minus SUM over the same q of casilla 16_q

Two non-obvious facts the brief did not assume and the registry must encode:

- The summed casilla-07 term is the positive part only - "las cantidades
  positivas consignadas en la casilla 07". A prior quarter whose casilla 07 was
  negative contributes 0, not its negative value. (A negative casilla 07 travels
  a different rail: it lands in casilla 15 of the next quarter via the
  already-shipped `saldo-negativo-fin-periodo` carry - see the casilla-15 ADR.)
- Casilla 05 is reduced by the sum of prior casilla 16 (Deduccion por inversion
  en vivienda habitual) of those same prior filings. This minoracion is a
  load-bearing term, not a rounding detail: omitting it over-states the
  deduction and under-pays.

Existing carry primitive shape. `resolve_previous_filing_binding_values`
(`_bindings_previous_filing.py`) already supports `aggregation = { op = "sum" }`
over multiple resolved source values, and the `_PreviousModeloSelector` already
supports `source_periods` (a static tuple) and `source_casillas` (multiple
casillas per filing). What it does not support is a target-relative span:
`source_period_offset_from_target` derives exactly one anchor period from one
integer offset (`_period_offset_math.apply_period_offset`), and `source_periods`
is a fixed list that cannot encode "all quarters strictly before the target".
The casilla-15 binding (`modelo-130-resultados-negativos-anteriores`) reaches
exactly one quarter back (offset -1, `op = "copy"`); casilla 05 must reach back
across an expanding set and sum.

Prior-quarter casilla 16 availability. The minoracion term requires that each
prior filing casilla 16 be present in the persisted observation. Casilla 16 is
`input_kind = "manual"`; the cross-period carry reads it from the stored
`CasillaObservation` set of each prior M130 revision. Where a prior filing
genuinely had casilla 16 = 0 (the common case), the term is a no-op; where it
was non-zero, it must be subtracted.

Provenance and grounding discipline. Per `registry-calculation-legal-grounding`
and `no-tautological-calculation-tests`, casilla 05 value and its test oracle
must be grounded in AEAT authority, not hand-computed from the same formula. The
accumulation rule above is grounded in the AEAT sede instrucciones text and must
be cited on the binding/formula `source_citations` with `required_text` drawn
from the verbatim quote.

## Constraints

<!-- Technical limitations: depends on non-mature library, frontier feature, requires rigorous research. Frontier risk, e.g. technology is new and falls outside the implementing model training cutoff. List blocking constraints and gaps needed for reliable implementation; evaluate how stable parent features are. -->

- Primitive gap is the blocker. The single-offset / static-period selector
  cannot express the target-relative prior-quarter span. Stage 2 cannot ship as
  a pure-data binding under the current selector grammar; it requires either a
  selector extension (a target-relative span operator) or a synthetic computed
  carry casilla fed by per-quarter copy bindings. This ADR chooses between them
  below; the chosen path is a bounded, additive extension, not a rewrite.
- The positive-part-of-07 and minus-16 terms are mandatory. A naive sum-prior-07
  binding would bake a wrong number into every cumulative filing (it would carry
  negative prior-07 values and skip the casilla-16 minoracion), violating
  registry-calculation-legal-grounding. The chosen shape must compute
  max(0, 07_q) per prior quarter and subtract SUM 16_q.
- Depends on the cross-period observation availability already used by the
  casilla-15 carry. This work inherits, and must not regress, the same-ejercicio
  (max_year_delta = 0) reach and the absent-by-design first-quarter path proven
  by modelo-130-relation-regression and the casilla-15 carry. Those parent
  surfaces are stable (both shipped, both gated).
- First-filer / alta-quarter null-not-error. The first quarter of activity has
  no prior pago fraccionado, so casilla 05 = 0 and this MUST be a clean Decimal
  zero with provenance, never an error or a blank that trips a coverage
  validator. This must reconcile with the in-flight first-filer attestation ADR
  and the deadline-engine pre-alta semantics (see Implementation S4).
- One canonical mechanism (per calculation-source-canonical-mechanism).
  Same-modelo within-ejercicio carry is the previous_filing family
  (max_year_delta = 0); this work must enroll under that row, not invent a
  parallel relation or a second resolver. The casilla-15 carry is the precedent
  for the row; casilla 05 is the summing sibling.

## Implementation

<!-- A high-level overview (not a plan) of HOW and WHAT will be implemented. Do not add code. -->

### S1 - Canonical mechanism and the chosen extension

The carry is same-modelo, within-ejercicio (source_modelo = 130,
max_year_delta = 0), so per calculation-source-canonical-mechanism it belongs to
the previous_filing family - the same row the casilla-15 saldo-negativo carry
occupies. The mechanism does not become a relation.

The primitive must be extended to express a target-relative prior-quarter span.
Two candidate shapes were weighed:

- Option A - synthetic computed carry casilla plus per-quarter copy bindings.
  Mirror the casilla-15 saldo-negativo-fin-periodo pattern: introduce a synthetic
  computed casilla per prior-quarter slot, copy each prior quarter max(0,07) and
  16 individually, then express casilla 05 as a formula summing them. Rejected:
  the slot count is target-dependent (4T needs three prior slots, 2T needs one),
  so this either over-provisions fixed slots (wasteful, and the empty slots trip
  coverage at 1T/2T) or needs per-period registry fragments - exactly the
  static-list dead end the primitive already has.

- Option B (chosen) - generalise the previous_filing selector with a
  target-relative span operator. Add a selector mode that resolves to the set of
  all same-ejercicio quarters strictly preceding the target - conceptually
  source_period_offset_from_target in {-1, -2, -3} intersected with same-year
  quarters, bounded by max_year_delta = 0. The existing
  required_period_anchors_for_target already returns a tuple of
  (year_delta, period) anchors and the resolver already loops over them and sums;
  the extension is to make a new selector mode produce the full preceding-quarter
  span rather than one offset anchor. The per-anchor value is max(0, casilla
  07_q) and a parallel anchor set yields casilla 16_q; the binding aggregation is
  op = sum, and casilla 05 value is SUM max(0,07_q) - SUM 16_q.

Option B is the smaller, canonical extension: it reuses the existing
multi-anchor resolve+sum path, keeps the carry inside the one previous_filing
resolver enrolled in the live mesh, and adds no new resolver/source kind (so it
clears no-dormant-source-resolvers and the novel-source gate by construction).

### S2 - The positive-part and minoracion terms

The raw prior casilla 07 can be negative; the rule sums only its positive part.
The cleanest registry shape keeps the source clean and the transform in the
registry expression language already used elsewhere (max and subtract ops, seen
in formulas/0001-formulas.toml). Two sub-shapes are viable and the plan must pick
one with the engine owner:

- (2a) Carry each prior quarter raw casilla 07 and casilla 16, and let a registry
  formula compute SUM max(0, 07_q) - SUM 16_q. This keeps the carried
  observations faithful to what was filed and puts the positive-part and
  subtraction logic in auditable formula expressions. Preferred, because the
  carried evidence is unmodified prior-filing values.
- (2b) Carry a pre-reduced per-quarter max(0, 07_q) - 16_q and sum. Fewer formula
  nodes but the carried value is a derived quantity, weakening the carried
  evidence equals what was filed property.

This ADR records (2a) as the preferred shape and carries (2b) as a fallback for
the engine owner to confirm against the expression-evaluator per-anchor
capabilities; the choice is an implementation detail bounded by the S1 decision,
not a re-litigation of the mechanism.

### S3 - Casilla 07 formula stays as authored

Casilla 07 = 04 - 05 - 06 (modelo-130-resultado-apartado-i) is already correct
and AEAT-cited; it does not change. Stage 2 only makes casilla 05 a populated
input to it. Casilla 05 flips from input_kind manual to input_kind bound (with
the new span binding) - mirroring how casilla 15 is bound. Manual-filing
operators who supply casilla 05 directly retain that ability only if the binding
is modelled as overridable in the same manner the casilla-15 override ADR
established; the plan must reconcile the manual-override affordance with the new
binding (the casilla-15 override ADR is the precedent).

### S4 - First-filer / alta-quarter null-not-error

A true first filer first obligation quarter has no prior same-ejercicio M130
filing. The span operator returns an empty anchor set, the sum over the empty set
is Decimal zero, and casilla 05 materialises as a clean zero with the
absent-by-design provenance marker - exactly the casilla-15 1T path. No prior
filing is required, so the observation-coverage validator must treat the empty
span as satisfied (not as a missing required observation). This is the
null-not-error invariant: a genuine first filer fires nothing, errors nothing,
and gets casilla 05 = 0.

This reconciles with the first-filer attestation ADR
(2026-06-13-first-filer-attestation-adr): that ADR scopes the cross-period
clean-state gate so an attested first filer is not blocked for missing prior
official evidence; this ADR empty-span path is the value side of the same truth -
no prior obligation means no prior payment to deduct. A mid-year alta (e.g.
activity starting 3T) has no 1T/2T obligation, so its 3T span is likewise empty
and casilla 05 = 0; the deadline-engine pre-alta semantics that suppress
pre-activity quarters are the authority for which quarters could have a prior
obligation, and the span operator must intersect its candidate set with the
periods for which a filing obligation actually existed (summing only over
quarters that were owed, which for a normal full-year filer is all prior
quarters, and for an alta filer is the post-alta prior quarters). The plan must
verify the span operator and the pre-alta suppression agree on the candidate
quarter set so neither double-counts nor demands a filing that was never owed.

### S5 - Stage-1 advisory interaction

Once casilla 05 is populated automatically, the Stage-1 prior_payment_not_deducted
advisory should fire only in the genuine residual case (a prior filing exists in
the catalogue but its observation is unreadable/absent so the carry could not
populate). When the span binding resolves cleanly, casilla 05 is non-zero and the
advisory stays silent by its existing precondition (zero casilla 05). The plan
must confirm the advisory degrades to fire only when the carry genuinely could
not run, not alongside a correct carry.

## Rationale

<!-- Brief rationale why architecture descision was made. Reference research findings and grounding reference. -->

The accumulation rule is taken verbatim from the authoritative AEAT sede Modelo
130 instrucciones (the same aeat-modelo-130-instructions source the registry
already cites for casillas 03/04/07/12/17/19), fetched and confirmed twice during
this research at the AEAT sede page
sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-130-irpf______esionales-estimacion-directa-fraccionado_/instrucciones.html
. The verbatim casilla-05 definition pins the two terms (positive-part-of-07 and
minus-16) that a naive binding would miss, satisfying
registry-calculation-legal-grounding. The BOE Orden EHA/672/2007
(BOE-A-2007-6032) approves the form but does not carry the casilla-level
computation text, so the instrucciones page is the correct and sole authority for
the accumulation rule - consistent with the existing M130 source_refs.

Option B (selector span generalisation) is chosen over Option A (synthetic slot
casillas) because the carry is canonically a previous_filing sum
(calculation-source-canonical-mechanism), the multi-anchor resolve+sum path
already exists, and a target-relative span is the minimal grammar addition that
expresses an expanding prior-quarter set without per-period registry fragments or
wasteful fixed slots. It keeps one resolver, one source kind, one mesh enrollment.

## Consequences

<!-- Gains, but framed honestly. Difficulties. Pathways this feature opens. Pitfalls. -->

Gains. Cumulative 2T/3T/4T filings stop over-stating the resultado; the operator
no longer hand-enters casilla 05; the silent over-payment closes at the value
level (Stage 1 closed it at the advisory level). The span operator is reusable:
any future same-ejercicio sum-all-prior-quarters carry can declare it.

Difficulties / pitfalls.

- The selector-span extension touches the shared previous_filing primitive and
  its validators; it must not regress the casilla-15 single-offset carry or the
  modelo-130-relation-regression guarantees. A parity-style regression across
  both carries is required.
- The casilla-16 minoracion term is easy to forget and silently wrong if dropped;
  the test oracle must include a non-zero prior casilla 16 so a
  drop-the-minoracion regression fails loudly.
- The positive-part term must be applied per-quarter before summing, not to the
  sum; a quarter with negative 07 next to a quarter with positive 07 must
  contribute 0 plus positive, not the net. The oracle must include a negative
  prior 07.
- Manual-override reconciliation (S3) inherits the casilla-15 override ADR
  complexity; if not handled, a binding that always overwrites a hand-entered
  casilla 05 would regress operators who legitimately adjust it.

Test oracle (externally grounded, not hand-computed from this formula). The
folleto and the BOE orden carry no worked numeric example, and the AEAT Pre130
service (which auto-fills boxes 05/13/15 from AEAT own records, confirmed on the
AEAT Pre130 help page) is the authority that this carry replicates but is not
directly replayable offline. The oracle is therefore the AEAT instrucciones
accumulation identity applied to a multi-quarter fixture whose per-quarter inputs
are independently fixed: construct prior 1T/2T/3T M130 filings with chosen
ingresos/gastos (and at least one negative 07 and one non-zero 16), let the engine
produce each prior quarter casilla 07 and 16, and assert the 4T casilla 05 equals
SUM max(0,07_q) - SUM 16_q computed from the instrucciones rule (a different code
path than the binding under test). This is not tautological: it pits the carry
binding against the verbatim AEAT textual rule, and a binding that summed raw 07
(skipping max-0) or skipped the minus-16 term would fail. Where a live AEAT Pre130
capture is available under the live-test gate, replaying its auto-filled casilla
05 against the same fixture is the stronger oracle and should be added when the
live surface is functional.

## Codification candidates

<!-- Name durable cross-session constraints as candidates for promotion into a project rule via the codify pipeline phase. An empty section is a positive signal. -->

- Rule slug: m130-casilla-05-is-positive-07-minus-16-cumulative.
  Rule: Modelo 130 casilla 05 MUST be computed as the same-ejercicio sum of each
  prior quarter positive part of casilla 07 minus the sum of those quarters
  casilla 16 (per the AEAT instrucciones verbatim rule); a binding that sums raw
  casilla 07, that omits the casilla-16 minoracion, or that carries negative
  prior-07 values is wrong and must not ship. (Promote only after Stage 2 lands
  and the externally-grounded oracle is green.)

## Open questions (operator)

<!-- Honest open questions carried for the operator. -->

- Casilla 16 availability across prior filings. The minoracion term assumes each
  prior M130 filing casilla 16 is present in its persisted observation set.
  Confirm casilla 16 is always materialised (even as 0) in stored M130 revisions;
  if a prior filing can lack a casilla-16 observation, the carry must treat
  absence as 0 - but that conflates filed-zero with not-captured, which the plan
  should make explicit.
- Manual override of casilla 05. Should an operator be allowed to override the
  computed casilla 05 (e.g. to reconcile against an AEAT Pre130 figure that
  differs)? The casilla-15 override ADR established an override affordance for a
  bound carry; the plan must decide whether casilla 05 mirrors it or is
  carry-only.
- Mid-year alta candidate-quarter set. S4 asserts the span must intersect with
  quarters for which a filing obligation actually existed (post-alta). The exact
  authority binding which prior quarters were owed to the deadline-engine
  pre-alta suppression needs confirmation against the first-filer ADR
  activity-start scoping - specifically whether an alta mid-quarter makes that
  same quarter owed or not, which shifts the span by one.
- Selector-grammar surface. Option B adds a target-relative span mode to the
  previous_filing selector. Confirm with the registry-schema owner that the new
  mode name/shape fits _PreviousModeloSelector validation and the relation-source
  collision gate without a carve-out (it should, as it stays a direct
  previous_filing binding).
- Pre130 replay oracle. Whether and when a live AEAT Pre130 capture of an
  auto-filled casilla 05 can be added as the stronger oracle depends on the live
  capture surface being functional (the first-filer ADR notes the live censo read
  is currently non-functional; the Pre130 surface status needs its own check).
