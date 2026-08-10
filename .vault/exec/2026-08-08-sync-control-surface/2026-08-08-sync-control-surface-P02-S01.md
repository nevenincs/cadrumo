---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:1603aec4a83e9eb3f41cfe8abbba4390fcfadc4584b8fee78dddcd13ba28ef32'
step_id: 'S01'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
  - "[[2026-08-08-sync-control-surface-adr]]"
  - "[[2026-08-08-sync-control-surface-reference]]"
---

# Relocate the recapture divergence computation ahead of the upsert

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Check the row against HEAD before dispatching it, per the standing rule that an
  unchecked row is not evidence the work is undone.
- Establish that the relocation had already landed, and confirm it by reading the
  production ordering rather than the commit subject.
- Confirm the ordering is held by a gate rather than by convention.
- Record the delivery so the row's three possible states stop wearing one
  checkbox.

## Outcome

THIS ROW WAS ALREADY DELIVERED WHEN THE CAMPAIGN OPENED IT, and this record
exists to say so rather than to claim work.

The row asks for the recapture divergence computation to run BEFORE the upsert
instead of after it, preserving the existing notice. At HEAD the capture
accumulator reads the divergence as its first act, ahead of the persist call,
with the reason written beside it: a re-capture is an unconditional upsert, so
afterwards the prior values are gone and the advisory can only ever report
nothing — which looks exactly like a clean sweep. That is the row's deliverable,
and it was in the tree before this campaign dispatched anything.

THE ORDERING IS HELD BY A GATE, NOT BY CONVENTION, which is what makes the
delivery durable rather than incidental. A dedicated test reads the accumulator's
own source and asserts the divergence read appears before the persist call. That
is an unusual shape and it is the correct one here: the property is an ORDERING
between two statements, and no behavioural assertion can distinguish "read before
the write" from "read after the write" once the write has already destroyed the
prior values. The failure this guards against is silent by construction — the
advisory returns nothing and nothing looks wrong.

WHY THE ROW LOOKED OPEN. The plan was authored on the day the relocation landed,
and the two did not reconcile. Nothing was wrong with either; the row simply
described a state the tree had already reached. Dispatching it would have
produced either a no-op commit or, worse, a second relocation of code already in
the right place.

## Notes

THE CHECK THAT FOUND THIS IS THE POINT, not the finding. The row was verified
against HEAD before dispatch, on the standing rule that an unchecked row is not
evidence the work is undone — the fleet and outside teams land steps in parallel,
and a row can be delivered by someone who never read the plan. The same pass
found a second row in the sibling plan in the same state.

A CONSEQUENCE FOR ANYONE TOUCHING THE CAPTURE ACCUMULATOR. Because the gate
asserts source ordering by inspection, any refactor that moves either the
divergence read or the persist call — including one that preserves behaviour
exactly — will red it. That is the gate working, not a false positive, but it
will surprise someone who changes the accumulator for an unrelated reason and
expects a behavioural test suite to be indifferent to statement order.

NO CODE WAS WRITTEN FOR THIS ROW and none should have been. The record closes the
gap between "delivered" and "recorded as delivered", which is one of the three
states that otherwise wear the same checkbox: delivered as specified, delivered
narrower, and recorded-but-not-implemented.
