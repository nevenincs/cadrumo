---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `phase0b` `relation-dependency-roles`

Typed dependency roles for registry relations.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `registry/aeat/modelos/180.toml`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Registry relations now require a `dependency_role` field. This makes the
cross-dependency ledger executable at schema level instead of relying on
relation names or surrounding prose.

The existing Modelo 180 relations to Modelo 115 are explicitly classified as
`periodic_to_annual_summary`. Annual-summary relations cannot validate with a
different dependency role, so future annual summary modelos must make the same
classification directly in the registry definition.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/test_registry_schema.py registry/aeat/modelos/180.toml`
- `uv run ruff format --check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/test_registry_schema.py`
- `uv run ty check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/test_registry_schema.py`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
