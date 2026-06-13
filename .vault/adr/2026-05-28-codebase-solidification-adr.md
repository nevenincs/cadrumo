---
tags:
  - '#adr'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-27-centralized-module-drift-audit]]"
  - '[[2026-06-04-codebase-solidification-research]]'
---

# `codebase-solidification` adr: `Recurring hardening epic strategy` | (**status:** `accepted`)

## Problem Statement

The drift audit dated `2026-05-27` surfaced ~115 concrete findings
across eight axes (centralized exceptions, centralized logging,
centralized locale, pydantic boundary models, helper duplication,
stubs / dead code, hardcoded values / enum bypass, typecheck escape
hatches). The codebase already ships every centralized module those
findings would route through (`aeat.core.errors`, `aeat.core.logging`,
`aeat.core.i18n`, `aeat.core.external_constants`, the registry of
`StrEnum`s scattered across `domain/` and `application/`). The drift
is **not absence of canonical infrastructure**; the drift is **failure
to enroll new callers into the canonical infrastructure** as the
codebase grew.

A single-shot remediation campaign would close the current findings
but cannot prevent the same drift returning two months later. The
codebase is large (1530 production files), parallel agent campaigns
land work continuously, and every fix is one careless review away
from being undone. What is needed is a **recurring hardening epic**
that re-audits the same surface on a fixed cadence, treats every
recurrence as a separate trackable Step, and accumulates an
auditable history of regressions so the pattern that produces them
can be diagnosed and prevented at the review-gate level.

## Considerations

- The audit swarm pattern (`aeat-swarm-audit-cadence.md`) already
  exists for cross-domain drift detection. The current rule covers
  six axes; this ADR extends the cadence to the eight drift axes
  identified in the audit plus a ninth axis covering the test
  suite's semantic intent and actual coverage.
- The plan-hardening convention provides an `L4` tier (`Epic > Wave >
  Phase > Step`) with append-only identifiers and gap-no-reuse. This
  is exactly the structure a recurring epic needs: each Wave is a
  pass over the eight axes, each Phase is an axis, each Step is one
  finding from that axis. Closed Steps stay closed; recurrences in
  the next Wave get new Step ids.
- The no-compression rule (`N self-similar actions = N rows`) is the
  whole point. Collapsing "replace every `logging.getLogger` with
  `get_logger`" into one Step destroys the line-by-line regression
  history. The user explicitly asked for extreme repetition; the
  convention rewards it.
- Standing review gates G1 through G6 (project memory
  `standing_review_gates`) already encode the policy this epic
  enforces. The epic's role is to surface drift between gate
  enforcement and the resident codebase, then close the gap.
- The audit document is the seed evidence for Wave 1. Subsequent
  Waves will produce their own audit documents under
  `.vault/audit/yyyy-mm-dd-codebase-solidification-wNN-audit.md`,
  one per Wave, written by the same swarm pattern.

## Constraints

- **Hardening only, never weakening.** Every Step lands a structural
  fix paired with a real-behavior test or extends an existing
  invariant. No skip / xfail / mock / tautological assertion is
  acceptable as a closing move. A Step that only adds a comment, a
  TODO, or a deprecation marker is rejected.
- **Use what is already there.** New modules, abstractions, or
  packages must be justified by absence in the current tree. The
  default move is `import` and `replace`, not `create`. The drift is
  underuse, not lack of capability.
- **No shims, no aliases, no deprecation paths.** Per
  `aeat-architecture-boundaries.md` and project memory
  `retire_means_delete_fully`, removed callers go straight to the
  canonical path. There is no transitional cohabitation period.
- **Real-behavior tests.** Per `aeat-quality-gates.md` and
  `aeat-roundtrip-discipline.md`, the verification gate on each
  Step is a real test that fails when the structural fix regresses,
  not a mock that pretends the contract holds.
- **Open-ended.** The epic has no terminal Wave. New Waves are added
  when the prior Wave's swarm re-audit produces fresh findings. The
  epic only closes when three consecutive Waves report zero net new
  findings across all eight axes plus the test-suite axis, at which
  point the epic is archived with a closing audit.

## Implementation

