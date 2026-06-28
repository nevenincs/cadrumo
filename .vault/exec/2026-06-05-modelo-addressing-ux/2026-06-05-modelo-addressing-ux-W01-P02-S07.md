---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S07'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P02.S07 - legacy root size budget tightening

Scope: tighten module size budgets after the baseline extraction slice.

## Description

- Lower the `_modelo.py` legacy module budget from 4300 lines to the measured 4248-line baseline.
- Preserve existing function-level budgets for known legacy command bodies until their extraction slices land.
- Run the static size guard lane.

## Outcome

`_modelo.py` can no longer grow beyond the current baseline without failing the static size guard. Future extraction slices should lower the module budget again after each successful removal from the legacy root.

## Notes

Verification: `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_module_size.py -q` passed.
