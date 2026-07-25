---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S248'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Introduce one typed filed-capture finalizer and failure accumulator used by single, bulk, and source capture with explicit fail-fast single and source policy and best-effort bulk policy

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`
- `src/cadrumo/application/live/_filed_data.py`

## Description

- Read the finalizer module that the sibling step already built before writing anything.
- Confirm the failure policy is a closed typed enum rather than a boolean or a string.
- Confirm the accumulator is a typed row rather than a message list.
- Verify each of the three capture routes passes the policy the step assigns it, by reading the call sites.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

The finalizer exists as its own module and matches the step's requirement closely enough that re-implementing it would have been destructive. It is one function taking the observations, an optional receipt mapping, and a mandatory keyword-only policy, returning a frozen result carrying the persisted observation keys and the accumulated failures. Selection and ordering are delegated to the persistence authority rather than reimplemented, which is what makes all three routes agree.

The policy is a closed string enum with exactly two members, fail-fast and best-effort, each documented with the routes that use it, so a caller cannot pass an unhandled third value and the axis is typed at the boundary. The accumulator is a typed failure row carrying the modelo, year, typed period, expediente identifier, error type and a bounded message, built once in a single private helper, so every route reports a failure in the same shape. Under fail-fast, accumulated failures are raised as one application error whose context names the failed count and the first failure's coordinates; under best-effort they are returned for the caller's report. Both policies therefore run the same loop and diverge only at the end, which is what the step means by unifying the mechanism while preserving the policies.

All three routes were checked at their call sites rather than inferred from the module docstring. Single capture passes fail-fast, bulk capture passes best-effort, and source capture passes fail-fast. That is exactly the assignment the step specifies, and there is no fourth caller and no route that bypasses the finalizer.

Run at the current commit as part of a fifty-seven test run across the three probe modules this phase names: all passed. No change was needed or made.

## Notes

Semantic code search was degraded and reported itself healthy, with an empty degraded-reasons list. The brief's warning that this module already existed is what prevented a duplicate, and it was confirmed by reading the module in full before any edit. Had the finalizer been located by search instead, the degraded index would plausibly have missed it and a second finalizer would have shipped, which is the failure mode the discovery mandate exists to prevent.

The step cites the capture and filed-data modules as its scope, but the finalizer it asks for lives in its own module named for the concept, which neither citation names. The three policy-bearing call sites are in the capture module as cited; the filed-data module holds no finalizer call. This is the same scope-citation drift recorded against three other steps in this campaign, and it is again the kind a reader with only the plan cannot detect.

The step's wording asks to introduce the finalizer, so the honest reading of this closure is that the work landed earlier under the sibling plan and this record verifies it rather than claiming authorship.
