---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S195'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run Ruff against every feature-owned Python file

## Scope

- `src/cadrumo/`

## Description

Run Ruff against every feature-owned Python file, then run it repository-wide and attribute
the difference.

## Outcome

SATISFIED for the feature-owned surface. Repository-wide is red, entirely outside it.

Feature-owned scope: the CLI entrypoint package, the MCP entrypoint package, the locale package,
and the audit tooling package.
Commands: `uv run --no-sync ruff check src/cadrumo/entrypoints/cli src/cadrumo/locales
src/cadrumo/entrypoints/mcp` and the matching `ruff format --check`, plus both verbs over
`dev/audit`.
Results: `All checks passed!` and `534 files already formatted` for the source scope; `All checks
passed!` and `11 files already formatted` for the audit tooling. Exit code 0 on all four.

Repository-wide, at HEAD `1844ef2ea0`: `uv run --no-sync ruff check src/cadrumo dev` reports
`Found 5 errors`, and `ruff format --check` reports `5 files would be reformatted, 4496 files
already formatted`. Both exit 1.

Attribution of the repository-wide reds, by working-tree state at the time of the run. Untracked
peer work in flight: a release pointer-guard test and a Clave credential-resolution test. Modified
peer work in flight: a distribution-claims test and a publish-release workflow test. Committed at
HEAD and therefore genuine standing debt: a TUI form-screen module with an unsorted export list,
an IVA domain package with an unsorted import block, and two modules that fail format check, the
wizard commands module and the core config module.

## Notes

The corpus size is quoted for both scopes so the green feature-owned result cannot be read
as a zero-file run: 534 source files and 11 tooling files were actually formatted-checked.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
