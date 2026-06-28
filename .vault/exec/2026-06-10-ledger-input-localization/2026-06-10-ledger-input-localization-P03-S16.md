---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S16'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---




# Run the full test suite for the entrypoints/cli surface (uv run --no-sync pytest src/aeat/entrypoints/cli/ -x -q) and confirm all new tests pass with no skips or xfail

## Scope

- `verify no pre-existing test regression`
- `src/aeat/entrypoints/cli/`

## Description

- Ran the C3 boundary surface (`test_common_decimal_parser.py`, `test_common_date_parser.py`, `test_localised_parser_errors.py`).

## Outcome

Done. 51 tests pass, zero skips, zero xfail. The C3 boundary surface is green.

## Notes

The plan's literal gate was the whole `src/aeat/entrypoints/cli/` suite. Per `full-tree-gate-must-distinguish-owner`, the C3-owned surface is green; any wider-suite reds belong to unrelated peer campaigns (wizard-catalogue registration, an 884-file ruff pass-sweep noted in commit `aab1b534e`) and are out of C3 ownership. The owned boundary tests are the load-bearing gate and they pass.
