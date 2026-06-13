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



# `calculation-truth-registry` `modelo-193` `application-links`

Closed the Modelo 193 workflow application-link surface for the current
registry foundation and added behavior coverage for the Modelo 123 annual
summary relation.

- Modified: `registry/aeat/modelos/193.toml`
- Created: `src/aeat/domain/calculations/registry/test_modelo_193_registry.py`

## Description

Modelo 193 now declares registry-snapshot gates for review, approval,
reconciliation, and workflow consumers in addition to the existing calculation,
filing, verification, extractor, and portal links.

The focused behavior tests validate the registry snapshot, prove every
declared Modelo 123 source output resolves against the Modelo 123 registry, and
exercise actual aggregation through the relation resolver and calculation
runtime.

Export layout completion and live filed-data capture remain open plan rows for
the Modelo 193 wave.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_193_registry.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_193_registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_193_registry.py`
- `uv run python -c "from pathlib import Path; from aeat.domain.calculations.registry import RegistryValidator, build_snapshot, load_registry_tree; root=Path('registry/aeat'); modelos,catalogues=load_registry_tree(root); modelo=next(item for item in modelos if item.id=='193'); RegistryValidator(catalogues, source_root=Path.cwd()).validate_modelo(modelo); build_snapshot(modelo, catalogues, source_root=Path.cwd(), filing_year=2025, period='0A'); print('modelo 193 registry validation passed')"`
