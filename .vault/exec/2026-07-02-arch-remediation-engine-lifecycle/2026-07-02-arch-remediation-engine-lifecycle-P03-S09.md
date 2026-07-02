---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S09'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
---

# Add a regression asserting closing a session disposes its engine, verified by pool inspection

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_engine_session_lifecycle.py`

## Description

- Add `test_closing_a_session_disposes_its_engine`: after a real connection, session close replaces the engine's pool,
  observable by pool inspection.

## Outcome

Regression pins that closing a session disposes its engine.

Landed in commit `38e62c216`.

## Notes
