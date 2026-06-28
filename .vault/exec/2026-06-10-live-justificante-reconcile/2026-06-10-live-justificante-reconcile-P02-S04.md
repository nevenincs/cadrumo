---
tags:
  - '#exec'
  - '#live-justificante-reconcile'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S04'
related:
  - "[[2026-06-10-live-justificante-reconcile-plan]]"
---




# Add the require_live_read-gated async capture_justificante_snapshot orchestrator (period-aware expediente resolution, capture_justificante, service.capture) and promote it plus the service to the package top-level re-exports.

## Scope

- `src/aeat/application/live/__init__.py`

## Description

- Add `resolve_period_expediente` (pure): cross-reference the period-bearing
  declarations against the procedure tree by `expediente_id`, refusing on
  missing-period or absent-from-tree rather than wrong-quarter fallback.
- Add the `require_live_read`-gated async `capture_justificante_snapshot`
  orchestrator wiring resolution + `capture_justificante` + service persistence,
  with four seam providers (defaulting to the live sede implementations).
- Promote the service, payload types, the resolver, and the orchestrator to the
  `application.live` top-level re-exports; type the seams for pyright strict.

## Outcome

Re-exports import clean; pyright strict 0 errors; broad collection clean.
Landed as commits `15debafc8` (orchestrator/resolver) and `bf76b73e2` (typing).

## Notes

`Expediente` (procedure tree) carries no period, so the period-bearing
declarations register is the disambiguation surface — the resolver bridges the
two. The seam providers are real-typed-record injection, not mocks. No scaffolds.
