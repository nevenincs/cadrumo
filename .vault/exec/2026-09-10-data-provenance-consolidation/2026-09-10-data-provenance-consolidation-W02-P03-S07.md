---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:8bda21cae6b36ef6cc97c08d199602378e9c6193ba066bdc0c4327fd981bd678'
step_id: 'S07'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Bind catalogue verification to the artifact identity join while retaining registry semantic validation

## Scope

- `src/cadrumo/domain/calculations/registry/corpus_catalogue.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/corpus_catalogue.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`
- `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py -k conflicting_identity` -> `pass`
