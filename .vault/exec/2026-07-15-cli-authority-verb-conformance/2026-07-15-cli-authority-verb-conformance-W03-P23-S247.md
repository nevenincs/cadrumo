---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:3cdd619e23b3027706dc35154405c23ed6ce5a150d2c3ddb059841cff4a01a06'
step_id: 'S247'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Make filed observation persistence the sole owner of latest-record selection, deterministic history ordering, metadata enrollment, and calculation-observation writes and remove the duplicate selector and persistence loop from capture orchestration

## Scope

- `src/cadrumo/application/live/_filed_observation_persistence.py`
- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Read the persistence module's selection and ordering authority and confirm it is a single function.
- Sweep capture orchestration for any surviving selector, period-token sort, or persistence loop.
- Investigate the second persistence loop that remains inside the persistence module and decide whether it is a competing authority or a parity-gated entry point.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

Selection and ordering live in one function in the persistence module and nowhere else. It reduces observations to the latest per modelo, year and period by an explicit rank that prefers an active registration over a cancellation, then the most recent presentation timestamp, then the expediente identifier as a tiebreaker; it then emits them in a deterministic history order that applies the fiscal period ordering for the IVA modelo and numeric ordering elsewhere. Its own docstring names it the single selection-and-ordering authority shared by the persistence path and the capture finalizer.

Capture orchestration carries no duplicate. A sweep of both cited modules for a selector, a raw period-token sort, or a persistence loop returns nothing but a single docstring cross-reference to the persistence module's batch function, and that reference is live rather than stale. The three capture routes reach persistence only through the finalizer, which delegates selection to the authority above.

The one finding worth recording is a second persistence loop that does survive, inside the persistence module itself. The module exports a batch function that loops the same selector and persists, alongside the finalizer's loop. They differ deliberately: the batch function skips an observation whose values cannot be extracted and returns the keys it managed to write, while the finalizer raises per observation and accumulates typed failure rows so a policy can be applied. The batch function has no production caller.

That looked at first like residual duplication to delete, and it is not. Both loops consume the same selector, so the axis this step governs is genuinely single-sited. The divergent behaviour is covered on purpose, with a probe asserting the skip path returns no keys and writes neither IVA history nor a calculation observation. More decisively, a probe asserts the finalizer's emitted keys and the batch function's keys are equal for the same input, which makes the batch function a parity anchor for the finalizer rather than a rival authority. Deleting it would remove the cross-check that proves the two agree. It stays.

Run at the current commit as part of a fifty-seven test run across the three probe modules this phase names: all passed. No change was needed or made.

## Notes

Semantic code search was degraded and reported itself healthy, with an empty degraded-reasons list, so the duplication question was settled by reading both loops in full and grepping every caller of each, rather than by searching for the concept. This mattered here: the two loops are near-identical in shape and a search-led read would plausibly have reported the batch function as a stray duplicate to delete, which would have removed the parity anchor.

The finalizer reaches into the persistence module for a private helper that maps an observation to its justificante receipts. Both modules sit in the same package, so this is an intra-package private import and within the boundary rule, but it is the one seam where the finalizer depends on persistence internals rather than its public surface.

One behavioural consequence of the finalizer's failure semantics is worth flagging for whoever owns the capture routes, though it is outside this step and landed earlier in the campaign. The batch function skips an unextractable observation silently, whereas the finalizer converts it into a failure row, and under the fail-fast policy that aborts the operation. Single and source capture use fail-fast. If unextractable observations occur routinely in a live register walk, those two routes now abort where the older path would have skipped and continued.
