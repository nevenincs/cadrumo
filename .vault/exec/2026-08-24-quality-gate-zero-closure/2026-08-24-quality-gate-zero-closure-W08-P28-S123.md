---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:154136a05cc1b4d19f36f34839e2e08ccf6093925b4e228df6859c3eb3248ba4'
step_id: 'S123'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Replace the banned unittest.mock spy in dev/registry/newmodelo/tests/test_manager.py with observation of the real cache through the public loader's object identity, so the assertion fails when the production reset call is removed rather than merely recording that a call occurred (Terra xhigh fixes and refactors)

## Scope

- `dev/registry/newmodelo/tests/`

## Changes

- `M` `dev/registry/newmodelo/tests/test_manager.py`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "unit or (integration and not serial)" dev/registry/newmodelo/tests/test_manager.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/registry/newmodelo/tests/test_manager.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/registry/newmodelo/tests/test_manager.py` -> `pass`
