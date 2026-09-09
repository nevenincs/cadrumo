---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1e4ce91e018741fc4b0a12fd62612abe54052185b47a6cf20a48ee78558fa667'
step_id: 'S09'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Record exact global legal-parameter adapter callers and closure conditions

## Scope

- `src/cadrumo/domain/calculations/registry/loader.py`

## Changes

- `M` `dev/registry/analysis/facts_external_constants_retirement.toml`
- `M` `dev/registry/tests/test_facts_external_constants_retirement.py`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P03-S09.md`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `verify:` `.venv/Scripts/python.exe -m pytest -n 0 dev/registry/tests/test_facts_external_constants_retirement.py -q` -> `pass`
