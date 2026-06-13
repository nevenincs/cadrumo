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



# `calculation-truth-registry` `modelo-200` `application-links`

Closed the Modelo 200 workflow application-link surface for the current
registry foundation.

- Modified: `registry/aeat/modelos/200.toml`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_200_registry.py`

## Description

Modelo 200 now declares registry-snapshot gates for review, approval,
reconciliation, and workflow consumers in addition to the previously declared
portal, calculation, filing, verification, and deadline links.

The construct references every declared workflow surface so application code has
one registry-owned route to the Modelo 200 definition. The export link remains
open because no complete export layout has been transcribed into the registry.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_200_registry.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_200_registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_200_registry.py`
