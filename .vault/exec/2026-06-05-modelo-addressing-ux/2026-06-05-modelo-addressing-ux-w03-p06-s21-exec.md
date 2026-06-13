---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S21'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W03.P06.S21 calculate extraction real CLI regressions

Scope:
- `src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py`

## Description

- Ran the focused real CLI calculation regression lane after calculate command extraction and support-helper relocation.
- Verified the extracted calculate command remains reachable through the public CLI and still produces real calculation output.

## Outcome

The existing natural-key and real calculation CLI regression lane passes after the calculate extraction.

## Verification

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py -q` passed with 5 tests.

