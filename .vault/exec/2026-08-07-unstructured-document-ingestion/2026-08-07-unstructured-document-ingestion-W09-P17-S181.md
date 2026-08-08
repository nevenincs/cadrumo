---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:7e2af5c36ed0f04ab4c717f6b51fc0b1ee541e2ee5ca7bdb438dd8583173d3ae'
step_id: 'S181'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Tell the operator that an anchor was supplied and refused rather than that none was supplied, since nulling the anchor on a miss makes a refused explicit anchor fall through to the no-anchor notice while the anchor-not-found notice cannot be reached from this producer at all. Messaging drift rather than dead code, since another producer does reach it. Preserve the refused anchor behind a distinct flag or branch the note selection on whether an explicit anchor was supplied

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add `refused_anchor` to the provenance envelope in `src/cadrumo/application/ledger/_evidence_draft.py`, carrying the printed form a reader offered and the check did not locate.
- Add a two-directional validator refusing an envelope that holds the same claim as both a located and a refused anchor, and refusing a refusal under an outcome meaning the check passed.
- Add `refused_anchor_of` to `src/cadrumo/application/ledger/_grounding_anchor.py` as the one place the refusal is derived, and stamp it from both producers there.
- Stamp it from the grounding stage in `src/cadrumo/application/ledger/_grounded_reading.py`, the producer the finding named.
- Branch the notice selection in `src/cadrumo/entrypoints/cli/_evidence_field_notices.py` on the refused anchor beside the carried one, and carry the check's computed reason into the anchor-not-found notice's message and context.
- Set that reason into the four locale catalogues through the locale CLI.
- Mirror the field on the extract payload envelope in `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`, and populate it off-default in the provenance roundtrip fixture.

## Outcome

A reader that pointed at a printed form the document does not carry and a reader that
pointed at nothing no longer arrive at the operator as the same message. The anchor is
still cleared on a miss, so nothing downstream can read a refused form as evidence; the
refusal is preserved beside it, where the operator surface can name it.

The shape is a dedicated nullable field rather than a boolean flag or a preserved anchor.
A boolean discriminates but discards the text the message needs. Preserving the anchor
would have carried the text at the cost of feeding a form the document does not print
into every consumer that reads an anchor as evidence, including the identity candidate
assembly, and it contradicts the envelope's own documented contract that a value nobody
can point at in the document carries no anchor.

The anchor-not-found notice also stopped dropping the check's own explanation, which was
computed, written onto the envelope, and read by nobody.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_evidence_field_notices.py src/cadrumo/application/ledger/tests/test_grounded_reading_wiring.py -n0 -q -m unit
    37 passed in 5.69s

Both directions are proven by mutation from outside the repository, rebinding the
production functions in the importing module's own namespace so nothing under source
control changed. Each run asserted the rebinding took hold rather than trusting that it
had, since a value bound as a default argument reports applied while ignoring a
module-global rebinding.

Recording no refusal, which is the defect itself:

    === MUTATION 1 APPLIED ===
    3 failed, 34 passed in 5.01s
    === MUTATION 1 invocations={'refused_anchor_of': 34, 'anchor_not_found_notice': 0} exit=1 ===

Dropping the carried reason:

    === MUTATION 2 APPLIED ===
    3 failed, 34 passed in 4.67s
    === MUTATION 2 invocations={'refused_anchor_of': 0, 'anchor_not_found_notice': 7} exit=1 ===

Locale parity, whose two reported extras belong to another lane's uncommitted work:

    uv run --no-sync python -m dev.locales scaffold --check
    es.yml: missing=0 extra=2

## Notes

The change was authored against a moving tree. A sweeping commit took every source edit
of this Step into the branch before this record was written, so the work landed under
another lane's subject line rather than under one naming it.

Two gates outside the notice surface were pulled in by the new envelope field and belong
to this Step rather than being incidental: the extract payload model, which forbids extra
keys and so refuses an envelope carrying a field it does not declare, and the provenance
roundtrip fixture, whose own gate requires every defaultable field to be populated
off-default or the roundtrip agrees that two absences match.

One adjacent mis-message was found and deliberately left. The identity role resolver
emits an unanchored envelope carrying an anchor the document DOES print, whose only
missing ingredient is role evidence; that envelope reaches the anchor-not-found notice
and is told the form does not occur in the transcription. It is a different defect from
this one and is reported to the coordinator rather than folded in here.
