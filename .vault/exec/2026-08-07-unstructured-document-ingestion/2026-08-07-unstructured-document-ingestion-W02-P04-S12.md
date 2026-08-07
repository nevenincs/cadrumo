---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1a5623210f166de068790014c03ca9078fce982ba5e470de544c2ba1b5da7fe5'
step_id: 'S12'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Replace the image-to-fields extractor with `LocalVisionDocumentTranscriber`, emitting `DocumentTranscription` and nothing else.
- Author a transcription-only prompt that names no invoice field, demands verbatim printed forms and headings, and marks an unreadable glyph rather than guessing it.
- Stamp the transcriber identity with origin, model, prompt version and transport.
- Route the router's vision branch through the one semantic-read-and-ground chain the text branch already used.
- Admit `VISION` to `GROUNDABLE_ORIGINS`, the anchor check now having an independently produced transcription to run against.
- Refuse an empty page set and an empty model reply.
- Delete `LocalVisionInvoiceFieldExtractor` and `extract_invoice_fields_from_images` outright, with no bridge.

## Outcome

The vision lane now reaches the same grounding the text lane gets.

The collapse it removes was structural rather than stylistic. One call answered
"what does this page say" and "what does that mean" together, so a wrong result
could not be attributed to either -- and, worse, the anchors came back from the
call that produced the values, leaving nothing independent to check them
against. That is why the provenance record carried a self-reported-anchor flag
at all, and why a self-reported anchor can never read as verified: a fabricating
model is self-consistent too.

Split into two calls, the anchor check becomes a real external check on this
lane for the same reason it always was on the text lane -- a different reader
produced the text the anchor is searched in. Stage two is the identical code
path, so a vision-read document now earns the same verdicts, including the role
evidence the prior Step made checkable.

The self-reported invariant survives the change without being weakened, and the
reason it survives is that it keys on the FLAG rather than on the origin. Had it
keyed on the origin set, admitting `VISION` there would have silently opened it.
That is now asserted rather than assumed.

Where the vision reader genuinely cannot resolve a character it writes an
explicit marker. That is a legitimate outcome and costs one field; an invented
character costs a filing silently, because a fabrication inside the
transcription would anchor perfectly against itself.

## Verification

    uv run --no-sync pytest src/cadrumo/llm/tests/test_evidence_draft_vision.py -n0 -p no:cacheprovider -q -m unit
    46 passed (within: 1 failed, 46 passed in 49.99s under mutation; unmutated run green in the suite below)

    uv run --no-sync pytest src/cadrumo/llm/tests src/cadrumo/application/ledger/tests src/cadrumo/entrypoints/cli/tests -n0 -p no:cacheprovider -q -m unit
    2 failed, 1902 passed, 2953 deselected, 1 warning in 347.45s

Both remaining failures are `test_waist_end_to_end_accounting.py` Hop 7, failing
inside `bundled_authority()` on `modelo 303 revision 2023-y-siguientes:
calculation-completeness manifest omits non-internal calculation-closure casilla
ids: '15', '152'`. That is a peer's uncommitted M303 registry work; this Step
touches no registry file and the failure precedes any code under it.

Mutation, from outside the repository:

    S13_MUTATION=let_the_vision_stage_interpret ... -p s12_s13_s14_mutation
    1 failed, 46 passed in 49.99s
    reds: test_the_transcription_module_reaches_no_field_grounding_symbol

The mutation injects a field-grounding import into the source the structural
gate reads, so the AST walk is shown to detect rather than merely to run. The
walk is an AST walk and not a text scan deliberately: this module's own prose
discusses the interpretation stage it no longer performs, so a substring search
would report a violation that is not there -- and, tuned around that, would miss
a real one.

## Notes

The vision transcriber has no rate-provenance stamp, and should not: stage one
compiles no rates, so a stamp naming them would cite an authority its prompt
never consulted. The rate-provenance gate was re-pointed at the semantic stage,
which is where the rates now reach.

That removed the vision lane's only transport-bearing stamp, which a consent
withdrawal enumerates cloud-derived artefacts by. A transcription is a durable
artefact derived from the document, so the transport is now folded into the
transcriber identity instead. Without that the artefact most needing re-derivation
after a withdrawal would have been the one the survey could not see.
