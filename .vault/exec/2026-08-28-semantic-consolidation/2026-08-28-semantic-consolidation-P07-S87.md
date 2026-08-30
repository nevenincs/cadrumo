---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:3fd0e0ba61d90af4217547db550e80fdfa355b0eaa2a09ef4e1388e485f308a3'
step_id: 'S87'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the currency, manuals and fincas facades, one package per commit

## Scope

- `src/cadrumo/domain/`

## Changes

- `M` `src/cadrumo/domain/currency/__init__.py`
- `R` `src/cadrumo/domain/currency/_models.py -> models.py`
- `R` `src/cadrumo/domain/currency/_service.py -> service.py`
- `M` `src/cadrumo/domain/manuals/__init__.py`
- `M` `src/cadrumo/domain/fincas/__init__.py`
- `verify:` `pytest src/cadrumo/domain/{currency,manuals,fincas} -n 0 -m ""` -> `pass`
