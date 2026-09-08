---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:5c6f21a823d1c560e0af7dc94ed13d5032b723a90c73d883a62221d689b1892d'
step_id: 'S171'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the descendant group and descendant door locale-key aggregates because their 57 constituent canonical locale constants are already independently scanner-visible, preserving both derived module key sets and all unit plus serial integration behavior without replacement censuses.

## Scope

- `src/cadrumo/application/wizard/descendant_group.py`
- `src/cadrumo/application/wizard/descendant_door.py`
- `reachability burndown reference`
- `focused descendant and locale gates`
- `full locale audit`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/application/wizard/descendant_group.py`
- `M` `src/cadrumo/application/wizard/descendant_door.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "DESCENDANT(_DOOR)?_LOCALE_KEYS" src/cadrumo dev -g "*.py"` -> `pass`
- `verify:` `scan_source_text descendant_group.py descendant_door.py` -> `pass` (derived sets unchanged at 55 and 2 keys)
- `verify:` `uv run ruff check src/cadrumo/application/wizard/descendant_group.py src/cadrumo/application/wizard/descendant_door.py` -> `pass`
- `verify:` `uv run pytest -q -n0 src/cadrumo/application/wizard/tests/test_descendant_group.py src/cadrumo/application/wizard/tests/test_descendant_door.py` -> `pass` (22 passed, 5 deselected)
- `verify:` `uv run pytest -q -n0 -m integration src/cadrumo/application/wizard/tests/test_descendant_group.py src/cadrumo/application/wizard/tests/test_descendant_door.py` -> `pass` (5 passed, 22 deselected)
- `verify:` `uv run python -m dev.locales audit` -> `fail`
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail`

## Notes

The initial parallel focused run passed 22 tests but reported five held serial tests; the explicit marker lanes account for all 27 tests. The locale audit retains the pre-existing drift in each of ca, en, es, and hu: missing `tui.declarations.lifecycle.verification_refused` and extra `aggregation.source_mesh.errors.ambiguous_source_disposition`. The live detector reports 360 exact unused symbols, down from 362, and the same 18 orphan test modules.
