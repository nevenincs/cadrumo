---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:67ad87515179a7b688186cd8698a2748ccb9167bf74fa35f514e256307d75509'
step_id: 'S292'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
