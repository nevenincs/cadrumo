---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S145'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P20.S145 CLI size and complexity guard

Scope:
- `src/aeat/entrypoints/cli/test_cli_module_size.py`

## Description

- Add a static module-size budget for production CLI files.
- Apply an 800-line default limit to ordinary CLI modules.
- Freeze known legacy monoliths with explicit line budgets so future changes cannot grow them.
- Add a command/registrar body line-budget guard with explicit legacy rows for existing overgrown command bodies.

## Outcome

- Newly extracted modules cannot silently become replacement monoliths.
- `_modelo.py`, `_ledger.py`, `_app_live.py`, and other known large legacy files cannot grow without the guard failing.
- Overgrown command functions are visible as named debt rows and cannot increase past their current budgets.

## Notes

- This guard prevents regression and makes remaining monolith debt measurable. It does not claim that `_modelo.py` is already healthy.

Verification:
- `.venv\Scripts\pytest.exe src/aeat/entrypoints/cli/test_cli_module_size.py -q` - passed as part of the 25-test focused gate.
