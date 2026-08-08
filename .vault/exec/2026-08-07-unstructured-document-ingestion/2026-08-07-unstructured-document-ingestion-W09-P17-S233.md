---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:178c644ac7c75b3f25c5b67693ba22fc60c70d35499c959fe6862e6b31fe1426'
step_id: 'S233'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S233 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Distinguish an offered-but-unroled anchor from an anchor the document does not carry, the third state the notice surface lacks. The single-competitor branch in the identity-roles module emits an UNANCHORED envelope carrying an anchor the document DOES print, since the candidate verified and only role evidence is missing. That envelope reaches the anchor-not-found notice, which tells the operator the form does not occur in the document's transcription, and that is false. Same class as the refused-anchor work but a different defect: there a refusal was reported as an absence, here an anchored-but-unroled value is reported as anchor-not-found. Three states now share two notices, so the honest shape is probably a fifth notice for offered, not refuted, not corroborated. Note the envelope staying UNANCHORED is deliberate and documented as load-bearing at that site, so the fix belongs in the notice selection rather than the grounding outcome and ## Scope

- `src/cadrumo/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Distinguish an offered-but-unroled anchor from an anchor the document does not carry, the third state the notice surface lacks. The single-competitor branch in the identity-roles module emits an UNANCHORED envelope carrying an anchor the document DOES print, since the candidate verified and only role evidence is missing. That envelope reaches the anchor-not-found notice, which tells the operator the form does not occur in the document's transcription, and that is false. Same class as the refused-anchor work but a different defect: there a refusal was reported as an absence, here an anchored-but-unroled value is reported as anchor-not-found. Three states now share two notices, so the honest shape is probably a fifth notice for offered, not refuted, not corroborated. Note the envelope staying UNANCHORED is deliberate and documented as load-bearing at that site, so the fix belongs in the notice selection rather than the grounding outcome

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Add a fifth notice shape, `anchor_uncorroborated`, to `src/cadrumo/entrypoints/cli/_evidence_field_notices.py` for a printed form the check did not report missing on a field that still did not come through.
- Narrow the not-found branch to a recorded refusal alone, and drop its carried-anchor fallback, which was the path the third state arrived by.
- Carry the envelope's computed reason into the new notice's message and context, since the message can only state truthfully that the printed form is not the problem.
- Set the new key in all four locale catalogues through the locale CLI.
- Reshape the not-found test fixture to the shape the producer really emits, and add the third state as its own fixture.

## Outcome

Three states no longer share two notices. An identifier that verified while nothing
on the page assigns it to a party keeps its anchor, because the check located that
printed form, and it was being told to the operator as a form that does not occur in
the document's transcription. That sends a person to re-read a page which says
exactly what the reader claimed, and closes the question that is actually open.

The fix is in notice SELECTION, not in grounding. The `UNANCHORED` outcome at that
site is deliberate and documented as load-bearing, so changing it to make the
message fit would have moved a value other gates read.

The new message states only what is true of every producer that can reach the shape:
the printed form was not found missing, and what is unsettled is something else. The
specific reason travels in the detail, which is the one place it exists.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_evidence_field_notices.py -n0 -q -m unit
    17 passed in 4.74s

Reachability is proven from the producer rather than from a fixture: one case drives
the real identity resolver with a single verified candidate carrying no role
evidence, asserts the envelope shape it returns, and only then asks for the notice.

Two mutations from outside the repository, both rebinding in the notice module's own
namespace. Routing the located form back to the not-found notice, which is the
defect:

    === MUTATION S233-1 APPLIED ===
    3 failed, 14 passed in 2.81s
    === MUTATION S233-1 invocations={'routed_to_not_found': 4, 'fallback_used': 0} exit=1 ===

Restoring the carried-anchor fallback inside the not-found notice, the dead branch
that would let the two states render alike again:

    === MUTATION S233-2 APPLIED ===
    3 failed, 14 passed in 2.01s
    === MUTATION S233-2 invocations={'routed_to_not_found': 0, 'fallback_used': 14} exit=1 ===

Locale parity across all four catalogues:

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

## Notes

The not-found fixture was reshaped rather than left alone, and that is part of the
fix. It built a carried anchor under an unanchored outcome, which no producer emits
at this surface, and building it that way is how a third state came to share the
notice in the first place: the fixture asserted the conflation was correct.

A shape-to-code bijection was added beside the individual cases. It fails when two
shapes share a code rather than counting them, so a sixth state added later without
its own notice fails instead of being tallied.

Type debt of my own from the previous row was cleared here: the grounding helper in
the same test module took `**values: object`, which erased every draft field's
declared type on the way in and produced 31 checker diagnostics. It now takes the
built draft.
