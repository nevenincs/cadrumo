---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S15'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Replay weak IVA cross-period company and pos-chain persona roots

## Scope

- `tmp/personas`

## Description

- Replayed the weak IVA cross-period, company, and pos-chain testimony against
  the current wallet and refund/carry implementation.
- Grounded the replay with `uvx vaultspec-rag` before drawing conclusions.
- Treated stale transcript claims as evidence leads only; current CLI and test
  behavior controlled closure.

## Outcome

No current product defect reproduced. Current code exposes `iva-wallet override`
for taxpayer override authority, first-period zero remains grounded in
activity-start and registry conditions, and company REDEME/refund/carry behavior
has explicit application coverage. The stale open testimony language is now
artifact drift rather than a live calculation blocker.

## Notes

Verification evidence included 4 focused first-period/wallet tests, 9
carry/refund tests, 2 verify/export guard tests, and a valid-UUID CLI replay
showing override guidance and taxpayer override selection.
