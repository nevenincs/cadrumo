---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:b101d8aa418deeb3788454f2a8534c98e377d00f626a6b4b0348241420d39141'
step_id: 'S179'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Wire the existing hedged register-scoping classifier at the discovery boundary where profile facts, offered options, and date coexist, carry its result through the discovery report, and preserve it through both filed-history onboarding outcomes instead of publishing a literal inconclusive placeholder.

## Scope

- `filed-history discovery and onboarding composition`
- `operation projection tests`
- `production-metastate gate`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/application/live/filed_data_capture.py`
- `M` `src/cadrumo/application/live/tests/test_filed_history_discovery.py`
- `M` `src/cadrumo/application/live/tests/test_filed_history_operation.py`
- `verify:` `uv run ruff check <S179 Python paths>` -> `pass`
- `verify:` `uv run pytest -q -n0 src/cadrumo/application/live/tests/test_filed_history_discovery.py src/cadrumo/application/live/tests/test_filed_history_operation.py` -> `pass` (43 passed; 18 integration-marker deselections)
- `verify:` `uv run pytest -q src/cadrumo/application/live/tests/test_filed_history_discovery.py src/cadrumo/application/live/tests/test_filed_history_operation.py src/cadrumo/application/live/tests/test_filed_history_onboarding.py src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py` -> `pass` (78 passed)
- `verify:` `git diff --check -- <S179 paths>` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `fail` (one live finding)
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail` (353 exact symbols; 18 orphan test modules)

## Notes

The zero-target metastate gate improved from two findings to one. The exact unused signal improved from 354 to 353 while orphan tests remained at 18. The remaining selection-row projection requires its own capture-pipeline ownership step.
