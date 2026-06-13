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



# `calculation-truth-registry` `construct classification reciprocity`

Hardened construct/dependency closure so dependency classifications and target
constructs cannot drift independently.

- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- Modified: `registry/aeat/modelos/180.toml`
- Modified: `registry/aeat/modelos/190.toml`
- Modified: `registry/aeat/modelos/193.toml`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The registry validator now requires every dependency classification that names a
target construct to be reciprocally listed by that construct. This closes a
one-way metadata drift where a dependency could claim a construct target without
the construct carrying that dependency in its reviewed member ledger.

The annual-summary constructs for Modelos 180, 190, and 193 now list their
dependency classifications. The Modelo 100 test mutates a real construct to
prove the validator fails when the reciprocal membership is removed.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- `uv run python -c "from pathlib import Path; from aeat.domain.calculations.registry import RegistryValidator, load_registry_tree; modelos,catalogues=load_registry_tree(Path('registry/aeat')); RegistryValidator(catalogues, source_root=Path('.')).validate_registry(modelos); print(f'verified {len(modelos)} modelos')"`
