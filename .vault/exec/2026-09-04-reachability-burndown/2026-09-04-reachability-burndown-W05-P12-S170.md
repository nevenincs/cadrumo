---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:8117a00e2f8ffd54dfb3a60e5e14a72fdb797c491f878cbc293c7402d3a8b09e'
step_id: 'S170'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the exported apoderado-flow locale-key aggregate because its six constituent canonical locale constants are already independently scanner-visible, preserving the derived module key set and the live apoderado behavior without replacing the census.

## Scope

- `src/cadrumo/application/auth/apoderado_flow.py`
- `reachability burndown reference`
- `focused apoderado and locale gates`
- `full locale audit`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/application/auth/apoderado_flow.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "APODERADO_FLOW_LOCALE_KEYS" src/cadrumo dev -g "*.py"` -> `pass` (zero matches)
- `verify:` module-local locale scan -> `pass` (all six constituent keys remain discovered)
- `verify:` `uv run ruff check src/cadrumo/application/auth/apoderado_flow.py` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/application/auth/tests/test_apoderado.py` -> `pass` (33 passed)
- `verify:` `uv run python -m dev.locales audit` -> `fail` (unchanged one missing and one extra key in each supported locale)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (362 exact symbols, down from 363, and 18 orphaned test modules unchanged)

## Notes

The remaining locale audit drift is `tui.declarations.lifecycle.verification_refused` missing and `aggregation.source_mesh.errors.ambiguous_source_disposition` extra in each supported locale; neither relates to the deleted aggregate.
