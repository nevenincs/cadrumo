---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:7bc0f52b12631376b1c209a7f99ca849adf2014acfa7daa015760d714181984b'
step_id: 'S03'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Implement strict one-fact-per-file TOML parsing

## Scope

- `src/cadrumo/domain/calculations/registry/facts/loader.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/facts/loader.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_loader.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P01-S03.md`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_loader.py -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/facts/loader.py src/cadrumo/domain/calculations/registry/facts/tests/test_loader.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/facts/loader.py src/cadrumo/domain/calculations/registry/facts/tests/test_loader.py` -> `pass`
