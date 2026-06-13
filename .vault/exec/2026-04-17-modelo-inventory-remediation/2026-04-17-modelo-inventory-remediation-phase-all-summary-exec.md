---
name: 2026-04-17-modelo-inventory-remediation-phase-all-summary
description: Phase-all summary for the modelo inventory remediation after the original #108 delivery
type: exec
tags:
  - "#exec"
  - "#modelo-inventory"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-modelo-inventory-remediation-plan]]"
  - "[[2026-04-17-modelo-inventory-remediation-adr]]"
  - "[[2026-04-17-modelo-inventory-remediation-research]]"
  - "[[2026-04-17-modelo-inventory-remediation-phase1-runtime-parity-exec]]"
  - "[[2026-04-17-modelo-inventory-remediation-phase2-setup-parity-exec]]"
  - "[[2026-04-17-modelo-inventory-remediation-phase3-green-gates-exec]]"
---

# `modelo-inventory` `phase-all` summary

Remediation completed for the audited post-#108 parity gaps between the modelo registry, the deadline engine, and the setup/profile-authoring path.

- Modified: `src/aeat/domain/modelos/*`
- Modified: `src/aeat/domain/deadlines/*`
- Modified: `src/aeat/application/setup/*`
- Created: `src/aeat/domain/modelos/_entries/modelo_193.py`

## Description

High-level delivery:

- Corrected the censal posture so `037` is treated as historical-only after its legal suppression date and `036` is documented as the current path.
- Implemented the real `130` professional withholding exception instead of the prior unconditional rule.
- Added annual `347` scheduling behind an explicit threshold flag so `year-plan` and the deadline engine no longer silently omit it.
- Restored `123 -> 193` annual-summary parity in the registry.
- Expanded the shared profile contract and the setup surface so the same legal traits flow through registry, runtime planning, and generated profile files.

## Tests

Verification stack:

- Focused registry/deadline tests: `95 passed`
- Setup/deadline-cli/workflow consumers: `62 passed`
- Full repo gate: `just test` -> `765 passed, 1 skipped, 23 deselected`
- Static and formatting gates: `just lint`, `just typecheck`, `just hooks` -> all passed
