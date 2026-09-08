---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:ecae822884f0030a8408d7b2ec7b010d9ed98f7366d3da5708f4dadfe5ba7b6e'
step_id: 'S148'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the ignored headers and retry-default compatibility parameters from maintenance and WAF site-health parsers, replacing uniform-signature loop dispatch with explicit typed calls so each production parser accepts only evidence it evaluates

## Scope

- `AEAT site-health parser API`
- `orchestrator dispatch`
- `focused parser tests`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/browser/_site_health_parsers.py`
- `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_site_health.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/adapters/outbound/aeat/browser/tests/test_site_health.py` -> `pass (29 passed)`
- `verify:` focused `uv run ruff check` over parser and tests -> `pass`
- `verify:` exact ignored-parameter rationale and deletion scan -> `pass (zero matches)`
