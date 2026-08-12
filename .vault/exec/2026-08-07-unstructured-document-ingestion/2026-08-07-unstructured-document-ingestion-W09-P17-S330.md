---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2d2f67114474570afb42d217299e9c66a23d251d6d2e78dcf2cd92ef417bcf2d'
step_id: 'S330'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Absorbed regression, found by the row above and fixed with it. The shared ledger CLI harness registered a profile with a declared IVA block but NO fiscal-address postcode, and the filer's own postcode had since become mandatory on every confirm path - it separates the peninsula from Canarias and from Ceuta y Melilla and is never read off an invoice. So the whole evidence-confirm CLI suite refused on an incomplete profile before reaching anything under test, eight cases red on one cause, the same shape and the same scale as the IVA block that preceded it. The harness now declares both, keyed by the production FILER_POSTCODE_FACT_PATH constant rather than a literal. One case genuinely wanted the gap and now constructs it, which exposed two states wearing one name: with NO resolvable profile the confirm carries a review notice, and with a profile that does not declare the postcode it REFUSES typed before any review. The case is re-pointed at the refusal, the reachable one for an operator who has a profile at all, and the negative control gained the assertion it could not make while every session ran incomplete

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Declare the filer's fiscal-address postcode in the shared ledger CLI harness.
- Re-point the one case that wanted the gap at the state an operator reaches.

## Outcome

Delivered, and it was eight pre-existing failures wide before it was one row.

The shared harness registered a profile with a declared IVA block but no fiscal
address. The filer's own postcode had since become mandatory on every confirm
path -- it separates the peninsula from Canarias and from Ceuta y Melilla and is
never read off an invoice -- so the entire evidence-confirm CLI suite refused on
an incomplete profile before reaching anything under test. Every case read an
incomplete-profile refusal in place of the behaviour it asserted.

THIS IS THE SAME EVENT AS THE IVA BLOCK, ONE MANDATORY FACT LATER, and the
harness already carried that lesson in its own docstring: declared centrally
because the cause is the harness rather than any one file. The postcode is now
declared beside it, keyed by the production constant rather than a literal, so
a rename reaches this harness through the type checker instead of through a red
suite nobody can attribute.

ONE CASE GENUINELY WANTED THE GAP, and making it construct its own exposed two
states wearing one name. With NO resolvable profile the confirm completes and
carries a review notice about the filer. With a profile that simply does not
declare the postcode, it REFUSES -- typed, before any review, carrying the
failed condition and its evidence. The case had been asserting the first while
being named for the second.

Re-pointed at the refusal, which is the reachable one: an operator who set up a
profile has one, so the notice path is the rarer state. It is also the stronger
assertion -- a typed refusal naming the fact and distinguishing UNDECLARED from
unreadable, rather than an advisory beside a completed confirm.

The negative control gained an assertion it could not previously make. Its own
docstring had said the filer question was "deliberately not asserted absent
here" because the session declared no postcode, so the item was genuinely open.
With a complete profile it is the control it was always meant to be: neither
question fires on a document that places its counterparty.

## Notes

The full CLI tree is broadly red from unrelated concurrent work -- 663 failures
across it, dominated by suites whose own harnesses never declared the IVA block
at all, by the in-flight error-code rehoming, and by a new IVA category member
landing ahead of its tests. Exactly ONE failure in that run traced to this
change, and it is the case re-pointed above. Owner triage was done by signature
rather than by count.

Worth carrying: this harness has now been the single cause of a tree-wide red
twice, both times because a profile fact became mandatory in production and the
test profile was not swept. The declaration is central, which is right, but
nothing makes a new mandatory fact reach it -- the signal is a suite failing on
a message it never mentions, which is exactly the signal that reads as thirty
unrelated regressions.
