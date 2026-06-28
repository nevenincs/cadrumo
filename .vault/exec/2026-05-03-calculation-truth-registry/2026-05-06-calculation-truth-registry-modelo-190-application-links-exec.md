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



# `calculation-truth-registry` `modelo-190` `application-links`

Closed the Modelo 190 workflow application-link surface for the current
registry foundation and added behavior coverage for the Modelo 111 annual
summary relation.

- Modified: `registry/aeat/modelos/190.toml`
- Created: `src/aeat/domain/calculations/registry/test_modelo_190_registry.py`

## Description

Modelo 190 now declares registry-snapshot gates for review, approval,
reconciliation, and workflow consumers in addition to the existing calculation,
filing, verification, extractor, and portal links.

The Modelo 190 construct references every declared workflow surface so
application code has one registry-owned route to the annual summary definition.
The focused behavior tests validate the registry snapshot, prove every
declared Modelo 111 source output resolves against the Modelo 111 registry, and
exercise actual aggregation through the relation resolver and calculation
runtime.

Export layout completion and live filed-data capture remain open plan rows for
the Modelo 190 wave.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_190_registry.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_190_registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_190_registry.py`
- `uv run python -c "from pathlib import Path; from aeat.domain.calculations.registry import RegistryValidator, build_snapshot, load_registry_tree; root=Path('registry/aeat'); modelos,catalogues=load_registry_tree(root); modelo=next(item for item in modelos if item.id=='190'); RegistryValidator(catalogues, source_root=Path.cwd()).validate_modelo(modelo); build_snapshot(modelo, catalogues, source_root=Path.cwd(), filing_year=2025, period='0A'); print('modelo 190 registry validation passed')"`
