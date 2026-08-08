---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:e1d4be7e184f536edcfbba17470bbd7053a615304c12a2207724bb59a0794866'
step_id: 'S231'
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
     The S231 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Carry refused_anchor to the review surface, the one surface it exists for. Measured: FieldProvenance.refused_anchor reaches the extract envelope and is mirrored on the business payload, and appears zero times in the review CLI, whose per-field row builder passes anchor and anchor_self_reported and nothing for the refused form. Its own docstring says the point is that the operator surface can say which of the two happened, a reader that offered nothing versus one that offered something the document does not carry, and the per-field review rows are where an operator reads a field's grounding. There the two remain indistinguishable, which is the exact state the field was added to end. Same shape as anchor_self_reported beside it and ## Scope

- `src/cadrumo/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Carry refused_anchor to the review surface, the one surface it exists for. Measured: FieldProvenance.refused_anchor reaches the extract envelope and is mirrored on the business payload, and appears zero times in the review CLI, whose per-field row builder passes anchor and anchor_self_reported and nothing for the refused form. Its own docstring says the point is that the operator surface can say which of the two happened, a reader that offered nothing versus one that offered something the document does not carry, and the per-field review rows are where an operator reads a field's grounding. There the two remain indistinguishable, which is the exact state the field was added to end. Same shape as anchor_self_reported beside it

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Declare `refused_anchor` on the review row payload in `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`, beside the anchor it qualifies.
- Pass it from the per-field row builder in `src/cadrumo/entrypoints/cli/_ledger_evidence_review_cli.py`, which passed the anchor and the self-reported flag and nothing for the refused form.
- Add an end-to-end regression driving the real review verb over a draft the real grounding stage produced.

## Outcome

The distinction the envelope records now survives to the row an operator reads a
field's grounding from. Both states reach that row with a blank anchor, because the
grounding stage clears a form it could not locate, so the row without the refusal
beside it rendered a reader limitation and a possible misread identically.

The field had reached the extract envelope and the business payload and stopped
there, which is this campaign's own signature defect landing on the fix for that
defect: computed, carried, and not reaching the one surface it was built for.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_cli.py -n0 -q -m integration
    7 passed in 6.23s

The regression seeds a draft whose envelopes came from the real `verified_provenance`
against a real transcription, then drives the real Typer tree. A row built by hand
carries whatever the test wrote into it and would pass while the builder still
dropped the field, which is the gap this row exists to close.

A positive control asserts both rows actually reached the surface, so neither
assertion can pass over an absent field.

Mutation from outside the repository, rebinding the row builder in its own module
namespace to blank the field, which is the pre-fix state exactly:

    === MUTATION S231 APPLIED ===
    1 failed, 6 passed in 5.55s
    === MUTATION S231 invocations={'field_payloads': 3, 'rows_blanked': 1} exit=1 ===

The blanked count is the load-bearing half: it proves the mutation had something to
remove rather than reporting applied over a row that never carried the field.

## Notes

The payload and builder edits were taken into the branch by a sweeping commit before
this record was written; only the regression landed under a commit naming the work.

The review row deliberately stays a curated subset rather than a mirror of the
envelope: it carries no `derived_from` and no `attribution_unverified` either, and
the refused form earns its place because it disambiguates a field the row already
shows, not because the envelope has it.
