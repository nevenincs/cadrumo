---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:568496dc3bc5bcb8c1a31caf98f24c7916b6ee7bf29aed9421edf7dbb5ab51db'
step_id: 'S07'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Classify every statutory declaration and production consumer

## Scope

- `src/cadrumo/core/external_constants.py`

## Changes

- `A` `dev/registry/analysis/facts_external_constants_retirement.toml`
- `A` `dev/registry/tests/test_facts_external_constants_retirement.py`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P03-S07.md`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `verify:` `.venv/Scripts/python.exe -m pytest -n 0 dev/registry/tests/test_facts_external_constants_retirement.py -q` -> `pass`
