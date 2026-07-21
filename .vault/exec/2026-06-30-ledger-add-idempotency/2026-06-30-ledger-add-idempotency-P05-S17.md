---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S17'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Add a test proving two non-granting verify retries with identical findings collapse to one report while a changed-finding re-verify produces a distinct report

## Scope

- `src/aeat/application/modelo/tests/`

## Description

- Add a real-behaviour application test (`test_verify_report_idempotent_collapse.py`) driving the real `verify_modelo_revision` against the real registry and the encrypted verification-report catalogue - no mocks.
- Prove two identical non-granting verify retries at different clocks collapse onto one stored report (same id, last-seen `run_at` wins), and a distinct outcome (different actor) yields a distinct retained report.

## Outcome

Landed in commit `6ee60da17`; 2 tests pass. Reuses the M180 non-granting scenario from the file-flow support module so the setup is the same real path the existing verify-flow suite exercises.

## Notes

The end-to-end verify path was transiently red earlier from an unrelated peer M390 registry edit (a new simplificado relation not yet covered by its dependency classification); the peer landed the coverage fix and the full verify-flow suite plus this test are green.
