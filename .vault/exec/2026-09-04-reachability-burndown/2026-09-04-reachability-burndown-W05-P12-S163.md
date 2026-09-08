---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:ee3cc66a8a49f66200389f0684f8ceae819c5a196fa66429b8d95c5a0c2205ef'
step_id: 'S163'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete three empty allowlist mechanisms and their stale-entry branches from the AEAT settings-read and resource-root structural guards so their live derived populations are unconditional zero-target assertions.

## Scope

- `settings single-surface guard`
- `resources single-surface guard`
- `focused structural tests`
- `live reachability detector`

## Changes

- `M` `src/cadrumo/core/tests/test_settings_single_surface_invariant.py`
- `M` `src/cadrumo/core/resources/tests/test_single_surface_invariant.py`
- `verify:` `rg -n "_ALLOWLIST|PENDING_RETIREMENT_ALLOWLIST|SANCTIONED_CHECKOUT_ROOT_OWNERS" <S163 paths>` -> `pass` (zero matches)
- `verify:` `uv run ruff check <S163 paths>` -> `pass`
- `verify:` `uv run pytest -q <S163 paths>` -> `pass` (4 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (367 exact symbols and 18 orphaned test modules, unchanged)
