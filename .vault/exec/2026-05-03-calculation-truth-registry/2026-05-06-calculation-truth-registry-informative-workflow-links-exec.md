---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `informative-modelos` `workflow-links`

Closed missing workflow application-link gates for the greenfield informative
Modelo 232 and Modelo 720 registry foundations.

- Modified: `registry/aeat/modelos/232.toml`
- Modified: `registry/aeat/modelos/720.toml`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_232_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_720_registry.py`

## Description

Modelo 232 and Modelo 720 now declare registry-snapshot gates for review,
approval, reconciliation, and workflow consumers. These links are attached to
the existing informative constructs for every supported revision.

The models remain informative-only: no formulas, cross-model calculation
relations, legal constants, or Python-side legal truth were added. The behavior
tests prove the new workflow surfaces are present, require snapshots, and are
construct-scoped.

Live sanitized filed-data fixtures remain open plan rows because the current
authenticated discovery recorded no filed declarations for the test NIF.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_232_registry.py src/aeat/domain/calculations/registry/test_modelo_720_registry.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_232_registry.py src/aeat/domain/calculations/registry/test_modelo_720_registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_232_registry.py src/aeat/domain/calculations/registry/test_modelo_720_registry.py`
