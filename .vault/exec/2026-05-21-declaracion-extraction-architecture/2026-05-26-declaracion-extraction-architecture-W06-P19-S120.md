---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W06.P19.S120'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-convention-hardening-audit]]'
---

# declaracion-extraction-architecture W06.P19.S120

Closed the remaining `JustificanteRepository` import-cycle regression with a
fresh-process public-surface test.

- Modified: `src/aeat/domain/justificante/test_vocabulary_stable.py`

## Description

The package-level lazy export introduced during `W06.P19.S113` was sufficient:
fresh-process imports of declaration/PDF error surfaces and
`aeat.domain.justificante.JustificanteRepository` now complete successfully.

This step added a regression test that starts a clean Python interpreter,
imports `DeclaracionObservation`, then imports `JustificanteRepository` through
the domain public surface. That reproduces the order that originally exposed
the partially initialized secure-storage crypto/sql cycle.

## Tests

- `uv run --no-sync ruff check src\aeat\domain\justificante\__init__.py src\aeat\domain\justificante\test_vocabulary_stable.py`
- `uv run --no-sync pytest -x src\aeat\domain\justificante\test_vocabulary_stable.py -q`
