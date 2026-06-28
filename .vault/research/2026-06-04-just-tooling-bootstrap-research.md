---
tags:
  - '#research'
  - '#just-tooling-bootstrap'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-15-linkage-tooling-prior-art-research]]'
  - '[[2026-04-30-aeat-restructure-research]]'
---

# `just-tooling-bootstrap` research: `just` quality tooling bootstrap

This research inspected the current `justfile`, Python tooling declarations, project
quality rules, and read-only empirical command runs to identify missing development
bootstrap endpoints for duplication, dead code, dependency drift, type control, and
complexity/refactor discovery.

## Findings

The current `justfile` exposes bootstrap, install/sync, lint, format, typecheck,
pytest lanes, import-linter, docs, hooks, database migration, Playwright doctor,
and release helper recipes. It does not expose recipes for dead-code discovery,
dependency drift, copy-paste duplication, security/static-pattern scans, or
complexity dashboards.

`pyproject.toml` already contains useful quality-tool configuration and dependency
intent. `ty`, `pyright`, `semgrep`, `radon`, and `complexipy` are declared in the
dev dependency group. `vulture` and `deptry` have configuration sections but are
not declared as dev dependencies and were not spawnable through
`uv run --no-sync`.

Current environment checks showed `radon`, `complexipy`, `ty`, `pyright`, and
`ruff` are spawnable. `vulture` and `deptry` are not spawnable through `uv run
--no-sync` in this worktree state because the shared virtual environment has not
yet been synchronized with the new declarations. `semgrep` is not on PATH, but
`uvx --from semgrep semgrep --version` resolved successfully, so the security
recipe can use `uvx` as a deterministic fallback.

The current `typecheck` recipe runs `ty check src` and Pyright over
`src/aeat/domain` plus `src/aeat/application`. In the shared worktree, `ty check
src --output-format concise` reported 1015 diagnostics, and the narrowed Pyright
lane reported 797 errors and 485 warnings. Some findings are likely from
concurrent in-flight changes, but the bootstrap still needs ratcheted,
non-ambiguous type lanes so agents can distinguish baseline debt from
surface-specific regressions.

Pyright configuration is already partially ratcheted: standard mode globally,
strict rule overrides for `domain` and `application`, deprecation warnings,
unused-function warnings, private-usage warnings, and missing-parameter-type /
missing-type-argument errors in selected execution environments. This is a good
base but lacks explicit recipe lanes for full audit, ratchet-only reports, and
surface-scoped checks.

Complexity tooling is present but not surfaced. A read-only `radon cc` run with
C-or-worse threshold produced 284 C-or-worse blocks. The hottest surfaces included
`src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/ledger/_actions.py`,
`src/aeat/domain/calculations/registry/_formula_runtime.py`,
`src/aeat/domain/calculations/registry/_bindings.py`, and
`src/aeat/diagnostics/_identity_placement.py`. A `complexipy` cognitive-complexity
sample with threshold 20 found high cognitive load in similar areas plus wizard
command assembly and Google sync helpers.

The `src/aeat/diagnostics/_identity_placement.py` references above are historical
diagnostic-output evidence from the bootstrap run, not approval for a production
`aeat.diagnostics` package. The later repo-health review rejected and removed
that source package because diagnostics is not an approved hexagonal module.

`radon mi` identifies several file-level maintainability hotspots with near-zero
or low scores, including `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`,
`src/aeat/adapters/outbound/aeat/sede/_declarations.py`,
`src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`,
`src/aeat/diagnostics/_identity_placement.py`,
`src/aeat/domain/calculations/registry/_bindings.py`,
`src/aeat/domain/calculations/registry/_record_design.py`,
`src/aeat/domain/calculations/registry/_schema.py`,
`src/aeat/domain/calculations/registry/_workbook_parity.py`,
`src/aeat/entrypoints/cli/_ledger.py`, `src/aeat/entrypoints/cli/_modelo.py`,
and `src/aeat/entrypoints/cli/_config/__init__.py`.

The duplication/tooling gap should be filled separately from Ruff. Ruff already
has branch/statement/McCabe-style rules available, but copy-paste clone detection
is a different problem. Candidate endpoints should either add a dedicated
copy-paste detector such as `jscpd` through a Node-backed recipe, or use
Pylint's similarities checker in a highly constrained report-only recipe.

Recommended `just` taxonomy:

- `audit-deps`: run dependency declaration drift checks over production source,
  backed by `deptry src/aeat --known-first-party aeat`.
- `audit-dead-code`: run `vulture` against the configured production paths.
- `audit-deprecation`: run Pyright deprecation/private/unused diagnostics in a
  stable report lane, distinct from hard type errors.
- `audit-complexity`: run `radon cc`, `radon mi`, and `complexipy` with thresholds
  that fail only above agreed limits.
- `audit-duplication`: run a dedicated clone detector in report-only mode.
- `audit-security`: run Semgrep from PATH when available, with a `uvx --from
  semgrep semgrep` fallback for fresh worktrees.
- `audit-structure`: compose import-linter, shim verification, relative-import
  checks, dead-code, dependency drift, and duplication reports.
- `quality`: keep the existing fast green gate: lint, typecheck, tests, import
  contracts, docs-check if desired.
- `quality-audit`: slower advisory gate for refactor planning and technical-debt
  inventory, allowed to be red while producing stable output.

The project should separate hard gates from discovery dashboards. Hard gates must
be green and deterministic before they are placed in `quality`. Discovery
commands should be available from `just` even while red, because they are used to
prioritise refactors rather than block unrelated feature work.
