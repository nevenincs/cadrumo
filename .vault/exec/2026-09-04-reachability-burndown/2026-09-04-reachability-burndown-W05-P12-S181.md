---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a6d706b83b95a321c40bb2d375de4a937774949d547f12ea9fbb9eef9a48c8ee'
step_id: 'S181'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unreached CasillaId-keyed apply_label_regex facade, its LabelHit result type, identity-only tests, and stale package claims after proving the live declaracion parser owns page provenance and ambiguity classification; preserve the shared PDF regex and decimal primitives required by production callers.

## Scope

- `src/cadrumo/adapters/inbound/pdf/label_regex.py`
- `its focused tests`
- `and package documentation`

## Changes

- `M` `src/cadrumo/adapters/inbound/pdf/label_regex.py`
- `M` `src/cadrumo/adapters/inbound/pdf/tests/test_label_regex.py`
- `M` `src/cadrumo/adapters/inbound/pdf/__init__.py`
- `verify:` `rg -n "\\bapply_label_regex\\b|\\bLabelHit\\b" src/cadrumo dev -g "*.py"` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/inbound/pdf/tests/test_label_regex.py` -> `pass` (4 passed)
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/inbound/pdf/label_regex.py src/cadrumo/adapters/inbound/pdf/tests/test_label_regex.py src/cadrumo/adapters/inbound/pdf/__init__.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail` (351 exact symbols; 18 orphan test modules)

## Notes

The wider blank-box parser suite passed 19 cases and failed one peer-owned Modelo 390 case while constructing a filing-grade registry snapshot from a revision currently graded for applicability. The failure occurs before the extraction path runs and is unrelated to this Step.

## Notes

The wider blank-box parser suite passed 19 cases and failed one peer-owned Modelo 390 case while constructing a filing-grade registry snapshot from a revision currently graded for applicability. The failure occurs before the extraction path runs and is unrelated to this Step.
