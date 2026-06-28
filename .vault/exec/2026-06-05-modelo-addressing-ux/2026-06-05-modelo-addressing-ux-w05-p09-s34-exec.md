---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S34'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W05.P09.S34 focused regression cadence

Scope:
- `src/aeat/application/modelo`
- `src/aeat/entrypoints/cli`

## Description

- Ran focused application selector and addressing regressions after application facade changes.
- Ran focused natural-key and UX CLI regressions after calculate extraction.
- Ran real CLI calculate regressions.
- Ran row flag parser and persistence/rendering regressions.
- Ran compile and Ruff gates for touched application and CLI files.

## Outcome

Focused regressions for the touched command group pass. The calculate flow remains on the natural-key work addressing path and delegates calculation input policy to application services.

## Verification

- `uv run --no-sync pytest src/aeat/application/modelo/test_selectors.py src/aeat/application/modelo/test_work_addressing.py -q` passed with 15 tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/test_modelo_work_ux.py -q` passed with 22 tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py -q` passed with 5 tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_work_calculate_row_flag.py -q` passed with 33 tests.
- `uv run --no-sync ruff check ...` passed for touched files.
- `uv run --no-sync python -m compileall -q ...` passed for touched files.

## Notes

- The combined calculate and row-flag lane exceeds the previous shared timeout on this workstation, so the tests were run as separate real-behavior lanes.
