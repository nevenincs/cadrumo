---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4d968b64abf5f8eaa50da3d709561105a00c69fcd60556ecbd21f86d5905c1cf'
step_id: 'S69'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Persist the confirmation provenance record naming the confirmer, time, overridden fields, finding resolutions, and the evidence and transcription content addresses, gated by a strict roundtrip with every defaultable field non-default

## Scope

- `src/cadrumo/application/ledger`

## Description

- Declare a bucket-scoped encrypted namespace for confirmation records at the same financial sensitivity the draft carries.
- Persist one record per confirmation: confirmer, time, the reading lane, every asserted field with its prior value and origin, every blocking finding paired with the answer that cleared it, and the evidence and transcription content addresses the decision was taken against.
- Pair each resolution with the blocker it answers rather than storing the answer alone, so the record stays readable once the draft is discarded.
- Address the record by a clock-free derived id folding the confirmed outcome, so a retried confirm returns the stored record instead of a second account of one decision.
- Resolve the evidence address from the evidence record's own content hash, and leave it absent rather than invented when the confirm was taken directly against an attachment id.
- Write the record on both confirm branches, the minting branch and the guarded idempotent no-op.

## Outcome

A later audit, or a consent-withdrawal re-derivation, can prove which bytes a confirmation was taken against and what a person accepted, not merely that an invoice exists.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_confirmation_record.py -n0 -p no:cacheprovider -q
    (run jointly with the two sibling files) 30 passed in 16.27s

The roundtrip runs against the real isolated runtime profile: real key provider, real SQLite engine, real serializer, with every defaultable field populated off its default. Anti-tautology covers both field classes. Deleting the required asserted value reddens the load with a validation error, and dropping the defaultable evidence address, which cannot raise by construction, is caught by strict inequality against the saved record. A positive control asserts the intact payload survives the same round trip, so the refusal is attributable to the deletion.

Mutation proof: a store that silently drops the evidence address on the way to disk reddens the boundary equality assertion.

## Notes

Cache posture: `-p no:cacheprovider`, serial `-n0`.

The confirm result carries the record's id rather than a copy of the record. The store is the durable answer, and a copy riding a transient result is a second account of one decision that can disagree with the first.
