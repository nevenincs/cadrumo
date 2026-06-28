---
tags:
  - '#research'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
  - '[[2026-06-04-just-tooling-bootstrap-adr]]'
  - '[[2026-06-04-uv-venv-lock-workaround-audit]]'
---

# `repo-health-triage` research

## Question

How should the repository health findings from the new `just` audit surface be
triaged into executable work without weakening the shared-worktree safeguards,
test-realism rules, or architectural boundaries?

## Findings

The diagnostic surface is dependable enough for triage. `just tooling-doctor`,
`uv lock --check`, `uv pip check`, and `just install` pass without requiring
`uv sync`. The resident VaultSpec RAG service owns the code index, so searches
must use `vaultspec-rag search --port 8766` to avoid Qdrant lock contention.

The highest-return first work is structural, not broad refactoring. The
relative-import checker has exactly 14 violations, `deptry` reports exactly 6
dependency findings, and `vulture` reports exactly 15 dead-code candidates. These
are tractable and should close before larger type and complexity work because they
restore trust in the hard gates.

Type work should be clustered by root cause rather than by diagnostic count. The
dominant type clusters are aggregation source-kind taxonomy drift, secure
repository payload-type invariance, optional/member narrowing gaps, constructor
coercion mismatches, and strict generic annotation cleanup. Addressing these
families should collapse many `ty` and Pyright diagnostics without adding local
casts or ignores.

Complexity work must be sequenced behind stable gates. The top refactor clusters
are `entrypoints/cli/_modelo.py`, `application/modelo/_actions.py`, registry
bindings and formula runtime, ledger CLI/actions, identity diagnostics, and the
live/auth cluster. The first slices should turn CLI handlers into parse-call-render
orchestrators and move typed input assembly into application modules.

Duplication and test-shortcut findings are not greenfield. A previous
`code-duplication-sweep` plan closed many symbol and boilerplate consolidations,
and a secure-storage test-hygiene audit already identifies env monkeypatch and
fake/stub pressure. Current triage should reference those artifacts and focus on
residual duplication, policy separation, and guard ratchets.

Security scan results need policy normalization before remediation counts are
actionable. Semgrep currently scans production code, tests, mirrored official
data, and fixtures together. A production/data/test policy split is a prerequisite
to using security counts as a meaningful gate.

## Recommendation

Create an L3 VaultSpec plan that sequences health remediation into five waves:
diagnostic gate stabilization, type-control ratchets, complexity decomposition,
hygiene cleanup, and final ratchet/policy hardening. Use the resident RAG server
for discovery and keep every execution slice narrow enough for independent agents
to verify with scoped `just` and `uv run --no-sync` commands.
