---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:5bc2bdc7cf94066b0160d70983af0e1f19ca2240b099592420c020eec4c7a034'
step_id: 'S02'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Implement adapters for record-design, manual, e-invoice, registry, and declared disposition records

## Scope

- `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/artifact_catalogue.py; uv run ruff format --check src/cadrumo/domain/calculations/registry/artifact_catalogue.py; uv run ty check src/cadrumo/domain/calculations/registry/artifact_catalogue.py` -> pass
