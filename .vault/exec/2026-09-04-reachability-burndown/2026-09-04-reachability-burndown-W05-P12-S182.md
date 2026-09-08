---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:736e11ee0f4ecfb3040e8de9092278f480c3586bab14549b301b800e8ca1dfbe'
step_id: 'S182'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