The epic is one `L4` plan document
(`2026-05-28-codebase-solidification-plan.md`) with the Epic intent
block declaring association with `chore/eliminate-shims` worktree on
this repository (the agent-fleet coordination surface that owns the
recurring audit cadence). The plan starts with **Wave 1** populated
from the `2026-05-27-centralized-module-drift-audit` findings,
arranged into **nine Phases** (one per axis: A1..A8 plus a P09
test-suite semantic / coverage audit), with **one Step per finding
and one parallel Step per finding for the test-coverage assertion
that closes it**.

Wave cadence:

1. **Wave 1 - close the inaugural audit.** Land every finding from
   the `2026-05-27` audit. Each fix Step is paired with a
   verification Step that adds or strengthens a real-behavior test
   under the canonical test surface (`src/aeat/.../test_*.py`). No
   xfail, no skip, no mock.
2. **Wave 2..N - recurring sweep.** When Wave 1 reaches 80%+ closed
   Steps across every Phase, dispatch the eight-axis swarm again
   (same brief, same anchors). The output becomes a new audit
   document, and Wave 2 is added to the plan via
   `vault plan wave add`, populated with one Step per fresh finding.
   Findings that match closed Wave 1 Steps by `file:line` are
   flagged as **regressions** in the Step action prose so the review
   record carries the regression signal.
3. **Termination.** When three consecutive Waves produce zero fresh
   findings on every axis, the epic is archived via
   `vault feature archive codebase-solidification` and a closing
   audit document is written.

The plan body uses CLI verbs (`vault plan step add`,
`vault plan phase add --wave WNN`, `vault plan wave add`,
`vault plan epic intent edit`) for every identifier-affecting
mutation. Hand edits to the prose blocks (Phase intent, Wave intent,
Epic intent) are permitted; structural mutations are not.

P09 (test-suite semantic / coverage axis) runs in every Wave even if
no production code Steps need to land in a Phase. It samples the
test surface for: tautological assertions (project rule
`no-tautological-calculation-tests.md`), mock / patch / skip / xfail
usage in test files outside the legitimate boundary-test fixtures,
real-behavior test absence at any persistence boundary touched by a
fix Step, and `pytest` collection coverage versus production module
inventory.

## Rationale

The recurring-epic shape was chosen over a one-shot remediation
campaign for three reasons. First, the swarm-audit cadence rule
already prescribes recurring audits; structuring the remediation
plan to match the cadence keeps the audit output and the remediation
ledger in one document tree rather than scattering follow-ups across
ad-hoc plans. Second, the line-by-line Step grammar (one Step per
finding, one verification Step per fix) creates a regression history
the swarm cadence rule explicitly calls out as the diagnostic surface
for systemic drift. Third, the L4 Epic tier with append-only ids and
gap-no-reuse is the only structural container in the plan-hardening
convention that supports an open-ended sequence of Waves without
breaking identifier stability.

The decision to bias toward "use what is already there" rather than
"introduce a new abstraction" was driven by the audit's own
finding: every centralized module the audit cites already exists.
The drift is enrollment, not capability. New abstractions would add
mass without addressing the underlying enrollment failure.

## Consequences

- The plan document will grow large (Wave 1 ships with ~260 Step
  rows). `vault plan status` over the document will be the canonical
  navigation surface; readers should not skim the body.
- Step backlog will dominate the agent fleet's worktree-In-Progress
  count for several weeks. Per `aeat-agent-delivery.md`, In-Progress
  is restricted to actively worked items with a worktree; pending
  Steps in this plan do NOT count as In-Progress.
- Subsequent Waves require the swarm-audit cadence to be wired into
  a schedule. The cadence rule already establishes monthly as the
  current target. Wave 2 should dispatch no earlier than four weeks
  after Wave 1 reaches the 80%-closed threshold to give real-world
  regression patterns time to surface.
- The epic's closing condition (three consecutive zero-finding
  Waves) is intentionally strict. Premature archival on a single
  clean Wave would re-create the original drift pattern; the
  three-Wave clean-run requirement is the empirical signal that the
  enrollment habit has actually formed.
- The test-suite P09 axis is new. The first execution may produce a
  large finding count because the codebase has not previously been
  audited against the no-tautological-test rule at scale.
