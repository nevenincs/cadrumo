---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `phase0b` `cross-model-relation-closure`

Registry-level cross-model dependency validation.

- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/entrypoints/cli/registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_catalogue_verification.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`

## Description

The registry validator now validates the whole loaded modelo set through
`validate_registry`. The gate preserves per-modelo validation and adds
cross-model relation closure for typed dependencies. Relations must point to an
existing source modelo, match at least one source revision, declare source and
target periods, use a supported aggregation operation, reference source periods
supported by the selected source revision, and reference a real source output.

The registry verification CLI now uses the whole-registry validator, so the
read-only `registry verify` path exercises dependency closure instead of only
checking each modelo file independently.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_catalogue_verification.py -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_catalogue_verification.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_catalogue_verification.py src/aeat/entrypoints/cli/registry.py`
- `uv run ruff format --check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_catalogue_verification.py src/aeat/entrypoints/cli/registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_catalogue_verification.py src/aeat/entrypoints/cli/registry.py`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
