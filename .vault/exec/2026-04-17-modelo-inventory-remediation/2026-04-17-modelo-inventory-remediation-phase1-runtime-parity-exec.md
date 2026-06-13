---
name: 2026-04-17-modelo-inventory-remediation-phase1-runtime-parity
description: Phase 1 execution record — runtime and registry parity remediation for modelo inventory gaps
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
---

# `modelo-inventory` `phase1` `runtime-parity`

Applied the core remediation patch set across the registry, deadline engine, and CLI parity surface.

- Modified: `src/aeat/domain/modelos/_entries/modelo_036.py`
- Modified: `src/aeat/domain/modelos/_entries/modelo_037.py`
- Modified: `src/aeat/domain/modelos/_entries/modelo_111.py`
- Modified: `src/aeat/domain/modelos/_entries/modelo_123.py`
- Modified: `src/aeat/domain/modelos/_entries/modelo_130.py`
- Modified: `src/aeat/domain/modelos/_entries/modelo_347.py`
- Created: `src/aeat/domain/modelos/_entries/modelo_193.py`
- Modified: `src/aeat/domain/modelos/_codes.py`
- Modified: `src/aeat/domain/modelos/_registry.py`
- Modified: `src/aeat/domain/modelos/_cli.py`
- Modified: `src/aeat/domain/deadlines/_models.py`
- Modified: `src/aeat/domain/deadlines/_applies.py`
- Modified: `src/aeat/domain/deadlines/_calendar.py`

## Description

The remediation closed the audited contract split between `aeat.domain.modelos` and `aeat.domain.deadlines`.

- `modelo 037` is now retained as historical-only metadata and no longer appears as a current censal path for active profile applicability.
- `modelo 036` now documents the post-`2025-02-03` censal path after the legal suppression of `037`.
- `modelo 123` now resolves to `modelo 193`, and `modelo 193` is present in the registry as the annual counterpart for the capital-mobiliario retención family.
- `AutonomoProfile` gained explicit booleans for professional-fee retentions, the `130` 70% professional-income withholding exception, and the `347` threshold gate.
- The deadline engine now computes `111` and `190` from real withholding outflows, applies the `130` exception correctly, and emits `347` annual obligations when the threshold flag is active.
- The internal rule table was upgraded to a strict pydantic model to respect the project's no-bare-dataclass discipline in this area.

## Tests

Focused unit verification passed after the runtime patch:

- `uv run pytest src/aeat/domain/modelos/test_codes.py src/aeat/domain/modelos/test_registry.py src/aeat/domain/modelos/test_cli.py src/aeat/domain/deadlines/test_models.py src/aeat/domain/deadlines/test_calendar.py src/aeat/domain/deadlines/test_applies.py src/aeat/domain/deadlines/test_engine.py -q`
- Result: `95 passed`
