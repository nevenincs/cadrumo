---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:2fadb1128fd49079ac8901bf190f950a8f5cde8ec7143b23d111f12065887ae7'
step_id: 'S68'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Record corrections as assertions: an operator override re-stamps the field OPERATOR while the confirmation record retains the prior value and origin, gated by a roundtrip asserting both values survive

## Scope

- `src/cadrumo/application/ledger`

## Description

- Derive one assertion per field the operator actually supplied a value for, carrying the asserted value beside the prior value, the prior origin and the prior grounding outcome.
- Skip a field the operator did not supply: silence is not an assertion.
- Record no prior origin where the document stated nothing, so supplying and correcting stay distinguishable acts.
- Produce a second, confirmed view of the envelopes in which each asserted field reads OPERATOR and UNANCHORED, leaving the document's own envelopes untouched.
- Never stamp an operator value ANCHORED: an assertion is not a reading, so there is no verbatim occurrence to anchor it to.
- Surface both views on the confirm payload, so the operator-asserted value and the document's account travel together.

## Outcome

The record can always answer both halves of the question: what did the document say, and what did the operator assert instead. An override that merely overwrote could answer neither.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_confirmation_record.py -n0 -p no:cacheprovider -q
    (run jointly with the two sibling files) 30 passed in 16.27s

Mutation proofs, from a plugin outside the repository:

- leaving the document's envelope in place reddens the re-stamp assertion and the never-anchored assertion;
- re-stamping every envelope rather than the asserted ones reddens the scope control;
- dropping the prior origin reddens the retention assertion;
- recording an unsupplied field as an assertion reddens the silence assertion.

## Notes

The prior envelope in the fixture is deliberately ANCHORED and carries an anchor. An earlier fixture left it already UNANCHORED with no anchor, which made the never-anchored assertion pass without the re-stamp running at all; that inertness was found by mutation and closed.
