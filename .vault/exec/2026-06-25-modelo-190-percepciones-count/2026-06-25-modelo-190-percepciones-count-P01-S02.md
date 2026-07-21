---
tags:
  - '#exec'
  - '#modelo-190-percepciones-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S02'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-plan]]"
---

# Add a producer-clave gate test refusing a clave-less withholding row

## Scope

- `src/aeat/application/aggregation/tests`

## Description

- Ground current implementation with `uvx vaultspec-rag search "WithholdingObservation clave missing CLI producer test modelo 190" --type code`.
- Add a producer-boundary negative test for a `--withholding-observation` JSON row without `clave`.
- Run lint and the focused producer test file.

## Outcome

- Added `test_parse_withholding_observation_without_clave_is_refused` in `src/aeat/entrypoints/cli/tests/test_withholding_producer.py`.
- The test drives the real `_parse_typed_cli_observations` path and asserts the CLI raises `typer.BadParameter` mentioning `clave`, with the real underlying `pydantic.ValidationError` as its cause.
- Verification passed in `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_withholding_producer.py`: all checks passed.
- Verification passed in `uv run --no-sync pytest -q --tb=short src/aeat/entrypoints/cli/tests/test_withholding_producer.py`: 4 passed.

## Notes

- Test-only change. No fakes, mocks, monkeypatching, skip, or xfail.
