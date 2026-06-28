---
tags:
  - '#adr'
  - '#atomic-relocation-coordination'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-30-identity-primitives-adr]]"
  - "[[2026-05-28-codebase-solidification-adr]]"
  - "[[2026-05-31-transient-metastate-sweep-audit]]"
  - '[[2026-06-04-atomic-relocation-coordination-research]]'
---

# `atomic-relocation-coordination` adr: `every-symbol-relocation-is-a-single-atomic-commit` | (**status:** `accepted`)

## Problem Statement

The `core-authority` ADR establishes canonical homes for cross-module
definitions. The `codebase-solidification` plan executes the migrations as
Steps. Neither document codifies the coordination contract for a single
relocation. The shared worktree runs many parallel agents holding
uncommitted changes; a relocation that lands the canonical-site move in one
commit and the consumer sweep in a later commit creates a window in which
every consumer is broken and the test suite cannot collect. Today the
suite returned 16 transient `ImportError` collection failures during a
single observation window; the same 16 surfaces collected cleanly within
minutes as peer commits landed the consumer half. Each transient window is
a coordination defect, not a known cost: every agent landing parallel work
during the window observes false-failure signal, peer agents waste
investigation turns, and the campaign's quality gate (suite must collect)
is structurally unavailable. Examples observed today: `InvoiceKind` moved
to `aeat.domain.iva._classification` but consumers still import from
`aeat.domain.invoices`; `ModeloDraftStatus` moved to
`aeat.domain.submission._protocols` but consumers still import from
`aeat.adapters.outbound.aeat.export`; `PROMOTE001_PROTECT_LIST` removed
under the transient-metastate sweep audit recommendation while consumers
remained in mid-deletion state.

## Considerations

The branch name `chore/eliminate-shims` declares intent that re-exports
are not a coordination tool. Re-exports cannot be reintroduced as a soft
bridge during relocation because the shim ban is the campaign's
load-bearing constraint. The only remaining coordination mechanism is
atomic landing: define the canonical site, sweep every consumer, and
commit both in one explicit-path commit such that the suite collects
cleanly at HEAD before and after.

The `aeat-git-worktree-safety` rule forbids `git stash`, `git reset`, and
every destructive reflow. Parallel agents cannot rescue a half-landed
relocation by stashing peer work and replaying it; the half-landed window
is structurally unfixable except by completing the second half. This makes
the atomic-commit rule a hard discipline, not a preference.

The `aeat-architecture-boundaries` rule already prohibits shims,
compatibility layers, and duplicate legacy APIs; `aeat-source-hygiene`
prohibits dead code. Re-exports authored as a "temporary bridge" during a
relocation are shims by definition and would violate both. The
`retire_means_delete_fully` memory rule extends the same constraint to
deletion: a deletion is a single atomic commit that updates every
reference, not a multi-commit deprecation walk.

## Constraints

The relocation worker MUST hold the canonical-site move, every consumer
update, every test fixture update, and every `__all__` baseline update in
the same git index, and MUST commit them with one explicit-path
`git commit -- <files>` invocation. The worker MUST run
`uv run --no-sync pytest --collect-only -q` immediately before the commit
and observe clean collection. The worker MUST NOT split the relocation
across two commits even if the second commit would be authored in the
same minute. The worker MUST NOT introduce a re-export shim in either the
canonical or the legacy package `__init__.py` to soften the move.

A relocation that cannot fit in one atomic commit is too large; it must
be split by symbol (one symbol per atomic commit) rather than by phase
(definition then consumers). The `vault plan step add` boundary is one
Step = one symbol = one atomic commit.

When a coordinator detects mid-flight collection breakage caused by a
peer relocation, the coordinator MUST NOT attempt to fix the consumers
forward; the coordinator MUST wait for the peer to land the second half
and re-collect, OR flag the peer's relocation as a coordination defect to
be rolled forward by the peer. The shared worktree forbids reverting
peer commits.

## Implementation

Add one Step row per in-flight symbol relocation under the existing
`codebase-solidification` plan via `vault plan step add` (do NOT author a
parallel plan document). Each Step's verification gate is the
`pytest --collect-only -q` clean-collection check at HEAD after the
atomic commit. Each Step's commit attaches the symbol name to the commit
subject so future audits can grep history for `relocation:<symbol>` to
trace the canonical-home decisions.

The `aeat-architecture-boundaries` project rule receives one new clause:
"Symbol relocations land in one atomic explicit-path commit; the test
suite must collect cleanly at HEAD immediately before and after; never
split the canonical-site move from the consumer sweep across commits."
The rule is propagated via `vaultspec-core sync` so all provider rule
directories regenerate consistently.

The `vault plan` CLI receives no schema change; the discipline is
documentation + audit, not CLI enforcement.

## Rationale

The atomic-commit rule is the smallest mechanism that closes the
coordination window without re-introducing shims. It costs the worker one
extra `pytest --collect-only` invocation per relocation Step (~30 seconds
warm). It produces a single audit-grep surface (`relocation:<symbol>` in
commit subjects) that lets the next codebase-solidification audit
enumerate the campaign's history without reading the plan. It composes
with `aeat-git-worktree-safety` because every parallel agent's discipline
already requires explicit-path staging; one extra discipline is one extra
line of brief, not a new tool.

The alternative (re-exports as temporary bridges) would re-establish the
exact shim surface the `eliminate-shims` campaign is closing; rejected
under `retire_means_delete_fully` and the existing no-shim rules.

The alternative (longer plan Steps that bundle multiple symbols per
commit) would amplify the blast radius of any single broken commit and
make audit-grep over commit history less useful. Rejected.

## Consequences

The next codebase-solidification audit can compute relocation completion
by enumerating `relocation:<symbol>` commit subjects against the
canonical-home audit's protect-list-excluded inventory. The two
relocations in flight today (`InvoiceKind`, `ModeloDraftStatus`) are
tracked as Steps under the existing plan; the peer worker driving them
will land them as atomic commits or surface a coordination defect.
Future relocations follow the same template; no exception path exists.

The discipline does not retroactively penalise the campaign for the 16
transient errors observed today. Those errors are recorded in the
transient-metastate-sweep audit as factual observations; the ADR closes
the gate going forward, not backward.

The rule deliberately does NOT prescribe a CI hook, a pre-commit check,
or a tooling-enforced gate. The single-author single-commit discipline is
testable by reading `git log -p` per symbol relocation; tooling
enforcement is deferred until a future ADR if the human-discipline path
fails. Adding tooling now would couple this ADR to CI infrastructure
that is itself mid-restructure.
