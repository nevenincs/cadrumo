---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:14f2c0053997dfd51841443bebb87cc863e108d6d751c82cbac92618eff3921a'
step_id: 'S156'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the unreachable exported profile-custody warmup and profile-record size constants, preserve the live custody safety limits, and prove the focused suite plus exact reachability recount.

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/{kdf_supervision.py`
- `capsule.py}`
- `focused custody tests`
- `live unused-symbol detector`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/capsule.py`
- `verify:` `uv run ruff check src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py src/cadrumo/adapters/persistence/storage/custody/capsule.py` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/adapters/persistence/storage/custody/tests -x` -> `pass` (241 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (371 exact symbols, down from 373; 20 orphaned test modules unchanged)
