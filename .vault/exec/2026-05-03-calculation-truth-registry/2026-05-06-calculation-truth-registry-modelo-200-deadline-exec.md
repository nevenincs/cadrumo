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



# `calculation-truth-registry` `modelo-200` `deadline`

Added the Modelo 200 annual filing schedule and 2024 filing deadline to the
central registry with BOE-backed legal and source evidence.

- Modified: `registry/aeat/modelos/200.toml`
- Modified: `registry/aeat/legal/is.toml`
- Created: `corpus/normatives/html/ley-27-2014-art-124.html`
- Created: `corpus/normatives/html/orden-hac-657-2025.html`
- Created: `src/aeat/domain/calculations/registry/test_modelo_200_registry.py`

## Description

The registry now cites Ley 27/2014 article 124 for the Modelo 200 filing
deadline and the BOE 2025 Modelo 200 order as the official source for the
calendar-year 2024 filing window. The Modelo 200 construct includes the annual
schedule, deadline window, and deadline application link so deadline behaviour
is registry-owned rather than inferred in Python.

The committed BOE source corpus is an excerpt that contains the exact deadline,
domiciliation, entry-into-force, and Modelo 200 source text needed for this
registry slice.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_200_registry.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_200_registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_200_registry.py`
- `uv run python -c "from pathlib import Path; from aeat.domain.calculations.registry import RegistryValidator, load_registry_tree; root=Path('registry/aeat'); modelos,catalogues=load_registry_tree(root); modelo=next(item for item in modelos if item.id=='200'); RegistryValidator(catalogues, source_root=Path.cwd()).validate_modelo(modelo); print('modelo 200 registry validation passed')"`
