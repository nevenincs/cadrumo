---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-07'
modified: '2026-07-17'
body_hash: 'sha256:a6c9de3bcd41df907c2bf5427488e70ac61f237b0cf4362a992b0a415168fc9f'
step_id: 'S347'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Annotate stale overview explain deadlines

## Scope

- `add an out-of-plazo annotation to explain output when overview calendar would have closed >12 months ago`
- `src/aeat/application/overview/_explain.py`

## Description

- Grounded the S347 finding with vault and code RAG searches for overview
  explain, stale deadlines, out-of-plazo, and prescription warnings.
- Checked the live BOE LGT authority for the ordinary four-year prescription
  framing in Ley 58/2003 arts. 66-67.
- Added `out_of_plazo_warning` to the typed `OverviewExplain` application
  payload.
- Derived the warning from the same registry deadline windows used by the
  deadline engine, preserving the existing applicability verdict.
- Rendered the warning in overview explain text output.
- Added real-registry tests for Modelo 100 2022 and 2025 deadline windows.

## Outcome

Closed. `overview explain` can now say both things that are true for a stale
historical return:

- the taxpayer-model applicability verdict remains `APPLICABLE`; and
- the voluntary filing window closed more than twelve months ago, with the
  ordinary four-year LGT arts. 66-67 horizon named.

For the S347 repro shape, Modelo 100 tax year 2022 evaluated on 2026-07-07
returns `applicable=True` and carries:

`out_of_plazo: voluntary filing window closed on 2023-06-30; as of 2026-07-07 the return is 1103 days past the deadline and is inside the ordinary four-year LGT arts. 66-67 prescription horizon (ordinary boundary 2027-06-30).`

Recent windows do not get the warning: Modelo 100 tax year 2025 evaluated on
2026-07-07 is after its 2026-06-30 close, but not more than twelve months past
the voluntary deadline.

Validation:

- `uv run --no-sync pytest -q src/aeat/application/overview/tests/test_explain.py`
  passed: 14 tests.
- `uv run --no-sync ruff check src/aeat/application/overview/_explain.py src/aeat/application/overview/tests/test_explain.py src/aeat/entrypoints/cli/_overview_rendering.py`
  passed.
- A direct `build_overview_explain` sanity check for Modelo 100 2022 returned
  `applicable=True` plus the out-of-plazo warning.

## Notes

No deadline dates were hard-coded. The warning reads the validated registry
deadline windows and only annotates matching windows whose close date is at
least twelve months behind the reference date.
