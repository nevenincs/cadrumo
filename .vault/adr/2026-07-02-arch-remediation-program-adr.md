---
tags:
  - '#adr'
  - '#arch-remediation-program'
date: '2026-07-02'
modified: '2026-07-17'
related:
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-modelo-surface-adr]]"
  - "[[2026-07-02-arch-remediation-ports-inversion-adr]]"
  - "[[2026-07-02-arch-remediation-engine-lifecycle-adr]]"
  - "[[2026-06-01-domain-boundary-audit-adr]]"
  - "[[2026-05-31-core-authority-adr]]"
  - '[[2026-07-06-arch-remediation-program-research]]'
---
# `arch-remediation-program` adr: `architecture remediation program: wave ordering, ratchets, plan topology` | (**status:** `accepted`)

## Problem Statement

The 2026-07-02 high-level architecture review produced fourteen findings and a
deferral regression register (D1-D11), and the operator directed that every
deferral be treated as regression scope. The findings have a strict dependency
structure (the layering gate itself is broken; the shared orchestrator files
are contended; the bindings surface is mid-consolidation), so uncoordinated
remediation would either measure progress with a broken instrument or send
parallel agents into the same hub files. Separately, the vault's own delivery
record shows large epics stall (three in-flight L4 plans sit at 0%, 82.9%
with 206 alerts, and 99.3%) while small L2/L3 plans close. This ADR fixes
three program-level decisions: the order of operations (waves), the
enforcement mechanism (ratchets), and the plan topology (per-track plans
under one feature family, coordinated by this ADR rather than by an epic).

## Considerations

- The audit register's items are not independent: D1/D8 (gate repair) change
  the measurement instrument every other item is verified with; D9 (bindings
  tails) must close before new resolver conventions land; the modelo-surface
  decision changes the target shape of the two most contended production
  files, so it must precede any fan-out that touches them.
- This is a shared factory worktree with six-agent capacity split across
  Track A (AEAT sync) and Track B (financial input); remediation is a third
  structural track and must not starve the other two.
- New-context agents are dispatched with minimal briefs; the tracking
  structure must let a fresh agent reach full task context from one plan
  stem via `vaultspec-core status` plus grounding links.
- Prior art binds this program: the hexagonal ownership contract and its D4
  persistence ruling (domain-boundary-audit ADR), the core-authority
  constraint that application may reach adapters only through declared
  ports, and the aggregation-taxonomy precedence ladder.

## Considered options

- **Topology option A: one L4 remediation epic.** Pro: single tracking
  surface. Con: the vault's own L4 record (0%/387-step, 99.3%/690-step,
  206-alert epics) shows epics stall and bury new-context agents; rejected.
- **Topology option B: per-finding plans with no program authority.** Pro:
  maximal decomposition. Con: wave ordering and ratchet policy live nowhere
  durable; plans drift and re-litigate ordering per dispatch; rejected.
- **Topology option C (chosen): this program ADR + per-track L1-L3 plans**
  in the `arch-remediation-*` feature family, each `related:`-linked to the
  audit and this ADR.
- **Ordering option A: severity-first** (start with the high finding's
  domain inversions). Con: progress would be measured by a gate with stale,
  duplicated, warn-only exception entries; rejected.
- **Ordering option B (chosen): instruments-first waves** (repair the gate,
  pin the baseline, decide core shapes, then fan out).
- **Ordering option C: parallel-everything.** Con: hub-file contention
  (`_calculation_actions.py`, `_formula_runtime.py`) plus mid-consolidation
  bindings surface; rejected.

## Constraints

- Destructive-git prohibition and shared-worktree discipline bind every
  dispatched agent; hub-file work is single-owner by scheduling, not by
  tooling.
- Every symbol relocation follows the atomic explicit-path commit rule with
  `relocation:` subject tags; no re-export bridges (no-legacy rule).
- Plan closure requires exec records; campaign close requires a
  fresh-context honesty review before the program is declared complete.
- The swarm audit cadence (every 6-8 commits on a structural branch) runs
  through Wave 3; findings it raises are absorbed, not deferred.
- Wave 2 depends on three sibling ADRs being accepted; Wave 3 must not start
  a track whose Wave 2 decision is still `proposed`.

## Implementation

Wave 0 — instruments. One track plan (gates-ratchet): dedupe and re-file the
`.importlinter` ledger, purge the eight dead-module entries, flip
`unmatched_ignore_imports_alerting` to error, replace the
`application → adapters` wildcard with the pinned ~80-edge baseline, and land
count-ratchet gates (pinned-edge counts may only decrease). Register items
D1 and D8.

Wave 1 — drain tails. Close the three open bindings campaigns through their
existing plans (D9); no new plan is cut. Freeze new source kinds and resolver
conventions until closure.

Wave 2 — core decisions. The three sibling ADRs: per-modelo extension
surface (modelo-surface), domain persistence ports inversion
(ports-inversion, refining boundary-audit D4 from opportunistic to planned),
and engine/session lifecycle unification (engine-lifecycle). ADR authoring
runs in parallel with Waves 0-1; implementation of each starts only on
acceptance.

Wave 3 — fan-out. Independent track plans, parallelizable across agents:
ports-inversion execution (one phase per domain, ~11 domains, fincas
template), crash-window matrix + injection tests (D11), deferred source-kind
promotion or re-ratification (D4/D5), registry format convergence decision
and execution (D6), data-budget gate and wheel-content decision, lazy-import
policy allowlist + ratchet (D7).

Wave 4 — closure. Fresh-context honesty review against this ADR and the
audit register; codify durable lessons; verify every ratchet is at zero or
frozen by an accepted ADR.

Ratchet policy (program-wide): every wave lands its own enforcement gate in
the same change as its remediation, so a later wave cannot silently regress
an earlier one; a ratchet may only be loosened by an accepted ADR.

Plan topology: one plan per track named
`yyyy-mm-dd-arch-remediation-<track>-plan`, tier L1-L3 by scope, never L4;
each plan's `related:` carries the audit and this ADR; dispatch briefs cite
the plan stem, this ADR, and the audit finding slug (the `### <slug>`
anchors and D-numbers exist for this purpose).

## Rationale

Instruments-first is forced by the audit's own evidence: the gate that would
verify all other remediation carries duplicated blocks, eight dead entries,
and warn-only alerting — repairing it first converts the operator's
"deferrals are regression scope" directive from intent into enforcement.
Core-decisions-before-fan-out is forced by contention: the modelo-surface
decision changes the target shape of the files every modelo campaign
touches, and deciding it late would have fan-out workers adding carve-outs
to files another campaign is shrinking. Per-track plans over an epic is an
evidence-based choice from this vault's delivery history, and it is also
the better shape for new-context dispatch: `vaultspec-core status <plan>`
plus two grounding links reconstructs full task context in one read.

## Consequences

- The program gains enforceable, per-wave progress that survives agent
  turnover; the cost is ~8 plan scaffolds and their exec-record overhead.
- Ratchet gates add permanent CI surface (~a handful of inventory tests);
  this deepens the audit's own observation that the enforcement ecosystem
  is large — accepted deliberately, with the ledger-hygiene gate now
  auditing the auditors.
- This ADR becomes the single ordering authority: if ordering changes, this
  document is edited (or superseded), never bypassed — a stalled wave is
  therefore visible as a contradiction between this ADR and plan states.
- Waves 0-1 delay visible "real" remediation by days; accepted, because the
  alternative is unmeasurable progress.
- Risk: the remediation track competes with Track A/B for capacity;
  mitigation is board discipline (only actively-worked items In Progress)
  and the small-plan topology, which tolerates preemption between tracks.
