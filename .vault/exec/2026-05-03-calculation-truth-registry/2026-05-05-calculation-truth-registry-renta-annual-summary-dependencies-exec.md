---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `Renta` `annual summary dependencies`

Added Modelo 190 and Modelo 193 as registry-owned annual factual evidence
dependencies for Modelo 100 ejercicio 2025.

- Modified: `registry/aeat/modelos/100.toml`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Modelo 100 now declares annual-summary bindings, relations, dependency
classifications, and construct membership for Modelo 190 annual withholding
evidence and Modelo 193 annual movable-capital withholding evidence. These
relations are factual evidence dependencies. They do not replace Modelo 100
casilla formulas and do not create Python-owned calculation authority.

The relation tests now resolve the annual Modelo 190 and Modelo 193 observations
through the same registry observation backend used for quarterly and annual
dependency sources.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_modelo_100_dependency_relations_resolve_against_registered_modelos src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_modelo_100_renta_section_constructs_classify_registered_relation_sources src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_modelo_100_dependency_classifications_cover_registered_relation_sources src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py::test_modelo_100_payment_calculation_resolves_cross_model_periodic_and_annual_observations -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q`
- `uv run python -c "from pathlib import Path; from aeat.domain.calculations.registry import RegistryValidator, load_registry_tree; modelos,catalogues=load_registry_tree(Path('registry/aeat')); RegistryValidator(catalogues, source_root=Path('.')).validate_registry(modelos); print(f'verified {len(modelos)} modelos')"`
- `uv run ruff check registry/aeat/modelos/100.toml src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`
