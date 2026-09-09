---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:9d77f891f10b0b1657530dc4ce3db218d7365f979a28b9897cac1cfbe7c04ede'
step_id: 'S42'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Record retained domain facades and excluded technical configuration readers

## Scope

- `src/cadrumo/domain and src/cadrumo/core/external_constants.py`

## Changes

- `M` `dev/registry/analysis/facts_external_constants_retirement.toml`
- `M` `dev/registry/tests/test_facts_external_constants_retirement.py`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P03-S42.md`
- `verify:` `.venv/Scripts/python.exe -m pytest -n 0 dev/registry/tests/test_facts_external_constants_retirement.py -q` -> `pass`
