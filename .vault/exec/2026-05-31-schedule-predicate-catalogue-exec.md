---
tags:
  - '#exec'
  - '#schedule-predicate-catalogue'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-schedule-predicate-catalogue-plan]]'
  - '[[2026-05-31-schedule-predicate-catalogue-P01-S01]]'
  - '[[2026-05-31-schedule-predicate-catalogue-P01-S02]]'
  - '[[2026-05-31-schedule-predicate-catalogue-P02-S03]]'
  - '[[2026-05-31-schedule-predicate-catalogue-P02-S04]]'
---

# `schedule-predicate-catalogue` summary

Completed the schedule predicate catalogue compile-time validation slice.

- Modified: `src/aeat/domain/calculations/registry/_authority.py`
- Modified: `src/aeat/domain/calculations/registry/_registry_contract.py`
- Modified: `src/aeat/domain/calculations/registry/test_authority.py`
- Modified: `src/aeat/domain/calculations/registry/test_filing_schedule_selection.py`

## Description

P01-S01 added eager registry validation during authority load so predicate-field
checks fire before first schedule selection. P01-S02 documented the historical
alias shims used by profile fact resolution. P02-S03 added proof coverage for
unknown predicate fields on the `filing_schedule` surface. P02-S04 added the
matching proof coverage for the `deadline_window` surface.

## Tests

The four step records report focused registry contract and filing schedule
selection gates passing, culminating in the combined gate of
`test_filing_schedule_selection.py`, `test_authority.py`, and
`test_registry_contract.py`: 16 passed, 0 failed.
