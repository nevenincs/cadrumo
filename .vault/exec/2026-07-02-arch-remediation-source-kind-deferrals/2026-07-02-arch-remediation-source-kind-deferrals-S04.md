---
tags:
  - '#exec'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:85f7265c94b6a117e911adc2c0d8fb791078311aeab23272a0618a841a17c056'
step_id: 'S04'
related:
  - "[[2026-07-02-arch-remediation-source-kind-deferrals-plan]]"
---

# Migrate the atribucion_member deferral to a structured annotation citing this deferrals ADR with no promotion date and the M184 next-hardening-campaign review trigger

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Migrate the `atribucion_member` (M184) deferral to a structured target citing the deferrals ADR, no promotion date, M184 next-hardening-campaign review trigger.

## Outcome

M184 atribución is governed with a per-modelo review trigger.

## Notes
