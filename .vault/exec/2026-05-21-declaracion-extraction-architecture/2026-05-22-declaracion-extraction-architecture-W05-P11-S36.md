---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-22'
modified: '2026-07-17'
body_hash: 'sha256:bc86e94b5a53f7740c41141f1dd8c144ffa022bbda6e68533816d6e1f59db7da'
step_id: 'S36'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-W04-P10-S28]]'
---

# W05.P11.S36 - M036 real declaration round-trip

BLOCKED. The M036 registry has `modelo-036-declaracion-pdf`, but W04.P10.S28 explicitly records its label patterns as provisional because they were derived from registry labels/instructions, not from a real printed declaration PDF.

Evidence checked:
- No Modelo 036 PDF fixture exists under `src/aeat/tests/fixtures/`.
- `src/aeat/_data/registry/aeat/modelos/036.toml` has a `declaracion_pdf` profile for 2025+, but its source comment states the corpus lacks a real printed-form specimen.

Action taken:
- Added backlog prerequisite `W05.P11.S94` to acquire a real Modelo 036 printed-form PDF fixture before implementing S36.

No code changes for S36.
