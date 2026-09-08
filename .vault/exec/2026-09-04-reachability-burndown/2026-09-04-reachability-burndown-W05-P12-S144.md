---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:557482bf8ba818093f8c1902e2ebcee09f8771c6e2571d90b885c218573ea580'
step_id: 'S144'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the shipped manuals review-required future-policy setting and no-op verification parameter, leaving reviewer completeness enforced only by the live strict manual schema and removing tests that configure an inert development switch

## Scope

- `manual verification API and tests`
- `core settings surface`

## Changes

- `M` `src/cadrumo/core/config.py`
- `M` `src/cadrumo/domain/manuals/verify.py`
- `M` `src/cadrumo/domain/manuals/tests/test_verify.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/domain/manuals/tests/test_verify.py` -> `pass (7 passed)`
- `verify:` `uv run ruff check src/cadrumo/core/config.py src/cadrumo/domain/manuals/verify.py src/cadrumo/domain/manuals/tests/test_verify.py` -> `pass`
- `verify:` exact settings, verifier-parameter, and call-site scan -> `pass (zero matches)`
