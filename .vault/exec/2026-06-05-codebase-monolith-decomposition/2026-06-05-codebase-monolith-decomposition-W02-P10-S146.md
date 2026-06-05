---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S146'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S146 Config Budget Verification

Scope: `src/aeat/entrypoints/cli/_config/tests`; `src/aeat/entrypoints/cli/tests`; `src/aeat/tests/test_codebase_size_budgets.py`.

## Description

- Verified the residual config callable splits and stale-path budget repair together.
- Re-ran locale audit after removing retired profile `switch` help strings and tightening stub-refusal legal anchors.

## Outcome

- `ruff check` passed on the touched config, locale-adjacent test, and budget files.
- `python -m aeat.locales audit` passed for `ca`, `en`, `es`, and `hu`.
- `pytest -m "unit or integration"` passed for config lifecycle, cross-profile unlock, config surface inventory, profile lifecycle, CLI module size, and codebase size-budget checks.

## Notes

- No skipped or xfailed verification was introduced.
