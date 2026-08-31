---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:a4c0f18268962e0afe8a509b1dfd4cdfc7080b2d21b35202df1a3afc124ea731'
step_id: 'S126'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in _profile_custody_carry.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py` -> `pass`
- `verify:` `uv run --no-sync pytest -o addopts='' -q src/cadrumo/application/user_profile/tests/test_custody_roundtrip.py src/cadrumo/application/user_profile/tests/test_custody_restore_atomicity.py` -> `pass`
