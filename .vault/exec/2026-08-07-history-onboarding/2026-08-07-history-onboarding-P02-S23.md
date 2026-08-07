---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:824127efeba84bad6062c7debc669c4f1ad28b94b3257099451f4e5986d3c881'
step_id: 'S23'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# carry tipo_solicitud through into _filed_observation_source_metadata as aeat_tipo_solicitud, landed only after the file's current peer contention clears and by an executor rather than this plan's authoring agent, verified by a roundtrip test asserting the persisted metadata carries the field when the source Declaracion has one

## Scope

- `src/cadrumo/application/live/_filed_observation_persistence.py`

## Description

- Carry the register row's request type into the persisted source metadata as `aeat_tipo_solicitud`, omitting the key when the row declared none.
- Reverse the pinning test that recorded the loss, as its own docstring instructed.
- Add the absent-versus-empty test and the strict persistence roundtrip.

## Outcome

AEAT's request type is the one signal distinguishing an original filing from an
amendment. It reached the raw observation and was then dropped, because the
calculation-observation source metadata was built from a fixed key set that did
not include it -- so the signal existed at capture and was gone before anything
downstream could read it.

Carrying it is NOT electing on it, and the distinction is kept explicit in the
code rather than left to a reader. No selection logic reads the key, and which
identifier an amendment-aware election should key on remains an open decision.
What changes is that the evidence survives, so that decision can later be made
against persisted data instead of requiring every taxpayer's history to be
re-captured.

The key is OMITTED rather than written empty when the register row carried no
request type. An empty string is indistinguishable from AEAT declaring an empty
request type, so a later reader could not tell "the row did not say" from "the
row said nothing"; absence is the honest encoding.

## Verification

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py -q -n 0 -k "request_type or tipo_solicitud"
    3 passed, 36 deselected in 38.55s

The sibling Step that pinned the LOSS was written to go red once this landed, and
its docstring named the reversal. It was reversed rather than relaxed: the two
absence assertions were deleted, not weakened, and the replacement asserts the
carried value plus two neighbouring provenance keys so a change that carried the
request type while dropping a sibling key does not read as a pass.

The roundtrip compares the WHOLE reloaded provenance envelope against an exact
expected mapping rather than checking the one new key, so a save that carried the
request type while re-defaulting another field fails. The absent-versus-empty test
carries an anchor assertion that the metadata was built at all, so its two
absences mean something.

## Notes

This row was gated on the file's peer contention clearing and on being landed by
an executor rather than the plan's authoring agent; both conditions held at
landing time. The file's diff was checked for foreign markers immediately before
the commit and carried none.
