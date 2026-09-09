---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:15dcc7cb3689b43a87fe324fad8539706b88164e5a0b6fec733ab9538e9a2d2f'
step_id: 'S182'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Wire the accepted Cl@ve Permanente remote-state action policy into the live credential-form driver immediately before username fill, password fill, and authentication click, and prove a policy refusal prevents the corresponding browser mutation rather than leaving the guard exercised only by its own tests.

## Scope

- `Cl@ve Permanente provider login form`
- `policy tests and live reachability measurement`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/auth/clave_permanente.py`
- `M` `src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_permanente.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_permanente.py` -> `pass` (19 passed)
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/outbound/aeat/auth/tests/test_auth_provider_real_lifecycle.py -k "clave_permanente"` -> `pass` (4 passed)
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/outbound/aeat/auth/clave_permanente.py src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_permanente.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail` (350 exact symbols; 18 orphan test modules)
