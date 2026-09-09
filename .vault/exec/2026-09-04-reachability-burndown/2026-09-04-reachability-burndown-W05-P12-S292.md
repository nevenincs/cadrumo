---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:6c5d87c70c0e58ae8550f16b8443e244aa37e21918a037839b1b3fa1cc9b1870'
step_id: 'S292'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only amendment-regime membership probe and its modelo roster assertion; retain boundary-driven amendment behavior tests over the live resolver.

## Scope

- `amendment-kind regime authority and focused tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/core/amendment_kind_regime.py`
- `M` `src/cadrumo/core/tests/test_amendment_kind_regime.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "modelo_has_codified_amendment_regime" src dev` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/amendment_kind_regime.py src/cadrumo/core/tests/test_amendment_kind_regime.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/tests/test_amendment_kind_regime.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
