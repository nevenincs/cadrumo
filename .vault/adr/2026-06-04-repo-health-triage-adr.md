---
tags:
  - '#adr'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-repo-health-triage-research]]'
  - '[[2026-06-04-repo-health-triage-reference]]'
---

# `repo-health-triage` adr: `diagnostic-first remediation sequence` | (**status:** `accepted`)

## Problem Statement

The project now has a cohesive `just` audit surface and a repaired virtual
environment, but the first full-repo run exposes many red diagnostics across type
checking, import boundaries, complexity, dependency drift, dead code, duplication,
security policy, and Ruff. Treating the full diagnostic count as one remediation
task would be too broad for a shared worktree and would make it hard to protect
concurrent teams.

## Considerations

The health audit combines hard-gate failures with advisory discovery findings.
Relative imports, dependency drift, and dead-code candidates are small and
repeatable. Type diagnostics are numerous but cluster around shared contracts.
Complexity findings identify real refactor opportunities but have higher behavior
risk. Security and duplication reports require policy separation before raw counts
can become gates.

## Constraints

All semantic discovery must use the resident VaultSpec RAG server through
`vaultspec-rag search --port 8766` while that service owns the local Qdrant store.
No remediation plan may require `uv sync` while the shared `.venv` is locked.

The shared worktree may contain unrelated dirty changes. Execution must not use
stash, reset, checkout, or destructive cleanup, and every work slice must avoid
reverting files owned by other agents.

## Implementation

Sequence repository-health remediation by diagnostic reliability and blast radius:
close small structural hard-gate findings first, then address type root-cause
families, then decompose complexity hotspots, then clean dependency/dead-code and
duplication findings, and only then promote policy ratchets.

The implementation plan is divided into waves for diagnostic gates, type-control
root causes, complexity decomposition, hygiene cleanup, and final ratchet policy.
Each step owns a narrow path scope so separate agents can execute without sharing
write sets.

## Rationale

The relative-import, dependency, and dead-code findings are small enough to close
with focused reviews and provide immediate trust in the tooling. Type errors are
numerous but cluster around a few design decisions, so they should be repaired at
the source instead of suppressed locally. Complexity findings require refactors
that can change behavior, so they should follow restored structural and type gates.

Security and duplication findings need policy context. Semgrep currently mixes
production code with mirrored official data and tests. Duplication is low overall
and has prior plan coverage, so residual work should target concrete drift risks
rather than blanket abstraction.

## Consequences

Execution becomes agent-friendly: independent workers can take scoped plan rows
without sharing write sets. The project avoids turning advisory red dashboards into
hard gates before baselines are understood.

The tradeoff is that full-tree counts will remain red while root-cause waves land.
Each wave must therefore record scoped command output and avoid claiming full-repo
closure until the final ratchet wave.

## Codification candidates

- **Rule slug:** `repo-health-ratchets-follow-baselines`.
  **Rule:** A red advisory audit may become a hard gate only after a baseline,
  exclusion policy, and focused remediation wave are recorded in VaultSpec.
