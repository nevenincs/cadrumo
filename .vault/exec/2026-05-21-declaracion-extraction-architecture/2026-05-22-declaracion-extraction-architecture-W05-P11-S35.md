---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S35'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-W03-P07-S21]]'
---

# W05.P11.S35 - M190 real declaration round-trip

BLOCKED. The local corpus has a real Modelo 190 fixture for exercise 2024 (`src/aeat/tests/fixtures/justificantes/190/2024-0A.pdf`), but the committed M190 registry only declares revision `2025-y-siguientes` with `period_selector = { year_from = 2025, periods = ["0A"] }`.

Evidence checked:
- `src/aeat/tests/fixtures/justificantes/190/2024-0A.pdf` exists and extracts as a 2024 Modelo 190 declaration/receipt bundle.
- `src/aeat/_data/registry/aeat/modelos/190.toml` has `modelo-190-declaracion-pdf`, but only under the 2025-y-siguientes revision.
- `parse_declaracion(... modelo_override="190", año_override=2024, period_override="0A")` fails before extraction because no 2024 registry snapshot exists.

Action taken:
- Added backlog prerequisite `W05.P11.S93` to acquire a 2025-or-later Modelo 190 fixture or legally source a 2024 revision before implementing S35.

No code changes for S35.
