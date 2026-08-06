---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:d4ad17f6cd88e2a88739b3365ceaddfc5c9c83711a54acdf9fa584cf49b4ade3'
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
