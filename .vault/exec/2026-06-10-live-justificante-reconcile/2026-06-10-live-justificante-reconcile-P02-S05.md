---
tags:
  - '#exec'
  - '#live-justificante-reconcile'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S05'
related:
  - "[[2026-06-10-live-justificante-reconcile-plan]]"
---




# Prove period disambiguation (1T vs 2T resolve to distinct expedientes, never the wrong quarter) and orchestrator wiring offline with a real service and a seam-injected session.

## Scope

- `src/aeat/application/live/tests/test_justificante_capture_resolution.py`

## Description

- Prove the primary risk: 1T and 2T resolve to distinct expedientes and the two
  quarters never collapse to one.
- Prove the refusals: a missing-period and an expediente-absent-from-tree both
  raise rather than fall back; a re-filed period resolves to the latest filing.
- Wire `capture_justificante_snapshot` offline with seam-injected typed sede
  records (a cast sentinel session) and the real persistence service against an
  isolated bucket; assert the 2T receipt persists against its own expediente.

## Outcome

Six tests pass; pyright/ruff clean. Landed as commit `df...` in the S05 commit
and the typing follow-up `bf76b73e2`.

## Notes

The seam providers return real `Declaracion` / `Expediente` / `SedeCapture`
records (constructed with `AnyHttpUrl`), not mocks; only the session is a cast
sentinel since the providers ignore it. No incidents.
