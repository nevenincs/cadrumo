---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S72'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W04.P06.S72` Reconciliation natural-key audit

Step scope: `docs/how-to/reconcile.md`.

## Description

- Confirm `aeat app modelo reconcile` accepts modelo, year, period, revision, and exact work-unit addressing.
- Rewrite the reconciliation guide around the visible filing target instead of copied work-unit IDs.
- Document exact work-unit IDs as an advanced automation escape hatch.
- Verify educational-doc command and link conformance against the live docs test lane.

## Outcome

The reconcile how-to now uses `aeat app modelo reconcile --modelo 303 --year 2026 --period 1T --from-justificante ./justificante.pdf` as the normal operator path. It documents registry-revision ambiguity as a refusal that should be resolved with `--revision`, while preserving exact work-unit IDs for advanced automation.

Verification passed with `.venv\Scripts\python.exe -m pytest -m docs src/aeat/entrypoints/cli/test_educational_docs_conformance.py`.

## Notes

Direct CLI help probing with `.venv\Scripts\aeat.exe app modelo reconcile --help` was blocked by an unrelated duplicate error-code registration during CLI startup: `REFUSED_MODELO_PROJECT_INVALID_DECIMAL_OVERRIDE`. The reconcile signature was confirmed directly in `src/aeat/entrypoints/cli/_modelo.py`.
