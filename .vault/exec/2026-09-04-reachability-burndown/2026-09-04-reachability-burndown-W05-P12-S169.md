---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:367effca89a36e399122f4b8d982d318a7bfe51be64a3ce91675535229d5facf'
step_id: 'S169'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the TUI search locale-key aggregate maintained only for scanner and test completeness, remove its duplicate test census, teach the locale scanner to derive literal mapping.get fallbacks that reach translation while rejecting routing fallbacks, and restore the existing anonymous helper-argument row-table detector alongside the direct-iterable form.

## Scope

- `src/cadrumo/entrypoints/tui/search.py`
- `src/cadrumo/entrypoints/tui/tests/test_search.py`
- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`
- `reachability burndown reference`
- `focused TUI and locale gates`
- `full locale audit`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/entrypoints/tui/search.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_search.py`
- `M` `dev/locales/_ast_scanner.py`
- `M` `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "_SEARCH_LOCALE_KEYS" src/cadrumo -g "*.py"` -> `pass` (zero matches)
- `verify:` `uv run ruff check dev/locales/_ast_scanner.py dev/locales/tests/test_dynamic_prefix_registry_coverage.py src/cadrumo/entrypoints/tui/search.py src/cadrumo/entrypoints/tui/tests/test_search.py` -> `pass`
- `verify:` focused fallback, anonymous-row-table, and TUI search pytest selection -> `pass` (21 passed)
- `verify:` whole-tree `scan_source_tree(Path("src/cadrumo"))` -> `pass` (4,433 keys, including search address and both mapping fallbacks)
- `verify:` `uv run python -m dev.locales audit` -> `fail` (improved to one pre-existing missing and one pre-existing extra key in each supported locale)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (363 exact symbols, down from 364, and 18 orphaned test modules unchanged)

## Notes

The first whole-tree scan after deleting the aggregate exposed two undiscovered literal `mapping.get` fallbacks, and the broad scanner suite exposed that S166's direct-inline-table precision had regressed the older helper-argument inline-table form. Both detector gaps were fixed with positive and negative controls. The locale audit consequently stopped falsely reporting `tui.aeat_sync.column.resolution` as extra; its remaining cross-locale drift is unrelated.
