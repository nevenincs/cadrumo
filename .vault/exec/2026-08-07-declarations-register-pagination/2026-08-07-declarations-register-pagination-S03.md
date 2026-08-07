---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:20e72310d446767730740875e33a957cfe7d38ce32fc6248ea787bde9d12eb84'
step_id: 'S03'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---
## Description

Confirmed, not built. The bulk sweep's walk arm already folds any walk exception
into a per-pair `FiledDataCaptureFailureRow` and continues, so the truncation
refusal is absorbed with zero additional code. That reuse-not-invent outcome is
the whole deliverable, and no production behaviour changed here.

This Step's original text also claimed the sweep re-raises a walk failure under
FAIL_FAST and required a test proving it. That claim was ungrounded and is
recorded here as a deliberate exclusion rather than a silent narrowing.

## Outcome

- `src/cadrumo/application/live/_filed_data_capture.py`: `_walk_or_failure_row`
  catches `Exception` and maps through `filed_data_capture_failure_row`
  unchanged. Its docstring now records that a truncated register read arrives
  here like any other walk failure, and why truncation deliberately gets no
  second reporting channel: two channels would let one partial capture be
  counted a success on one path and a failure on the other.
- No new branch, parameter, or abort mechanism was added. Adding one to make a
  mis-authored gate true would have been the worst available outcome.

## Verification

A test in `application/live/tests/test_filed_bulk_capture.py` asserts the refusal
is catchable by that arm and that the resulting row preserves the error type,
both counts and the reason. Mutating the row's message bound down to 40
characters reds it, so the truncation assertion is not decorative — the first
refusal wording overran the real 160-character bound and arrived with its reason
cut off mid-word, which is why that assertion exists at all.

## Notes

Two scope exclusions, both verified against the code rather than assumed, and
both deliberate:

There is no FAIL_FAST path for a bulk walk failure. `capture_filed_data_bulk`
takes no failure-policy parameter and `_walk_or_failure_row` catches
unconditionally. The `FiledCaptureFailurePolicy` axis in this file is real but
governs `finalize_filed_capture`'s calculation-observation stage — hardcoded
best-effort for the bulk sweep, fail-fast for the singular `capture_filed_data`
and for `capture_source_filed_data`. That is a different function and a different
failure class. The fail-fast-equivalent for a single-pair capture is
`capture_filed_data`'s uncaught propagation, which this plan does not touch. So
the excluded gate clause described a branch that does not exist, and the Step
text was amended to drop it rather than the code changed to fit it.

The sweep-continuation half of the original gate is also excluded, and this one
is a genuine coverage gap rather than a mis-authored claim. Forcing one
`(modelo, ejercicio)` pair's walk to raise while the others complete needs either
a substituted register (a test double, which this campaign forbids) or a live
authenticated session (which no authorisation covers): both bulk paths resolve
`active_verified_session` and open their own Playwright register before any walk,
so the walk arm is unreachable offline. The consequence worth stating plainly is
that nothing tests BEST_EFFORT sweep continuation for ANY failure kind, not just
this one. Closing it needs a seam letting the sweep accept an already-opened
register, which is a decision beyond this plan's scope and is left open rather
than quietly absorbed.
