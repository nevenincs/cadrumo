---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:2f76c7a8c902ad990212aef4076bed8bed20b9cb6653ee1e60e9c29e42795eab'
step_id: 'S338'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Retire the permanently red relative-self-import style gate and duplicate detector tests

## Scope

- `relative-import scanner`
- `aggregate and changed-path gates`
- `CI workflows`
- `test-fast recipe`
- `stale rationale`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `dev/quality/relative_imports.py`
- `D` `dev/quality/tests/test_relative_imports.py`
- `D` `src/cadrumo/tests/test_relative_imports_only.py`
- `M` `dev/quality/suite.py`
- `M` `dev/quality/changed_paths.py`
- `M` `justfile`
- `M` `.github/workflows/ci.yml`
- `M` `.github/workflows/ci-full.yml`
- `M` `pyproject.toml`
- `M` `src/cadrumo_harness/mcp/tests/test_stdio_lifetime.py`
- `M` `src/cadrumo/application/tests/test_storage_namespace_adoption.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_changed_paths.py dev/quality/tests/test_suite_gate_table.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/suite.py dev/quality/changed_paths.py src/cadrumo_harness/mcp/tests/test_stdio_lifetime.py src/cadrumo/application/tests/test_storage_namespace_adoption.py` -> `pass`
- `verify:` `just --list` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
