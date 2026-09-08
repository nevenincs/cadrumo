---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f066b7678ce6b001386b81b385f21c9a898f94aa840086e1e5bcb9a1c90304a9'
step_id: 'S160'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Replace the compatibility lifecycle gate's hand-maintained expected durable-format population with synthetic detector-teeth authorities, preserving live derived enrollment checks without a second product-identity census.

## Scope

- `compatibility lifecycle gate tests`
- `reachability burndown cadence`
- `live unused-symbol detector`

## Changes

- `M` `src/cadrumo/core/tests/test_compatibility_lifecycle_gate.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run ruff check src/cadrumo/core/tests/test_compatibility_lifecycle_gate.py` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/core/tests/test_compatibility_lifecycle_gate.py` -> `pass` (14 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (367 exact symbols and 19 orphaned test modules, unchanged)
