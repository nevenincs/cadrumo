---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S56'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S56 Ledger Actions Verification

Scope: `W03.P06.S56` verifies application ledger action behavior and facade imports after decomposition.

## Description

- Smoke-test `aeat.application.ledger` facade imports for import, manual mutation, split/merge, export, and bulk classification services.
- Run application ledger action, split, and merge behavior tests.
- Run focused CLI ledger validation and UX integration tests that consume the backend services through the transport layer.
- Repair ledger CLI fixture-root references to consume the centralized `FIXTURES_DIR` facade.
- Rewire LLM classification helper imports to the centralized ledger action common helper module.
- Run Ruff over the ledger application package and focused CLI ledger test files.

## Outcome

Ledger action behavior remains intact after decomposition. The latest verification run reported 213 passing application ledger tests, 186 passing focused CLI ledger tests across split chunks, 2 passing CLI module-size tests, and no Ruff findings.

## Notes

The combined CLI ledger lane exceeded the shell timeout as one batch, so the same collected tests were rerun in split chunks. The split chunks all passed. The CLI integration run emitted third-party `ofxparse` deprecation warnings for `findAll`; no test failure or application regression was observed.
