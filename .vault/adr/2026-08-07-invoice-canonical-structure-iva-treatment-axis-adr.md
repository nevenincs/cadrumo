---
tags:
  - '#adr'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a33316f88c4861a22b9ae0e26bc23fae9cf88007fce5979d8b0427a8616055cf'
related:
  - '[[2026-08-06-invoice-canonical-structure-adr]]'
  - '[[2026-08-06-invoice-canonical-structure-lane-discovery-sweep-research]]'
  - '[[2026-08-06-invoice-canonical-structure-research]]'
  - '[[2026-08-07-unstructured-document-ingestion-confirm-boundary-under-declaration-audit]]'
  - '[[2026-07-06-cross-domain-continuity-adr]]'
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

The confirm boundary keeps its refusal-first shape and narrows one of its three decline
cases. Where the document states several rates and every one of them resolves to a
registered Spanish domestic tier on the invoice's issue date, the record resolves to the
ordinary domestic supply treatment rather than to no treatment at all. Where any rate
fails to resolve, where a recargo is present, or where a rate is ambiguous between tiers,
the existing decline stands unchanged.

The resolution stays composed from the two shipped authorities the single-rate path
already uses - the dated rate-to-tier lookup and the single tier-to-category mapping - so
no fourth copy of either table appears. Because the invoice-level category is now used as
a treatment marker on a document whose tiers differ, the operator-facing surfaces that
display the category state that the tiers are carried per line.

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

- **Zero-cuota lines never reach Modelo 303, and this decision does not fix it.** The
  aggregation loop skips every line whose IVA amount is not positive, so an exempt,
  zero-rated or issued-reverse-charge line is dropped before an observation is built -
  measured, and directly contrary to the Axis-A table's own declaration that these
  categories carry a real taxable base feeding the base-only casillas. An exempt line was
  measured to classify correctly and then to be skipped anyway. This is a separate
  under-declaration defect that predates and outlives this record; it needs its own
  investigation, and its prorrata-denominator consequence is unquantified here.
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
