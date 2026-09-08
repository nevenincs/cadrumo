---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:3fb9026b89542da094c05128572740aaf6cd2429e7c104f8ec5e825809a6331d'
step_id: 'S08'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Re-confirm prorrata seed source coordinates through revision_carry_outcome

## Scope

- `src/cadrumo/application/prorrata_register/seed.py`

## Changes

- `M` `src/cadrumo/application/prorrata_register/seed.py`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/prorrata_register/tests/test_seed.py` -> `pass`
