---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S05'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W03.P03.S05 - live Modelo 036 censo refresh attempt

## Description

- Ran the active-profile authentication and profile status probes.
- Removed the orphaned read process from this verification run after it held the live-auth lock.
- Retried the live Modelo 036/G313 censo refresh after the local lock owner was stopped.

## Outcome

- `config auth status` reported `clave_movil` configured, authenticated, and available for the active profile.
- `config profile status` reported active profile `live-iva-readonly-20260602`, with tax id present, activity present, `iva.regime = GENERAL`, and `tax_residence.ccaa = madrid`.
- `config profile censo show` refused because no censo snapshot exists for the active profile.
- `config profile censo refresh` reached the AEAT auth path but failed before G313 capture because AEAT refused a new Cl@ve Movil push while a previous petition remained pending server-side.
- The concrete live blocker was `AUTH_AUTH_CLAVE_MOVIL_CLAVE_MOVIL_APPROVAL_TIMEOUT` with `failure_mode = pending_petition_blocked`.

## Notes

- No censo snapshot was captured in this step.
- The next live attempt requires the operator to reject pending Cl@ve requests in the mobile app or wait for AEAT to expire them, then rerun `config profile censo refresh`.
