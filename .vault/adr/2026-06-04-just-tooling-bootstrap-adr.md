---
tags:
  - '#adr'
  - '#just-tooling-bootstrap'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-just-tooling-bootstrap-research]]'
---

# `just-tooling-bootstrap` adr: `quality audit command surface` | (**status:** `accepted`)

## Problem Statement

The project has accumulated modern Python quality tooling in `pyproject.toml`, but
the `justfile` does not expose authoritative recipes for dead-code discovery,
dependency drift, duplication, deprecation review, or complexity/refactor discovery.
The result is a split-brain bootstrap: contributors can see configured tools, but
there is no definitive command surface for running them consistently.

## Considerations

The existing stack already aligns with the modern Astral-centered Python workflow:
`uv` owns environment synchronisation, Ruff owns lint and format, `ty` is the fast
primary type checker, and Pyright provides a mature cross-check on selected strict
surfaces. Additional audit tools should be wired through the same `uv run` and
`just` pattern so that contributors do not need to reverse-engineer command flags.

The research found that `radon`, `complexipy`, `ty`, `pyright`, and `ruff` are
spawnable in the current environment. `vulture` and `deptry` are configured but not
installed in the current synchronized environment. `semgrep` is not on PATH, but
`uvx --from semgrep semgrep` resolves a working executable, so the security audit
can remain runnable without requiring a workstation-wide install.

## Constraints

This worktree is shared and dirty, so implementation must avoid any destructive Git
operation and must not rely on stash, reset, checkout, restore, or clean. The command
surface must also separate hard quality gates from advisory discovery dashboards:
current full-tree type checking and audit discovery are red in this shared state, so
they cannot honestly be promoted into the same lane as deterministic required gates.

The implementation relies on actively maintained tools. `ty` is still a fast-moving
checker, so Pyright remains as a cross-checker. Static dead-code and duplication
tools necessarily produce false positives in dynamic Python and should be exposed as
audit surfaces before being promoted to ratcheted hard gates.

## Implementation

The `justfile` will expose a layered quality surface:

- a hard `quality` recipe for existing deterministic gates;
- advisory audit recipes for dependency drift, dead code, duplication,
  deprecation/type opportunities, complexity, security availability, and structural
  health;
- a `quality-audit` aggregate recipe that composes the advisory dashboards.

`pyproject.toml` will declare missing audit dependencies that already have project
configuration. Vulture will back dead-code discovery, deptry will back dependency
declaration drift, and radon plus complexipy will back cyclomatic,
maintainability, and cognitive complexity. Copy-paste duplication will use pinned
`jscpd` through the workstation Node toolchain, keeping Node packages out of the
Python dependency lock while still exposing an authoritative `just` endpoint.

Semgrep will remain a security-audit recipe. It will prefer an installed
workstation executable and fall back to `uvx --from semgrep semgrep` for fresh
worktrees.

## Rationale

The research showed that the project already has high-value complexity and type
signals, but contributors currently lack memorable, authoritative `just` endpoints.
Separating `quality` from `quality-audit` keeps daily development honest: fast green
gates remain hard, while red discovery dashboards can still guide refactors without
blocking unrelated work.

## Consequences

The project gains a single command surface for modern quality discovery and easier
agent delegation. Dependency and dead-code tooling become installable through the
normal `uv sync` bootstrap. Complexity and duplication reports become repeatable
instead of ad hoc.

The immediate drawback is that several advisory commands may be red on first use.
That is intentional: they reveal existing debt and should be ratcheted only after the
team agrees on baselines. Semgrep may still require network access on first `uvx`
execution when no workstation executable is installed.

## Codification candidates

- **Rule slug:** `just-audit-gates-are-explicit`.
  **Rule:** Project quality tooling that is configured or declared must have either a
  working `just` recipe or an explicit ADR-backed deferral explaining why it is not
  runnable.
