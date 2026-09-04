---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:075d66189f6e73a372a88d7d4fc43acf9208f6eea77aa7a7ce6f2f694d776d7a'
step_id: 'S15'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Resolve the Ledger controller and route factory clone while preserving dependency injection and refresh ownership

## Scope

- `src/cadrumo/entrypoints/tui/ledger`

## Changes

- `A` `src/cadrumo/entrypoints/tui/ledger/workspace_injection.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/controller.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/routes.py`
- `M` three TUI test modules and the devtools workbench fixture, 28 construction sites
- `M` `dev/audit/duplication_dispositions.toml`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" src/cadrumo/entrypoints/tui/ledger src/cadrumo/entrypoints/tui/devtools` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/tui/ledger/` -> `pass`

## Notes

Clone count fell from 11 to 10. The eleven injected dependencies are now one frozen
`LedgerWorkspaceInjection`, so the parameter list is declared once rather than in both the
route factory and the controller constructor.

Dependency injection and refresh ownership are preserved, which this Step required. The
factory keeps its public signature, so `launcher.py` and every external caller are
unchanged; it builds the injection once and hands it to the controller. The controller
still exposes each dependency as the attribute its screens read, assigned from the
injection, so no downstream reader changed.

The guard consolidated in the preceding Step moved into the injection's `__post_init__`,
which is where it belongs: there is now one construction path, so a check cannot apply on
one and not the other. The duplicated prepared-import uniqueness check moved with it.

28 construction sites were converted across three test modules and the devtools workbench
fixture. 232 tests pass.

## Notes on the conversion

The first conversion attempt used a line-oriented regex and produced 16 failures and 12
type errors. It assumed one argument per line, which is how most sites are written, and
mangled the compact ones where the whole call sits on a single line. The three affected
files were restored from copies taken beforehand and reconverted through an AST rewrite,
which reads the call rather than its formatting.

That is the same lesson this campaign has now hit twice in a different guise: a regex over
code shape reports success on the shapes it anticipated. The AST conversion found 28 sites
where the regex had found 27, and the extra one was the single-line call in
`test_ledger_workspace.py` that the earlier pass had reported as zero.
