---
tags:
  - '#adr'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a6ce59feb885487429e9cac1a6b6daeeb7f515bb41e1ec2aad6686567cc32349'
related:
  - '[[2026-08-06-invoice-canonical-structure-adr]]'
  - '[[2026-08-06-invoice-canonical-structure-lane-discovery-sweep-research]]'
  - '[[2026-08-06-invoice-canonical-structure-research]]'
  - '[[2026-08-07-unstructured-document-ingestion-confirm-boundary-under-declaration-audit]]'
  - '[[2026-07-06-cross-domain-continuity-adr]]'
  - '[[2026-08-07-invoice-canonical-structure-iva-treatment-axis-research]]'
---
# `invoice-canonical-structure` adr: `Where the IVA treatment axis lives on a multi-operation factura` | (**status:** `proposed`)

## Problem Statement

`Invoice.iva_category` is single-valued. The evidence-confirm boundary therefore
declines to resolve a category for a document charging two rates, leaving the record
with no declared IVA treatment. That decline is safe but expensive: the decomposition
contract refuses an uncategorised record, and the renta sales-evidence path then counts
the row's bank cash instead of its ingresos integros, dropping base, cuota and
retencion together.

The decision cannot be taken as a bug fix, because the enum member the record would have
to store names a rate tier, and Spanish invoicing law models one factura as carrying
several tiers AND several treatments. What the axis is, and where it lives, has to be
settled before any resolution is written.

## Considerations

- Every production consumer of `Invoice.iva_category` is treatment-only, measured rather
  than reasoned. The complete set is three: the decomposition contract, which reads only
  the Axis-A presence columns; the Modelo 349 clave derivation, whose table is keyed
  exclusively on intra-community members and holds no domestic key; and the retencion
  routing, which reads only the retencion role.
- The three domestic rated members are component-identical. They are produced by one
  shared factory in `src/cadrumo/domain/iva/_components.py` and differ only in which tipo
  article they cite. A two-rate invoice tagged domestic-general and the same invoice
  tagged domestic-reduced were measured to decompose identically: grounded, base 1500.00,
  cuota 260.00, cash 1760.00, with identical Axis-A rows.
- Modelo 303 never reads the invoice-level category. The aggregation loop in
  `src/cadrumo/application/aggregation/_modelo_bindings.py` iterates the invoice lines and
  derives each observation's category from the line's own rate, measured: a 21 percent
  line yields domestic-general and a 10 percent line domestic-reduced on the same
  invoice. The registry selectors naming domestic-general match that line-derived
  observation, not the invoice field.
- The category-to-tier reverse map has zero production call sites. Nothing anywhere reads
  a tier back off a category.
- The tier-named members are nevertheless load-bearing elsewhere and cannot be removed. A
  ledger transaction has no lines, so its category must carry the tier, and the IVA
  ledger observation's category is the token registry selectors match as strings.
- RD 1619/2012 art. 6.1.g requires the invoice to state "el tipo impositivo o tipos
  impositivos, en su caso, aplicados a las operaciones" - the reglamento contemplates
  plural tipos on one factura, which is the legal form of "the tier belongs to the
  operation, not the document". Verified against the bundled corpus file
  `rd-1619-2012-art-6.html`.
- The same article refutes the stronger claim that treatment is invoice-level and
  single-valued. Art. 6.2 requires the base to be stated separately per operation in
  three cases, and only one is about rates: exempt operations mixed with non-exempt
  (6.2.a), operations where the destinatario is the sujeto pasivo mixed with operations
  where they are not (6.2.b), and operations subject to different tipos (6.2.c). Spanish
  law explicitly contemplates a single factura mixing exempt with rated supply, and
  reverse-charge with ordinary supply. A single invoice-level treatment field cannot
  describe either of those two compliant documents.
- A wrong treatment is caught; a wrong tier is not. Tagging the two-rate invoice
  domestic-exempt was measured to raise the cuota-contradicts-category defect, while
  either rated tier passes silently. The existing guard defends the treatment axis and is
  indifferent to the tier axis, which is what the axis separation predicts.
- Overloading the category enum with a second dimension has already been ruled against.
  `2026-07-06-cross-domain-continuity-adr` rejected adding a criterio-de-caja member on
  the reasoning that a cash-accounting sale still needs its own IVA treatment, and added
  an independent cash-accounting axis instead.

## Considered options

1. **Resolve a multi-rate domestic document to the ordinary domestic treatment, keep
   declining mixed treatment.** Closes the measured money loss on the case that actually
   occurs, using a member whose downstream effect is measured identical to the
   alternatives. Cost: the stored token names a tier the document only partly carries, so
   an operator reading the record sees a general-rate label on a half-reduced invoice,
   and nothing catches it. Kept as the decision.
2. **Move the treatment axis onto the invoice line.** The only option that can describe an
   art. 6.2.a or 6.2.b factura, and the shape the law points at. Rejected for now, not on
   merit: it changes the decomposition contract's key, the Axis-A lookup's caller shape,
   and the three invoice-level consumers at once, and the case it uniquely unlocks is not
   the case costing money today. Named as the direction, deferred to its own record.
3. **Mint a treatment-only domestic member.** Would let the record state "ordinary
   domestic supply, tier on the lines" without asserting a tier. Rejected: the category
   enum is shared with the ledger-transaction surface, where a tier-less domestic member
   has no tier to fall back on and would drop out of the per-tier bindings silently; and
   it repeats the member overloading `2026-07-06-cross-domain-continuity-adr` rejected.
