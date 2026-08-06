---
tags:
  - '#exec'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:a35c14f8470bccb39250fcbed9661de6de0be43e488779cfdd983015d43bddda'
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
