---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:3df53ff5ab42aba02bfbdb782713577bbecddfd5a52a1e54c8424b1f9236d81c'
step_id: 'S06'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Prove changed derivative inputs and divergent registry source identity fail closed

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`
- `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py` -> `pass`
