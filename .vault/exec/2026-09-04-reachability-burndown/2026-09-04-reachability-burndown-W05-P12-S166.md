---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e188574c4ba0be73172b96232f55aceeb40519551785fc47bcc1a59092aa491d'
step_id: 'S166'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the censal transport locale-key census that existed only for development scanner visibility, extend the locale AST scanner to derive translation keys from an inline row table iterated directly by production code, and prove it collects only the loop column reaching the translation sink rather than dotted machine-code siblings.

## Scope

- `src/cadrumo/entrypoints/cli/config/_censo_transport.py`
- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_row_table_tr_argument_discovery.py`
- `reachability burndown reference`
- `focused locale and censal gates`
- `full locale audit`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/entrypoints/cli/config/_censo_transport.py`
- `M` `dev/locales/_ast_scanner.py`
- `M` `dev/locales/tests/test_row_table_tr_argument_discovery.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run ruff check dev/locales/_ast_scanner.py dev/locales/tests/test_row_table_tr_argument_discovery.py src/cadrumo/entrypoints/cli/config/_censo_transport.py` -> `pass`
- `verify:` `uv run pytest -q dev/locales/tests/test_row_table_tr_argument_discovery.py src/cadrumo/entrypoints/cli/config/tests/test_censo_pull_verb.py` -> `pass` (6 passed)
- `verify:` `uv run python -m dev.locales audit` -> `fail` (the three censal keys remain discovered; pre-existing drift remains one missing and two extra keys in each of ca, en, es, and hu)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (366 exact symbols, down from 367, and 18 orphaned test modules unchanged)

## Notes

The full locale audit remains red on `tui.declarations.lifecycle.verification_refused` missing and `aggregation.source_mesh.errors.ambiguous_source_disposition` plus `tui.aeat_sync.column.resolution` extra in every supported locale. None is introduced or hidden by this step; the deleted censal registry's three keys remain present in the derived codebase key set.
