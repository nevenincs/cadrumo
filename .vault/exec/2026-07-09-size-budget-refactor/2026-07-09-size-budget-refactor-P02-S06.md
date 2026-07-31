---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:fab259368d337f002071e913d6c80ee3b1fdabf1aa0eacadd50c42eb484827e3'
step_id: 'S06'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Run the overview test suite, ruff, pytest --collect-only, and test_codebase_size_budgets to confirm the module and callable are under budget with zero behavior drift

## Scope

- `src/aeat/application/overview/tests/`

## Description

- Ran the full overview test suite (`src/aeat/application/overview/tests/`, 214 tests) -- all passed.
- Ran `ruff check` on both `_calendar.py` and `_calendar_evidence.py` -- clean.
- Ran `pytest --collect-only` across the full `src/aeat` tree; confirmed the only 6 collection errors present were pre-existing, unrelated peer WIP in `secure_objects.py` (a different campaign's in-flight file, confirmed via `git status`/`git log -1`), and that excluding those 6 test files yields a fully clean collection (12474/15178 tests, 0 errors).
- Ran `test_codebase_size_budgets.py` and confirmed `_calendar.py` and `build_overview_calendar` no longer appear in either offender list; the remaining 4 module and 4 callable offenders match exactly the 6 deferred peer-owned offenders this plan's P05 records (`secure_objects.py` and `taxpayer_profile_from_mapping` were also already resolved by the parallel coder-perf agent's P03/P04 work at the time of this run).

## Outcome

Zero behavior drift: 214/214 overview tests pass, ruff clean, full-tree collection clean modulo unrelated peer WIP, and `test_codebase_size_budgets.py` no longer lists either `_calendar.py` or `build_overview_calendar` as an offender.

## Notes

No incidents.
