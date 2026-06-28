---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'P04.S01'
related:
  - '[[2026-05-21-cli-persona-testimonials-plan]]'
---

# P04.S01 - work-unit metadata declaration inputs

Closed as already satisfied in the current worktree.

Implementation evidence:
- `src/aeat/application/modelo/_actions.py` resolves informational casillas whose semantic roles are `filing_year` and `filing_period` through `_resolve_declaration_period_inputs`.
- `calculate_modelo_revision` merges these declaration-period inputs before calling `calculate_registry_snapshot`.
- The resolver maps registry-native period tokens including quarterly, annual, monthly, and Modelo 202 pago-fraccionado tokens to Decimal ordinals for the engine.

Verification:
- `uv run --no-sync pytest -x src\aeat\application\modelo\test_declaration_period_binding.py` -> 9 passed.
- `uv run --no-sync ruff check src\aeat\application\modelo\_actions.py src\aeat\application\modelo\test_declaration_period_binding.py src\aeat\application\modelo\test_profile_binding.py src\aeat\entrypoints\cli\test_modelo_discovery_defects.py` -> passed.

