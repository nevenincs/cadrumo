---
tags:
  - '#exec'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S06'
related:
  - "[[2026-07-02-arch-remediation-source-kind-deferrals-plan]]"
---

# Migrate the foreign_asset deferral to a structured annotation citing this deferrals ADR with no promotion date and the M720 next-hardening-campaign review trigger

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Migrate the `foreign_asset` (M720) deferral to a structured target citing the deferrals ADR, M720 next-hardening review trigger.

## Outcome

M720 foreign-asset is governed.

## Notes
