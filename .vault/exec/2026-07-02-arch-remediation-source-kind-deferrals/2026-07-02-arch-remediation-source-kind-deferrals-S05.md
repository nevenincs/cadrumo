---
tags:
  - '#exec'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:ded57ab7e2a910e5d60e9148ae55a3f539b6312a5efd0c783e161a9dde1c8f8b'
step_id: 'S05'
related:
  - "[[2026-07-02-arch-remediation-source-kind-deferrals-plan]]"
---

# Migrate the related_party_operation deferral to a structured annotation citing this deferrals ADR with no promotion date and the M232 next-hardening-campaign review trigger

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Migrate the `related_party_operation` (M232) deferral to a structured target citing the deferrals ADR, M232 next-hardening review trigger.

## Outcome

M232 related-party is governed.

## Notes
