---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:5cfb26c5c501f52af67ecea2dcce854445fcc61ffe23958fc2a986d8f0a4b787'
step_id: 'S161'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the orphaned regenerable-format floor test whose sole live assertion duplicates the canonical compatibility lifecycle gate, preserving both live and synthetic detector proof in one owner.

## Scope

- `duplicate regenerable floor test`
- `canonical compatibility lifecycle gate`
- `live reachability detector`

## Changes

- `D` `src/cadrumo/core/tests/test_regenerable_persisted_format_floors.py`
- `verify:` `rg -n "misclassified_floor_keys\\(RELEASED_FORMAT_FLOORS, PERSISTED_FORMATS\\)" src/cadrumo --glob '*.py'` -> `pass` (one canonical live gate remains)
- `verify:` `uv run pytest -q src/cadrumo/core/tests/test_compatibility_lifecycle_gate.py` -> `pass` (14 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (367 exact symbols unchanged, 18 orphaned test modules down from 19)
