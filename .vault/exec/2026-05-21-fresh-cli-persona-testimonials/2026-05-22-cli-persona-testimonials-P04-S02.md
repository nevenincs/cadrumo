---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'P04.S02'
related:
  - '[[2026-05-21-cli-persona-testimonials-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-P10-S45]]'
---

# P04.S02 - profile bindings and estimacion-directa channel

Closed as already satisfied in the current worktree.

Implementation and test evidence:
- Profile-sourced Modelo 100 bindings resolve from the active profile without caller input in `src/aeat/application/modelo/test_profile_binding.py`.
- CCAA profile facts use the enum binding channel, while the `estimacion-directa-es-normal` typed-enum registry binding remains a Decimal-consumed binding.
- CLI discovery rows now label `source = "profile"` as `profile fact`, per the cross-campaign hardening repair in `P10.S45`.

Verification:
- `uv run --no-sync pytest -x src\aeat\application\modelo\test_profile_binding.py src\aeat\entrypoints\cli\test_modelo_discovery_defects.py` -> 31 passed.
- `uv run --no-sync ruff check src\aeat\application\modelo\_actions.py src\aeat\application\modelo\test_declaration_period_binding.py src\aeat\application\modelo\test_profile_binding.py src\aeat\entrypoints\cli\test_modelo_discovery_defects.py` -> passed.
