---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:76668ef089548dccbc6afdb6f5701664eae561f7f216bbd9f28bd9d1ad7c38ba'
step_id: 'S58'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S58 Live Facade Verification

Scope: `src/aeat/application/live/tests`, `src/aeat/entrypoints/cli/tests/test_live*`.

## Description

- Run semantic discovery for live facade verification coverage.
- Verify `aeat.application.live` imports successfully in a fresh process.
- Run live application tests and focused live CLI tests.
- Run ruff over live application and focused live CLI test surfaces.

## Outcome

All focused live verification passed. The earlier import-time `NameError` did not reproduce in a fresh process.

## Notes

Verification passed with 185 selected tests and ruff.
