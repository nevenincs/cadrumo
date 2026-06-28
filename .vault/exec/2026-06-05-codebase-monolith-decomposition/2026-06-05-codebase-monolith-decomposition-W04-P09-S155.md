---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S155'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S155 No-Legacy Production Budget Verification

Scope: verify hard production module and callable budgets after residual decomposition.

## Description

- Ran a direct production inventory over `src/aeat`, excluding tests:
  - no production module over 1250 lines;
  - no production callable over 180 lines.
- Ran the existing module/callable budget tests.
- Ran full Ruff over `src/aeat`.
- Ran compileall over `src/aeat`.
- Fixed a missing `datetime` import in `_clave_movil.py` exposed by full Ruff after the earlier Cl@ve split.

## Verification

- `uv run --no-sync pytest src/aeat/tests/test_codebase_size_budgets.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q`
- direct AST/line inventory: no production module over 1250 lines and no production callable over 180 lines.
- `uv run --no-sync ruff check src/aeat`
- `uv run --no-sync python -m compileall -q src/aeat`
- `uv run --no-sync pytest src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil.py src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_translated_message.py src/aeat/adapters/outbound/aeat/auth/tests/test_smoke.py -q`

## Notes

The no-legacy posture is now encoded directly by S91; the budget tests no longer carry shrinking legacy allowance maps.
