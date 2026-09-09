---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b27476bf520a14027417c9843cfd93e70f80c63157ec8746e5550a7538dd34fb'
step_id: 'S297'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the dev-wide governance-corpus isolation census and its eleven path-keyed exemptions; retain the strict no-allowlist src isolation gate and shared detector.

## Scope

- `development governance isolation test`
- `production isolation gate`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `dev/tests/test_dev_governance_isolation.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q dev/tests/test_governance_corpus_isolation.py` -> `pass`
- `verify:` `rg -n <deleted dev-isolation identifiers> src dev justfile pyproject.toml` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

## Notes

The retained strict production-boundary suite passed all 37 tests. Exact reachability remained at 243 unused symbols, 31 unreachable modules, and zero orphan tests; deleting the dev-only census changes no shipped edge.
