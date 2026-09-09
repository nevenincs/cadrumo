---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:ce5b491dd70e7ac771f1222c6c82ae53c86ba19c3faddd18ce204a9650bb2996'
step_id: 'S20'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Register statutory scalars schedules and classifications

## Scope

- `src/cadrumo/core/external_constants.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/facts/statutory_constants.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_statutory_constants_provider.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `A` `src/cadrumo/_data/registry/aeat/legal/statutory-constant-sources.toml`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W02-P08-S20.md`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_statutory_constants_provider.py src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py -q` -> `pass`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_convenio_provider.py::test_convenio_provider_references_validate_through_full_authority -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/facts/statutory_constants.py src/cadrumo/domain/calculations/registry/facts/tests/test_statutory_constants_provider.py src/cadrumo/domain/calculations/registry/facts/providers.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/facts/statutory_constants.py src/cadrumo/domain/calculations/registry/facts/tests/test_statutory_constants_provider.py src/cadrumo/domain/calculations/registry/facts/providers.py` -> `pass`
