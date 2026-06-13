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



# `calculation-truth-registry` `formula runtime external value closure`

Hardened the registry formula runtime so supplied binding and relation values
must belong to the selected revision.

- Modified: `src/aeat/domain/calculations/registry/_formula_runtime.py`
- Modified: `src/aeat/domain/calculations/registry/test_formula_runtime.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The formula runtime already rejected unknown casilla inputs. It now applies the
same fail-fast behaviour to external binding values and relation values before
formula evaluation begins. This prevents misspelled or shadowed dependency
inputs from being silently accepted by a filing-grade calculation path.

The tests exercise real committed Modelo 130 and Modelo 180 snapshots and
verify hard failures for unknown binding and relation identifiers.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_formula_runtime.py -q`
- `uv run python -c "from pathlib import Path; from aeat.domain.calculations.registry import RegistryValidator, load_registry_tree; modelos,catalogues=load_registry_tree(Path('registry/aeat')); RegistryValidator(catalogues, source_root=Path('.')).validate_registry(modelos); print(f'verified {len(modelos)} modelos')"`
- `uv run ruff check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
- `uv run ty check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
