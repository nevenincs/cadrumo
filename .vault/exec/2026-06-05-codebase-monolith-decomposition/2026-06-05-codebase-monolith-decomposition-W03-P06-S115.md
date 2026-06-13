---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S115'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S115 Live Filed-Data Capture Extraction

Scope: `src/aeat/application/live/__init__.py`, `src/aeat/application/live/_session.py`, `src/aeat/application/live/_filed_observation_persistence.py`, `src/aeat/application/live/_filed_data_capture.py`, `src/aeat/application/live/tests/test_filed_bulk_capture.py`, `src/aeat/application/live/tests/test_filed_capture_calculation_history.py`, `src/aeat/entrypoints/cli/tests/test_registry_cli.py`.

## Description

- Used RAG/direct source tracing to locate filed-data listing, capture, bulk capture, source capture, session acquisition, and filed-observation calculation-history enrollment.
- Extracted live session acquisition into `_session.py`.
- Extracted filed-observation calculation-history persistence into `_filed_observation_persistence.py`.
- Extracted filed-data listing/capture orchestration into `_filed_data_capture.py`.
- Kept `aeat.application.live` as the public facade for CLI and tests.
- Preserved legacy public helpers used by existing tests: `filed_data_listing_row`, `select_declarations_for_capture`, and `_persist_latest_filed_calculation_observations`.

## Outcome

Filed-data capture orchestration no longer lives in the live package root. The CLI still imports through the public `aeat.application.live` facade.

## Verification

- `uv run --no-sync ruff check src/aeat/application/live/__init__.py src/aeat/application/live/_session.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/live/_filed_data_capture.py src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed.
- `uv run --no-sync pytest -q -m "unit or integration" src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed: 64 tests.
- `uv run --no-sync python -c "import aeat.application.live as live; ..."` passed and showed `capture_filed_data`, `capture_filed_data_bulk`, and `list_filed_data` exported from `_filed_data_capture`.

## Notes

`src/aeat/application/live/__init__.py` is reduced but remains above the 1250-line target. Residual live-root decomposition is still required before the whole codebase can satisfy the monolith objective.
