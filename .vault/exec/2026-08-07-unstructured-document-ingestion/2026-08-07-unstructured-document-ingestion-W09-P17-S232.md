---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:4ef8fc57b6de5873b84997e0690956a024253d8120e50d681f4095e359de67e1'
step_id: 'S232'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec W09.P17.S232

## Scope

- `dev`

## Description

- Answer the row's third question first, since it narrows the other two before they are asked.
- Measure whether the extractors can emit coordinates at all, and whether those coordinates actually separate the two parties rather than merely existing.
- Measure the cost of preserving geometry on the cached-transcription path, at the models and the namespace that would have to change.
- Measure the alternative the row did not ask about: consuming the geometry at extraction time and discarding it.
- Land the measurement in the existing harness so the size is re-derivable rather than quoted, with controls carrying discrimination and the corpus lane carrying non-vacuity.
- Report a size and a recommendation. No pipeline was changed.

## Outcome

**The recommendation is to consume the geometry at extraction time and preserve none of it.** That was not one of the shapes the row proposed, and it is the measurement that produced it rather than a preference.

**The scope is much smaller than the row's framing.** Co-location is never consulted for a structured record, and the reason is structural rather than the one first reported here. The draft path RETURNS on a structured shape before grounding is reached, at `src/cadrumo/application/ledger/_evidence_draft.py:836`, and the structured builder `_extract_invoice_fields_from_structured_record` calls neither `ground_draft_against_transcription`, nor `resolve_party_attribution_by_colocation`, nor `stamp_unverified_party_attribution` — measured on the source, not read off the prose. There is also nothing to co-locate against, because the four structured shapes are read exactly and never transcribed. A second, independent guard would clear the stamp if such an envelope arrived by another route: `ATTRIBUTION_ESTABLISHING_ORIGINS` at `src/cadrumo/application/ledger/_party_attribution.py:127`, exported on the package facade and consumed once at line 235, carries `EXACT_STRUCTURED`.

**The first version of this record cited only that second guard, and a reviewer could not reconcile it.** That was a real imprecision: the set governs whether a value is STAMPED, which is a different question from whether co-location is CONSULTED. The scope arithmetic is unchanged — the 88 XML documents stay out of scope — but it now rests on the mechanism that actually produces it rather than on the one that would only matter if the first had failed. Only prose is in scope. Within prose only one of the two transports can carry coordinates at all, because the vision path returns a model's text and has no geometry to give. Of 302 corpus documents, 88 are XML and out of scope entirely, 121 are images that can never be reached by any amount of geometry work, and 78 are PDFs — of which 69 carry a text layer and 9 are scan-only and therefore route to vision. So the largest single population in the corpus is permanently outside this remedy, and that should be read before any size.

**The coordinates exist and they separate the parties.** Measured on a real two-column invoice rather than inferred from the API: pdfplumber reports `EMISOR` at x0=40 and `DESTINATARIO` at x0=320 on a 595-point page, on the same baseline. Sixteen corpus PDFs carry a detectable two-column header, and the gap between the columns is 0.421 of the page width in every one of them.

**That identical figure is a warning, not a reassurance.** All sixteen come from one generated template, so the separation is real while its consistency is a property of how the corpus was built. This measures that geometry CAN segment the layout; it cannot measure how robust a column-detection rule would be, because there is no layout diversity here to be robust against. Any threshold fitted to this population would be reporting its own tuning.

**Preserving geometry is the expensive shape.** Both the in-memory transcription and its cache entry forbid extra fields, so a geometry field is a schema change on two strict models. The cache namespace is versioned and classified FINANCIAL, so the field forces a version bump that invalidates every cached transcription — and re-reading is free on the text-layer path and a paid model call on the vision path, which is the path the cache exists to protect. The payload is the deciding number: a minimal per-word box set, three rounded values and nothing else, serializes to a median 2.96 times the size of the text it accompanies, up to 3.40. That is not a fraction of the record, it is multiples of it, in encrypted storage, for the most sensitive record the ledger holds. Under the pre-release regime the bump costs a deletion today and an upgrader after the compatibility checkpoint.

**And none of that cost buys anything the cheaper shape does not.** Rendering the same words column by column at extraction time, and discarding the coordinates, flips the resolver from unpartitionable to partitionable on 16 of 16 two-column PDFs, with a naive page-midpoint split and no tuning. The resolver is unchanged, no model gains a field, no namespace is bumped, no payload grows and nothing new is persisted. The row asked whether the pipeline can PRESERVE geometry; the answer is that it does not need to.

**Size.** The change is confined to the text-layer transcriber: group extracted words by visual row and by side of a column boundary before joining them, instead of by row alone. It touches one extraction path, adds no field to any persisted model, and requires no cache invalidation. What it does need, and what this sizing cannot supply, is a corpus with more than one two-column layout to establish the boundary rule on — so the honest sequence is to acquire layout diversity first and fit the rule second, rather than shipping a midpoint split that works on every document anyone has looked at because they were all rendered by the same generator.

## Verification

    uv run --no-sync pytest dev/ingest_harness/tests -n0 -q
    32 tests ran; 13 DESELECTED by -m 'unit and not external_tool and not os_keychain'
    32 passed, 13 deselected in 3.26s

    uv run --no-sync pytest dev/ingest_harness/tests -n0 -q -m integration
    13 tests ran; 32 DESELECTED by -m 'integration'
    13 passed, 32 deselected in 3.16s

    uv run --no-sync ruff check dev/ingest_harness/   All checks passed!
    uv run --no-sync ty check dev/ingest_harness/     All checks passed!

The controls carry discrimination and the docstring says so, because a sizing whose probe can only produce one answer reports its own behaviour. The positive case flips a two-column header; the negative case is a stacked header that partitions in BOTH renderings, so the flip is the layout changing rather than the column-aware branch always answering yes. A third control asserts the rendering itself — today's genuinely emits both labels on one line, the column-aware one genuinely separates them, and both contain the same words, so a rendering that dropped one could not pass by partitioning for the wrong reason.

**One assertion of mine was wrong and the run caught it.** I asserted that an empty word list yields a payload ratio of zero. It does not: an empty box list still serializes as two bytes, so the ratio is small and positive. The function's zero is reserved for having no text to divide by. Corrected to assert the measured relation rather than the tidy one, because a measurement quietly reporting zero for a real payload is exactly what this package refuses — small is not absent.

## Notes

No pipeline code was changed and none should have been. The row asked for a size and a recommendation, and building the column-aware renderer would have pre-empted the decision this record exists to inform.

The measurement went into the existing ingestion harness rather than a new module, for the same reason the ceiling did: that package's contract is that every figure is re-derived rather than inherited from prose, and a sizing whose numbers cannot be re-run is the stale-denominator failure it was built to prevent.

A sweeper committed the module, its controls and the facade wiring mid-flight; all three were verified present at HEAD before this record was written.

The corpus figures were taken against the external pinned key. The 16-of-16 result and the 0.421 column gap are properties of a single generated template and are reported as such rather than as a general fact about invoices.

Both lanes are covered for this package.
