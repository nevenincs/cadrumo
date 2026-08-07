---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1dda37a329ae5e55c7498d0dba33dd243bb7d114ffd92f824c325fe4a4ce702d'
step_id: 'S14'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Change the semantic stage to consume `DocumentTranscription` rather than a bare string, on the extractor and on the router-facing wrapper.
- Read the stamped origin off the transcriber instead of asserting `TEXT_LAYER`.
- Point the router's text branch at the artefact it already held.
- Add the wiring gate: artefact in, origin carried, provider pinned LOCAL, evidence marked, role-named model resolved, role evidence carried through.

## Outcome

Most of this surface already existed and was consumed rather than rebuilt. The
prompt compiler, the field-form contract, the strict payload schema, the grounded
re-validation, the LOCAL pin and the consent marking were all at HEAD; the
role-named model settings existed too, as `ModelRole.TEXT_EXTRACTION` with its
own resolvable setting, deliberately sized apart from the vision role because the
text roles must be satisfiable on a machine that can host no vision model at all.

What was missing was the seam. The stage took `evidence_text: str`, which is what
made it a helper that happens to accept text rather than the second stage of a
pipeline. A string carries no answer to "who read these characters off the
document", and that answer is not decoration -- it is the origin stamped on every
value the stage proposes, and the record of whether an independent reader
produced the text its anchors are later checked against.

Hardcoding `TEXT_LAYER` was defensible while a text layer was the only thing that
could reach this reader. The moment a vision transcription can, it laundres a
rasterised read into an exact-looking one, which is the precise distinction
`FieldOrigin` exists to keep. The origin is now read off the artefact.

The consent gate is untouched and unmoved: the stage marks every request
evidence-derived unless the caller names the public corpus, and the single
dispatch point does the refusing. No second dispatch path was added.

## Verification

    uv run --no-sync pytest src/cadrumo/llm/tests/test_stage_two_semantic_reader_wiring.py src/cadrumo/llm/tests/test_invoice_role_evidence.py -n0 -p no:cacheprovider -q -m unit
    20 passed in 11.94s

    uv run --no-sync pytest src/cadrumo/llm/tests/test_evidence_consent_gate.py -n0 -p no:cacheprovider -q -m unit
    30 passed in 19.46s

Mutation, from outside the repository:

    S13_MUTATION=hardcode_the_reader_origin ... -p s12_s13_s14_mutation
    1 failed, 6 passed in 6.56s
    reds: test_every_envelope_carries_the_transcribers_origin_not_a_hardcoded_one[vision]

The origin case is parametrised across BOTH acquisition members rather than
asserting one, because a stage that hardcoded either would pass a single-origin
case. The mutation reds exactly the `vision` parametrisation and leaves
`text_layer` green, which is the signature of a genuine hardcode rather than of
a broken reader.

## Notes

The plan row records this Step as in flight in another lane. Checked before
editing: the working tree carried no uncommitted change on the target files, and
the module's history showed no in-flight work on this seam.

The consent-gate cases needed their call sites moved to the artefact. Their
positive control is intact and still discriminating -- the public-corpus case
differs from the refusal case in exactly one variable and reaches the endpoint,
so the refusal is not satisfied by a reader that can no longer dispatch at all.
