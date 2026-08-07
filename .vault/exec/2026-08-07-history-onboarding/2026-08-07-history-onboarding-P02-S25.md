---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:fd08ff771fc14e06c19bf4dd630e4b64a2ed7be7c34f2e4709c2bb5ba23a3565'
step_id: 'S25'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
## Description

The live register returned two active filings for the same period, so the
history selector's collapse behaviour became load-bearing rather than
incidental. Existing coverage exercised an ALTA superseding a later BAJA and one
two-ALTA duplicate, but always with the inputs already in a convenient order.
That is exactly the arrangement under which a last-write-wins reduction and a
max-by-rank one agree, so the property the selector actually claims -- that it
RANKS rather than remembers -- was unproven.

This Step adds the order-invariance test. The batch mixes two duplicated periods
(each an original plus a later-presented amendment, both ALTA) with an ordinary
single-filing period, and asserts three things: exactly one observation survives
per period, every period survives, and the later-presented filing is the one
kept. Then it feeds the identical set in reverse and asserts the result is
IDENTICAL. That last assertion is what separates ranking from arrival order.

No production code changed.

## Outcome

Added `test_history_selection_is_invariant_to_the_order_duplicated_periods_arrive_in`
to `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.

Assertions are properties, not tallies: the per-period uniqueness check compares
the selected period list against its own set, and the coverage check compares the
selected period set against the input's, so no row count is hardcoded.

## Verification

The test passes. Two runtime mutations from an out-of-repo pytest plugin proved
it bites, each aimed at a different assertion:

- Ranking that compares only the ALTA flag and forgets the presentation
  timestamp reds the winner assertion (`assert '2024...303C' == '2024...505E'`) --
  every active filing ties, so the first one seen wins.
- A reduction that keeps whichever row arrived last reds ONLY the invariance
  assertion (`selection depends on the order the register rows arrived in, so it
  is not ranking them`), with the winner assertions still passing. That is the
  proof the reverse-order half earns its place.

The second mutation had to be re-aimed. A first attempt assigned ranks in
call order rather than input order, which scrambled the forward pass too and red
the winner assertion instead of the invariance one -- so it proved nothing about
the assertion it was meant to target. Both runs are recorded here rather than
only the successful one.

## Notes

Selection is a pure function over already-validated observations, so this test
touches no storage and needs no profile bucket.
