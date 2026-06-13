---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P14.S50'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P14.S50 - Locale Traversal Helper Consolidation

## Scope

- `src/aeat/locales/_ast_scanner.py`
- `src/aeat/locales/manager.py`

## Work

Extracted repeated locale traversal mechanics behind module-local helpers:

- `_iter_parseable_python_modules()` now owns AST scanner source-file skip,
  read, parse, and debug-log behavior for both concrete-key discovery and
  dynamic namespace discovery.
- `_iter_yaml_key_matches()` now owns YAML key-stack traversal for replace,
  append, and remove leaf operations.

The slice does not change locale data, regex discovery, dynamic namespace
rules, YAML write strategy, or CLI behavior.

## Verification

- `rg -n "rglob|scan_source_tree|scan_namespace_markers|_iter_parseable_python_modules|_iter_yaml_key_matches|_replace_existing_yaml_leaf|_append_yaml_leaf|_remove_existing_yaml_leaf|isinstance\(.+dict|\.items\(\)" src/aeat/locales`
- `uv run --no-sync vaultspec-rag search "translation locale nested dictionary traversal YAML key path" --type code --port 8766 --max-results 12`
- `uv run --no-sync vaultspec-rag search "repo health locale traversal consolidation plan" --type vault --port 8766 --max-results 8`
- `uv run --no-sync ruff check src/aeat/locales/_ast_scanner.py src/aeat/locales/manager.py src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py src/aeat/locales/test_cli.py`
- `uv run --no-sync pytest src/aeat/locales`
- `just audit-duplication`

## Outcome

Ruff passed for the locale surface and the full locale suite passed with 29
tests. The duplication audit no longer reports clone groups for
`src/aeat/locales/_ast_scanner.py` or `src/aeat/locales/manager.py`.

The audit still reports 19 clone groups outside this S50 slice. The shared
worktree has shifted enough that a new `_modelo_m036_cli.py` clone appears in
the residual list; it is recorded as follow-up evidence rather than folded
into this locale-only commit.
