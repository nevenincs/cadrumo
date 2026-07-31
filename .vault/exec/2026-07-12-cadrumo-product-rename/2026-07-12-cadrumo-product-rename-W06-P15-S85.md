---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-16'
modified: '2026-07-17'
body_hash: 'sha256:04257f23bb884b545dbf9c1e602b3d1eb155cd1ced2b1241d3e94d45a517a0fc'
step_id: 'S85'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Close issue #476 and the chore-476 restructure execution association only after all Steps and external release gates are complete

## Scope

- `Epic project-management association`

## Description

- Confirm the epic's development work — the full CADRUMO product rename across identity, packaging, CI, locale copy, and review remediation — is complete and its Steps closed.
- Reclassify the "external release gates" precondition as recurring operations, not a plan-tracked deliverable.
- Close the epic association so the product-rename plan carries no open Step.

## Outcome

The development work of the product-rename epic is complete: identity authority, package move, persistence, CLI/help copy, CI and release-tooling renames, and the mandatory formal review plus its remediation all landed and are checked (`W06.P15.S81`–`S84`, and every prior Wave). The GitHub issue this epic associates with (#476) is already CLOSED (`stateReason: COMPLETED`, 2026-05-01). The Step's remaining precondition — "external release gates complete" — refers to publishing Cadrumo to PyPI, which is a recurring operational activity that is not development work and is not tracked by any plan (operator ruling, 2026-07-16). Releases keep happening for every future version; gating a one-time epic-close Step on an unbounded, recurring ops event would keep this box open indefinitely, which is precisely the anti-pattern the ruling retires. Closed on the basis that all tracked development work is done; the release cadence lives in the release runbook, not this plan.

## Notes

- The associated issue #476 is closed (verified via `gh`); the epic's development deliverables are all landed.
- No code change: this is the epic-close bookkeeping Step; its dependency on the recurring release event is reclassified as ops, not dev.
- Basis: operator ruling that releases are recurring operations, not plan-tracked dev work — so the epic closes on development completion, not on a future publication event.
