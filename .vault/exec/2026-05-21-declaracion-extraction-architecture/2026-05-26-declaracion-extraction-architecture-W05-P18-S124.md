---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S124'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
---

# `declaracion-extraction-architecture` `W05.P18.S124`

Closed the follow-up no-synthetic-Sede live-surface reconciliation handoff.

- Modified: `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`
- Modified: `.vault/plan/2026-05-26-no-synthetic-sede-live-surfaces-plan.md`
- Created: `.vault/adr/2026-05-26-no-synthetic-sede-live-surfaces-adr.md`
- Created: `.vault/research/2026-05-26-no-synthetic-sede-live-surfaces-research.md`
- Created: `.vault/exec/2026-05-26-no-synthetic-sede-live-surfaces/`

## Description

The declaration-acquisition slice discovered that accepted live-parity policy
allowed AEAT-hosted synthetic input outside acquisition. That follow-up was
promoted into the no-synthetic-Sede research, ADR, implementation plan, schema
guard, registry rewrites, direct Sede guard-policy rewrites, validation gates,
and execution records.

Remaining acquisition fixture rows for modelos 180, 036, 369, 720, and 840 stay
open because they require authorised real fixtures or authenticated read-only
filed declarations. Synthetic data remains prohibited on Sede and all
AEAT-hosted form surfaces.

## Tests

Evidence is recorded in the no-synthetic-Sede `P03.S07` and `P03.S08` step
records. No live Sede call was made in this closure step.
