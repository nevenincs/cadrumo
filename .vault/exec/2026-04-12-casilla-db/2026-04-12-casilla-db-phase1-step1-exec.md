---
tags:
  - "#exec"
  - "#casilla-db"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-casilla-db-plan]]"
---

# casilla-db phase1 step1

Scaffolded the new `aeat.domain.casillas` package to avoid the in-flight `aeat.domain.schema`
ownership boundary from issue #9.

- Created: `src/aeat/domain/casillas/__init__.py`
- Created: `src/aeat/domain/casillas/_protocols.py`
- Created: `src/aeat/domain/casillas/errors.py`
- Created: `src/aeat/domain/casillas/models.py`
- Created: `src/aeat/domain/casillas/catalogue.py`

## Description

The new package owns the strict pydantic casilla models, catalogue loader,
verification helpers, protocol stubs for sibling workstreams, and the public
`aeat.domain.casillas` import surface.

## Tests

The package was exercised through focused `ruff`, `ty`, and `pytest` runs
before broader branch verification.
