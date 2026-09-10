---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b62366cedf07da85a14e68a6672c9f72df202f2e808000a0ac7fc26a247e87ab'
step_id: 'S05'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Prove conflicting identity, malformed data, orphaned targets, and unclassified files produce distinct diagnostics

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`
- `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py` -> `pass`
