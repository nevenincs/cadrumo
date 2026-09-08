---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:3434d8a3596f816b8629ab863441209b6331ed6adcafa4d22413157e0aa27791'
step_id: 'S181'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
