---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:20def46578732032d94dc536973ce43ebf70b8e16422e21795b4d3dae42104d6'
step_id: 'S03'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---
## Description

Partially delivered, and reopened rather than closed. The confirmation the ADR
asks for is done: the bulk sweep's walk arm already folds any walk exception into
a per-pair `FiledDataCaptureFailureRow` and continues, so the truncation refusal
needed no new control flow. The Step row's own gate asks for more than that, and
the remainder is not reachable under this campaign's constraints.

## Outcome

- `src/cadrumo/application/live/_filed_data_capture.py`: `_walk_or_failure_row`
  catches `Exception` and maps through `filed_data_capture_failure_row`
  unchanged. Its docstring now records that a truncated register read arrives
  here like any other walk failure, and why truncation deliberately gets no
  second reporting channel: two channels would let one partial capture be
  counted a success on one path and a failure on the other.
- No production behaviour changed in this file. That is the intended result.

## Verification

Delivered: a test in `application/live/tests/test_filed_bulk_capture.py` asserts
the refusal is catchable by that arm and that the resulting row preserves the
error type, both counts and the reason. Mutating the message bound down to 40
characters reds it, so the truncation assertion is not decorative.

NOT delivered, and the reason this Step stays open: the row's gate asks for a
test that forces one `(modelo, ejercicio)` pair's walk to raise under
`BEST_EFFORT` while the remaining pairs complete, plus a `FAIL_FAST` companion.
`capture_filed_data_bulk` takes no register or session parameter — it opens its
own authenticated register and resolves a verified live session before any walk —
so forcing one pair's walk to raise requires either a substituted register (a
test double, which this campaign forbids) or a live authenticated AEAT session
(which no operator authorisation covers). Both routes are closed, so the gate as
written cannot be met without either relaxing a standing prohibition or adding an
injection seam to production code that nothing else needs.

## Notes

The taxonomy test builds a representative `SedeParseError` rather than importing
the adapter's private refusal helper: an application-layer test reaching into
another package's private module is exactly the coupling the import boundary
forbids. The consequence is that the refusal's wording is duplicated in the test,
so a production rewording reds it — the correct signal, since the length bound
has to be reconsidered each time that wording changes.

Two ways to close this honestly, both needing a decision this Step should not
make alone: narrow the row's gate to the confirmation the ADR actually asks for,
or authorise a seam that lets the bulk sweep accept an already-opened register so
the sweep's continuation semantics become testable offline. The second is the
more valuable of the two, since nothing currently tests the BEST_EFFORT
continuation for any failure kind, not just this one.
