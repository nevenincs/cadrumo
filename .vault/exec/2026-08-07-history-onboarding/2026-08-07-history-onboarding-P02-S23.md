---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c731ee9972ed836356e74c3c3c082c898d95fab9d21e70f2fc6b1ea9a090a200'
step_id: 'S23'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# carry tipo_solicitud through into _filed_observation_source_metadata as aeat_tipo_solicitud, landed only after the file's current peer contention clears and by an executor rather than this plan's authoring agent, verified by a roundtrip test asserting the persisted metadata carries the field when the source Declaracion has one

## Scope

- `src/cadrumo/application/live/_filed_observation_persistence.py`

## Description

- Carry the register row's request type into the persisted source metadata as `aeat_tipo_solicitud`.
- Reverse the sibling pinning test that recorded the loss, as its own docstring instructed.
- Add the absent-versus-empty test and the strict persistence roundtrip.

## Outcome

AEAT's request type is the one signal distinguishing an original filing from an
amendment. It reached the raw observation and was dropped at persistence, because
the source metadata was built from a fixed key set, so the signal existed at
capture and was gone before anything downstream could read it.

Carrying it is NOT electing on it. No selection logic reads the key, and which
identifier an amendment-aware election should key on remains open; what changed is
that the evidence survives so that decision can later be made against persisted
data rather than requiring every taxpayer's history to be re-captured.

The key is OMITTED rather than written empty when the register row carried no
request type, because an empty string cannot be told apart from AEAT declaring
one.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py -q -n0 -k "request_type or tipo_solicitud"
    3 passed, 36 deselected in 38.55s

Closed against the landed implementation at commit `1742dc2cc9`, which this
executor authored in this session; the row was added to the plan by its author
after execution began and fell between the two scopes, so it stayed open while the
code was already in HEAD.

Read before closing, against the row as written. The row asks for the carry
"verified by a roundtrip test asserting the persisted metadata carries the field
when the source Declaracion has one". The implementation satisfies that and is
NARROWER in one respect worth stating: it reads `tipo_solicitud` off the raw
observation's metadata mapping rather than off a `Declaracion` directly, because
that mapping is where the capture path already deposits it — the persistence
boundary never sees a `Declaracion`. It is also narrower by design on the empty
case, omitting the key rather than writing a blank. Neither narrowing withholds
anything the row asked for.

## Notes

The sibling row that pinned the LOSS was written to go red once this landed and
its docstring named the reversal. It was reversed rather than relaxed: the two
absence assertions were deleted, and the replacement asserts the carried value
plus two neighbouring provenance keys so a change that carried the request type
while dropping a sibling key does not read as a pass.
