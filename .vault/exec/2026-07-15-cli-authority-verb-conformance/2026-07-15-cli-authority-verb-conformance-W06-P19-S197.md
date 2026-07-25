---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S197'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the feature-surface-gate skill against only feature-owned paths

## Scope

- `.`

## Description

Run the feature-surface-gate discipline against only feature-owned paths, scoping lint and
tests to the surface this feature owns rather than the whole trunk.

## Outcome

SATISFIED for lint, FAILED for tests, with the difference attributed.

The skill's own procedure assumes a feature branch and a diff against the trunk. This campaign
lands directly on the trunk, so the touched surface was taken as the paths the Phase's Step scopes
name: the CLI entrypoint package, the MCP entrypoint package, the locale package, and the audit
tooling package.

Lint, path-scoped. `uv run --no-sync ruff check` and `ruff format --check` over those four scopes:
`All checks passed!` with `534 files already formatted` for the source scopes, and `All checks
passed!` with `11 files already formatted` for the audit tooling. Exit 0 throughout. The corpus
sizes are quoted so this cannot be read as a zero-file run.

Tests, path-scoped. Green for the locale package. Red for the CLI and MCP entrypoint packages and
for the audit tooling, with every failure traced under S196, S201 and S207 to causes outside this
feature: an untracked peer test module poisoning the schema registry, an untracked peer relocation
of two wizard schemas out of the discovery walk, an uncommitted peer edit to a sequence contract,
and undispositioned clones introduced by the TUI campaign.

Vault scope. Feature-scoped placeholder validation over the vault reports clean.

## Notes

The honest answer to the gate's own question, whether this feature's commits regressed the
surfaces they touched, is NO for lint and NOT ESTABLISHED for tests: the feature-owned test
surface is currently red, but every named cause is peer-owned and four of them are uncommitted, so
the surface cannot be measured cleanly until the working tree settles.

This record originally reserved one exception to that attribution, naming the CLI config package
initialiser's module-size breach as a genuine feature-owned regression. That exception is
WITHDRAWN. Numstat shows the file was inside its budget at 1254 lines until a peer commit added a
net 134 lines in one move, and that this campaign's three subsequent commits reduce it by three.
The correction is recorded in full under S200.

With that reattributed, NO feature-owned regression has been identified in any failing lane. Every
failure this Phase measured belongs to a concurrent campaign, to uncommitted peer work, or to the
machine.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
