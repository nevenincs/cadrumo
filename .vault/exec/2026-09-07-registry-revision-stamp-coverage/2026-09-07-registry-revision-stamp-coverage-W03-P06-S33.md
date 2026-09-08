---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:cf565171f52ee62c4f86e4dc9e8020440cf3748e448bc9d86a4272cc255c4055'
step_id: 'S33'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Stamp registry-derived prorrata entries at seed and settlement creation boundaries while requiring operator-authored entries to declare an explicit empty source-coordinate tuple

## Scope

- `src/cadrumo/application/prorrata_register`
- `src/cadrumo/application/modelo/revision_persistence.py`
- `src/cadrumo/entrypoints/cli/_prorrata_register_cli.py`

## Changes

- `M` `src/cadrumo/application/prorrata_register/seed.py`
- `M` `src/cadrumo/application/prorrata_register/sector_lifecycle.py`
- `M` `src/cadrumo/application/modelo/revision_persistence.py`
- `M` `src/cadrumo/entrypoints/cli/_prorrata_register_cli.py`
