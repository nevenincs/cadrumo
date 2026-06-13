---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S138'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S138 Modelo Filing Extraction Verification

Scope: verify residual modelo filing extraction preserves filing records, supersession, and public facade imports.

## Verification

- `uv run --no-sync ruff check --fix src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_filing_actions.py src/aeat/application/modelo/_verification_actions.py`
- `python -m compileall src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_filing_actions.py src/aeat/application/modelo/_verification_actions.py`
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_file_flow.py -q`
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_verificado_completo_regression.py -q`
- Direct import smoke for public and `_actions.py` filing/report facades.

Result: lint passed, compile passed, 30 file-flow tests passed, 18 export/verificado tests passed, and facade import smoke passed. The test runs still emit the existing pydantic validator warning in `src/aeat/domain/deadlines/_models.py`.
