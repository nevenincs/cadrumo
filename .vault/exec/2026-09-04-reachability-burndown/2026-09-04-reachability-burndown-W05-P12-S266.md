---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:00be24ce76b4878394f2334a966500d0399fab9821b76cae3b2b940cce571ba7'
step_id: 'S266'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the hand-maintained external-constants centralisation part-two census that pins production module paths, aliases, constant names, literal tuples, and parallel test ids; remove the calendar-only IVA regime alias it kept alive while retaining the canonical external constant and live warning consumers, run focused calendar and external-constant gates, remeasure exact reachability and orphan tests, update cadence, and write the Step Record.

## Scope

- `external constants centralisation part-two census`
- `overview calendar IVA alias`
- `canonical constant and live warning behavior tests`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `D` `src/cadrumo/core/tests/test_external_constants_centralisation_part2.py`
- `M` `src/cadrumo/application/overview/calendar.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/overview/calendar.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/core/tests/test_external_constants.py src/cadrumo/application/overview/tests/test_calendar_regime_warnings.py src/cadrumo/application/overview/tests/test_calendar.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The canonical external constant and live calendar/warning behavior suite remain green at 85 tests. Exact unused symbols improved from 279 to 278; 31 unreachable modules and zero orphaned tests remain.
