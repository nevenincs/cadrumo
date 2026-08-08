---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:821f358bc7f78e72fd003c65c5ca9719f486fbd090910f4b523de5926b25b9e5'
step_id: 'S252'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Sweep for the campaign's dominant defect stated as a searchable pattern, beyond this feature: a rule PROVEN IN TESTS and WIRED TO A FIELD THAT IS EMPTY in exactly the cases the rule exists for. Two separate defects on one row shared it and neither is country-specific. The declared-relief guard read the resolved country code, empty for precisely the uncatalogued codes its exemption is for, while its own cases supplied the status directly. The country advisory had the identical defect, reading the resolved field while its fixtures set that field by hand, so it had never fired from a real document in its life. Both were invisible to a green suite because the tests entered BELOW the wiring. The generalisation: a gate that supplies its subject directly proves the RULE and says nothing about REACHABILITY, and the tell is a fixture setting a field no production path populates. Sweep other advisory and guard surfaces for that tell. Pairs with the fixture-provenance audit, which asks whether a fixture's SHAPE is one a producer emits, where this asks whether the fixture's INPUT arrives the way production supplies it

## Scope

- `src/cadrumo`

## Description

- State the invariant independently of the two instances that motivated it, and
  build the sweep instrument from the invariant rather than from their shape.
- Walk every decision surface in the package for fields it reads that no
  production path writes.
- Confirm the one live instance end to end against the real parser, with the
  control that supplies the missing term.
- Report two further candidates that need an owner's ruling rather than a fix.

## Outcome

The invariant, stated without the country axis: a decision surface reads field
F to decide whether to act, and no production writer populates F in the cases
that surface exists for. The tell is a fixture setting a field no production
path populates, and the reason a green suite cannot see it is that the tests
enter BELOW the wiring -- they prove the rule and say nothing about
reachability.

**One live instance, verified, and it blocks.** The arithmetic-closure check
tests `total = base + cuota + recargo + suplidos`. Nothing anywhere in the
package reads suplidos: not the e-invoice parser, not the on-host reading
schema, not the text lane. The role exists -- `FieldRole.SUPLIDO_AMOUNT`, whose
own declaration says such roles must be recognisable "even where no importer
column exists for them yet" -- and the draft field exists and is documented. The
producer is what is missing.

Facturae is where that lands, because it models suplidos as
`ReimbursableExpenses` and folds them into `InvoiceTotal`, which is exactly the
element the parser reads as the printed total. So a CORRECT Spanish invoice
carrying suplidos arrives with a total the components cannot reach, the closure
identity is short by exactly the suplido, and `ARITHMETIC_CLOSURE` maps to
`CLOSURE_DISCREPANCY`, which blocks the confirm. The operator is told the
document "carries one this draft cannot represent" -- honest wording for a
refusal that should not be happening.

That is the over-refusal direction, which nothing in this apparatus watches, and
it reaches the Spanish national format rather than an edge case.

**Two further candidates, measured but not ruled on.** Both are aggregations
consuming records nothing constructs, so they are the same invariant one level
up -- a surface wired to a container that is empty in production rather than to
a field:

The Modelo 720 aggregation is called from the service on
`command.foreign_asset_observations`, which defaults to an empty tuple, and no
production code constructs a `ForeignAssetIngestObservation` at all. The
contributor flag derived from it is therefore always false.

The Modelo 131 agrarian income ledger filters on `Transaction.tipo_actividad`
and `Transaction.concepto_ingreso`. Nothing writes either field -- no CLI
surface, no importer, no application path. Both are declared operator-declared
facts with no way for an operator to declare them, so that filter admits nothing.

These are reported rather than fixed because the measurement cannot distinguish
a defect from a surface deliberately built ahead of its producer, and this
campaign has an explicit vocabulary for the second. The owner of each has to say
which it is. If either is meant to be live, the consequence is the
under-declaration direction: an aggregation that sees nothing declares nothing.

Modified files: none. This row is a sweep; the instrument lives outside the
repository and every finding is reported for its owner rather than patched here.

## Verification

The instrument was rebuilt once, and the first version is worth recording because
it failed in the way the row warns about. Version one asked only "written in
tests, never in production" -- half the invariant -- and returned 135 candidates,
almost all fields populated through `model_validate` over a parsed mapping:

    models: 1675   declared fields: 3212
    CANDIDATES (written in tests, never as a production keyword/update key): 135

Version two intersects both halves, walking decision surfaces for the fields they
READ and reporting only those whose writers are tests:

    decision surfaces scanned; fields they read: 937
    CANDIDATES (read by a decision surface, written only in tests): 11

Eleven is a readable list; each was read rather than believed, and seven were
false positives whose producer is a `model_validate` over registry TOML, a
parsed payload, or a persisted record.

The live instance, driven through the real parser over a Facturae specimen
carrying a reimbursable expense of 30.00, the corpus file never written to:

    taxable_base   : 200.00
    iva_amount     : 42.00
    grand_total    : 272.00   (InvoiceTotal, suplidos included by the format)
    FINDING arithmetic_closure: expected=242.00 observed=272.00
      shortfall = 30.00  (exactly the stated suplido)

    with the suplido present, findings: []

The last line is the control and it is what makes this a wiring finding rather
than a rule finding: supplying the term the reader cannot supply makes the
finding vanish, so the identity is correct and only its fourth input is
unreachable.

The blocking consequence is read off the shipped mapping rather than asserted:
`DraftDiscrepancyKind.ARITHMETIC_CLOSURE` maps to
`ConfirmationBlockReason.CLOSURE_DISCREPANCY`.

Semantic search was run before the sweep and again per finding. The after-pass on
suplidos is what closed it: every hit for the concept under other names is a
CONSUMER of a suplido once it exists -- the ledger expense surfaces, the invoice
model, the field role -- and none is a producer. The Facturae element name itself
appears nowhere in the package.

## Notes

The first probe could not run: the draft assembler imports the
deterministic-findings module, which loads the modelo registry, and a peer's
registry fragment was mid-write with a duplicate key. The measurement was
isolated onto the parser instead, which reads every amount in the identity, so
the unrelated breakage was removed without weakening it. Not reported as a
failure -- it is transient peer work.

The discriminator that makes this sweep tractable is worth stating for whoever
runs the next one: the question is whether the field is empty IN THE RULE'S OWN
CASES, not whether it is often unset. "Often unset" is the obvious reading and
produces a large list of nothing -- version one of the instrument is that list.

And a positive finding here is not always "this rule never fires". It can be
"this rule never fires, and something behind it is wrong in a way nobody has
been able to observe" -- which is what happened on the country axis, where
wiring one rule up made a latent over-spare behind it live. A sweep that reports
only the first misses why the second matters.
