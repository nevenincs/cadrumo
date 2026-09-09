---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:590fa6818b5ddaaf556fc716c430dc4d4e8a9b598ea37e3d58f6d261b8f657e2'
step_id: 'S08'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Record exact IVA recargo grounding and repository retirement conditions

## Scope

- `src/cadrumo/domain/iva`

## Changes

- `A` `dev/registry/analysis/facts_iva_retirement.toml`
- `A` `dev/registry/tests/test_facts_iva_retirement.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P03-S08.md`
- `verify:` `uv run pytest dev/registry/tests/test_facts_iva_retirement.py -q` -> `pass`
- `verify:` `uv run ruff check dev/registry/tests/test_facts_iva_retirement.py` -> `pass`
- `verify:` `uv run basedpyright dev/registry/tests/test_facts_iva_retirement.py` -> `pass`
