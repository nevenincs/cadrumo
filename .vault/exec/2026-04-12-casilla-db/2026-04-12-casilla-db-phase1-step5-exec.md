---
tags:
  - "#exec"
  - "#casilla-db"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-casilla-db-plan]]"
---

# casilla-db phase1 step5

Added test coverage and contributor documentation for the new workflow.

- Created: `src/aeat/domain/casillas/test_smoke.py`
- Created: `src/aeat/domain/casillas/_test_catalogue.py`
- Created: `src/aeat/domain/casillas/_test_cli.py`
- Created: `src/aeat/domain/casillas/test_live_cli.py`
- Created: `docs/casillas.md`
- Modified: `README.md`

## Description

Documented how to add a new `(modelo, period)` catalogue and added colocated
tests for schema validation, CLI behavior, and the deferred issue-21 live-test
boundary.

## Tests

`pytest` now includes dedicated casillas unit coverage and opt-in live test
placeholders for each of the three canonical catalogues.
