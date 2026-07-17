---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Confirm the M210 continuity suite and the convenio-doble-imposicion suites pass unmodified against the typed outcome

## Scope

- `src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`

## Description

- Run the M210 formula-runtime contract suite.
- Run the M210 convenio rate-resolution verification suite.
- Run the M210 IRNR multi-year continuity suite.

## Outcome

The focused W1 continuity gate passed: `32 passed in 22.49s`.

## Notes

Full pytest output is stored in `_scratch-codex/w1_m210_convenio_pytest.log`.
