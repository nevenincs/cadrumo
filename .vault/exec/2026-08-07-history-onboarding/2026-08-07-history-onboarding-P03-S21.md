---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:8508222c512eb276d476504ec01d41db68bd3e40d19fb6f3c164edbee7eca3d7'
step_id: 'S21'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# extend FiledDataCaptureReport and BulkFiledDataCaptureReport with a per modelo ejercicio period breakdown of raw register row count versus the one persisted calculation observation, computed from the declarations and selected tuples already held before finalize_filed_capture runs, touching no persistence-boundary file, verified by a synthetic-fixture test asserting a two-row period reports raw count two and selected count one

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Add `FiledPeriodSelectionRow` and `filed_period_selection_rows`, projecting raw register rows against captured observations.

## Outcome

The register can hold several filings for one period and exactly one is promoted
to calculation history. That collapse is correct and was invisible, so an operator
seeing one persisted observation could not tell whether AEAT held one filing or
four.

Keyed on PERIOD rather than on the query pair, because one pair returns several
periods and summing them would report the pair as duplicated while hiding which
period actually held two filings.

Supersession is read off the raw count alone. Deriving it from raw-minus-selected
conflates a period AEAT held several filings for with a period whose single filing
simply was not captured — and reporting the second as supersession would tell the
operator their filing was superseded by one that never existed. The unaccounted
rows get their own count instead.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_history_discovery.py -q -n0
    38 passed in 16.82s

The period-keying test caught a real semantic defect on first run: a period with
one uncaptured row reported `held_more_than_one_filing` as true. The predicate was
corrected to the raw count, which is also what the sibling advisory row specifies.

## Notes

Computed from tuples the sweep already holds before finalisation, so it touches no
persistence-boundary file and adds no read.
