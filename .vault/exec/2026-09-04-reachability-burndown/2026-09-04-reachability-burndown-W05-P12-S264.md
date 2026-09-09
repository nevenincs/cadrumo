---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:9663ecb1a2702007e17dbc4d505dce1e84873f0ec31acbab683ecd9e003c4dd1'
step_id: 'S264'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only justificante metadata persistence facade in favor of the live enrollment owner that performs the same parsing and persistence plus atomic filing stamping; remove facade-specific tests and exports while retaining enrollment, mismatch, and conflict coverage, run focused filed-capture gates, remeasure exact reachability, update cadence, and write the Step Record.

## Scope

- `filed observation justificante persistence facade and dedicated tests`
- `live enrollment behavior tests`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `M` `src/cadrumo/application/live/filed_observation_persistence.py`
- `M` `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/live/filed_observation_persistence.py src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py -k "justificante"` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m integration src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py -k "justificante"` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

All six justificante-focused tests now exercise the live enrollment owner and pass. The explicit integration command selected no tests because this file's 45 tests are unit-marked; it was recorded as no evidence, not a green gate. Exact unused symbols improved from 281 to 280; 31 unreachable modules and zero orphaned tests remain.