4. **Leave the decline and fix the renta path to trust a rated-but-uncategorised
   invoice.** Attacks the cost directly and touches no taxonomy. Rejected: the renta path
   would read grounding out of the rate while the decomposition contract still reports
   the record ungrounded, so two consumers would disagree about whether the same invoice
   is interpretable.

## Constraints

- The resolution must stay date-aware. The declared-rate lookup takes a fraction, not a
  percentage, and answers against the rate records in force on the invoice's own issue
  date; a tier's rate changes by statute, so resolving a 2024 document against today's
  table answers about a rate it was never charged at.
- The recargo decline is independent of this decision and must survive it. A
  recargo-bearing supply grounds under both the ordinary domestic and the recargo
  category, so a wrong pick is caught nowhere; that ambiguity is not resolved here.
- Option 2 depends on the invoice aggregate's line model, which is stable, but its reader
  side is not complete: see the first consequence below.

## Implementation

Written against the confirm boundary as it now stands, which was rebuilt after this record
was first drafted; the research of the same stem carries the audit. The boundary no longer
resolves a category from a rate. It resolves a rate TIER at the reading stage and hands it
to a classification authority whose criteria assembly feeds a rule table, and the category
comes from that authority and from nowhere else on the path. A declared document code and
the rate-tier axis are both INPUTS to the table rather than rival deciders, and a
contradiction between them resolves to no category as a review item.

The multi-rate decline survived that refactor unchanged: the tier resolver still returns no
tier for a document whose breakdown carries more than one entry, the criteria then carry no
tier, and the rule table refuses the domestic branch that needs one. So this decision is
unaffected in substance and changes only where it lands.

What follows from it is that the domestic branch must be reachable for a document that
charged several registered domestic tiers. The tier axis is the wrong place to express
that - a multi-tier document has no single tier and inventing one is the guess this record
rejects - so the signal belongs beside the tier as a distinct input stating that every rate
resolved to a registered domestic tier without settling which. The rule table then decides
the ordinary domestic treatment on the same evidence it already uses, and the recargo,
unregistered-rate and ambiguous-rate declines stay exactly as they are.

Nothing changes on the Modelo 303 path, which already reads tiers per line, or in the
Axis-A table, whose rated rows are already tier-indifferent.

## Rationale

The knockout is that the tier choice is measured to be downstream-immaterial while the
treatment choice is measured to be guarded. Every consumer that could distinguish the
general from the reduced domestic member on an invoice was enumerated and none does; the
one consumer that reads tiers reads them from the lines, where the law also puts them. So
resolving a two-rate document to an ordinary domestic treatment cannot mis-declare
anything to AEAT - the figures it produces were reproduced identically under both
candidate members - while continuing to decline demonstrably does, through the renta
path.

Option 2 is the better model and this record says so plainly. It is not chosen now
because its blast radius would be paid for a case that is real in law but not yet costing
money, and because taking it under time pressure would change the decomposition
contract's key while the confirm boundary is still moving.

The honest limit of this decision is that it improves the common case by accepting a
label that is imprecise on the uncommon one. That trade is defensible only because the
imprecision is invisible to every filing surface and visible only to the operator.

## Consequences

- **Zero-cuota lines never reach Modelo 303, and removing the guard alone would not fix
  it.** The aggregation loop skips every line whose IVA amount is not positive, so an
  exempt, zero-rated or issued-reverse-charge line is dropped before an observation is
  built - measured, and contrary to the Axis-A table's own declaration that these
  categories carry a real taxable base feeding the base-only casillas. The guard is not
  the whole cause, and deleting it delivers nothing: the loop builds observations through
  the standard-case line helper, which classifies from the RATE SLOT, so an exempt line
  becomes domestic-exempt at rate kind exempt while the casilla 59 and 60 bindings select
  on intra-community-supply and the two export categories at rate kind zero. Verified on
  both the 2009 and 2023 revisions - such a line misses on both axes, and no Modelo 303
  selector absorbs domestic-exempt or domestic-zero, so a stray observation routes
  nowhere rather than into a wrong casilla. Delivering that base to casillas 59 and 60
  requires constructing the observation from the invoice's own category, the direct
  construction the helper's own docstring points at, which is a second and independent
  reason the treatment axis matters. Tracked separately from this record.

  The prorrata-denominator consequence this record first raised is REFUTED, traced end
  to end in the research of the same stem: both prorrata volume casillas are manual
  inputs that no binding populates, and the percentage is computed from them, so the
  observation rollup never fed the deductible percentage and losing observations could
  not inflate it. What the omission actually broke was the divergence DETECTOR, and in
  the direction that matters - an operator who under-declared exempt volume matched an
  equally understated rollup and the detector stayed silent. Restoring the lines closes
  that. It also newly mis-routes an exempt-slot intra-community supply into the
  sin-derecho bucket, which is the same rate-slot-versus-category root cause and is
  recorded there.
- The record gains a treatment for the common mixed-rate document, so the decomposition
  grounds it and the renta path stops substituting bank cash for ingresos integros.
- The stored category becomes, for this one construction, a treatment assertion carried on
  a tier-named token. Future readers must not infer the invoice's rate from it. The three
  domestic rated members are now formally treatment-equivalent at invoice level, a
  property no gate enforces.
- The art. 6.2.a and 6.2.b facturas - exempt mixed with rated, reverse-charge mixed with
  ordinary - remain undescribable and continue to decline. That is now a known, named gap
  rather than an unexamined one.
- Option 2 stays open and is cheaper than before, because this record establishes by
  measurement which consumers would have to move.
