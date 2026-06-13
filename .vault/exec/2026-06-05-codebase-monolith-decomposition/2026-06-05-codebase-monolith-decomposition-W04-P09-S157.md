---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S157'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S157 Declarations Register Split

Scope: `src/aeat/adapters/outbound/aeat/sede/_declarations.py`, `src/aeat/adapters/outbound/aeat/sede/_declarations_diagnostics.py`, `src/aeat/adapters/outbound/aeat/sede/_declarations_remote.py`, and the focused declarations adapter tests.

## Description

- Extract declarations-register diagnostics into `_declarations_diagnostics.py`.
- Extract remote-read guard and cotejo CSV helpers into `_declarations_remote.py`.
- Keep `_declarations.py` as the declarations-register facade and preserve existing private compatibility names needed by tests.
- Split the oversized declarations adapter test module into shared support plus three focused part modules.
- Leave the broader production residual row open for core config and record-design surfaces.

## Outcome

The declarations adapter production facade is under the 1250-line guard, and the declarations adapter test monolith is replaced by focused real-behavior tests without duplicating production logic.

## Notes

Verification passed for Ruff on the declarations production and test split surface, compileall for `src/aeat/adapters/outbound/aeat/sede`, a facade `__all__` smoke import, 61 focused declarations tests, and the 2-test hard codebase size-budget guard.
