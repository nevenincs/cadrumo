---
tags:
  - '#adr'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
body_hash: 'sha256:43d2122a8b55df972b4035f0d94acc0fcdc4285734aa09b9fc06547f140c02fb'
related:
  - "[[2026-07-14-data-output-standardization-audit]]"
---

# `honest-all-green` adr: `Honest all-green burndown` | (**status:** `accepted`)

## Problem Statement

The data-output-standardization campaign closed with campaign-owned failures
at zero, but its S29 gate run documented ~94 residual full-suite failures
triaged as peer-owned or parallel-only: a ~55-test renta registry
grounding-data cluster plus its ~12-test application/modelo cascade,
exception-hierarchy hygiene roots, docs period-token findings, three
master-key-rotation integrity diagnostics, three aggregation
enrollment/precedence failures, two packaging companion-wheel build errors,
~13 structural-inventory findings, and two parallel-only artifacts. The
operator mandate (recorded 2026-07-14) is to drive the whole check surface
to a genuinely green state.

## Considerations

- "Honest" is load-bearing: the project's quality gates forbid mocks,
  fakes, stubs, monkeypatches, skips, xfail, tautological assertions, and
  baseline/allowlist mutes as shortcuts. Green must mean fixed.
- Calculation expectations must come from external authority (AEAT
  workbooks, BOE/AEAT worked examples, registry-authoritative fixtures,
  oracle replay), never from re-running the formula under test; figures are
  cross-checked against live BOE/AEAT text even when the bundled corpus
  states them.
- The failing surfaces belong to several peer campaigns in a shared
  worktree; executors must detect actively-mid-work peer surfaces (git
  log/diff evidence) and coordinate rather than collide, and re-run
  registry failures sequentially before triaging (loader-cache parallel
  race).
- Key-management caution: fixes implicating key schedules or DEK
  derivation are owner-gated, never autonomous.

## Considered options

- **O1 — Leave peer-owned failures to their owning campaigns** (status
  quo): honest triage exists, but the tree stays red indefinitely and every
  campaign pays the owner-triage tax on every gate run; rejected by
  operator mandate.
- **O2 — Coordinated burndown campaign fixing every cluster at root cause
  under the honesty constraints** (chosen): one plan, cluster-per-phase,
  executor-per-cluster, with collision detection against active peer work.
- **O3 — Mute/deselect the known-red set to get fast green**: violates the
  honesty mandate and every quality-gate rule; rejected outright.

## Constraints

- No skips, xfail, mocks-as-shortcuts, tautologies, raised baselines, or
  allowlist mutes; gate-weakening is never a fix.
- Registry data changes commit atomically with the legal entries they
  reference; grounding follows the bundled-corpus-first, live-BOE-crosscheck
  discipline.
- Shared-worktree safety rules bind every executor (no destructive git,
  explicit-pathspec commits, WIP checks).
- Session-limit pauses are resume-events, not failures: paused executors
  resume with context; their surfaces are not reassigned.

## Implementation

One L2 plan (`2026-07-14-honest-all-green-plan`) with a phase per failure
cluster: P01 renta registry grounding + modelo cascade, P02 core hygiene
gates (exception roots, docs period tokens), P03 storage rotation
diagnostics + aggregation enrollment, P04 structural-inventory debt, P05
packaging builds + parallel-robustness of the loader-cache and
import-hygiene proofs, P06 full-suite green verification in both parallel
and sequential modes. Each fix lands with real-behavior tests, exec
records, and step closure; verification is a full-suite run whose remaining
failure count is zero (with any genuinely environment-only findings proven
so with evidence, not assumed).

## Rationale

The S29 triage and the close honesty review (related audit) provide the
grounded failure inventory and per-failure signatures; the burndown turns
that inventory into fixes under the same review-gated execution discipline
the previous campaign proved (independent code review per phase, revisions
on findings). Root-cause fixing under honesty constraints is the only
option consistent with the operator mandate and the standing quality-gate
rules.

## Consequences

- The full tree becomes a trustworthy signal again; future campaigns stop
  paying per-run owner-triage overhead.
- Some fixes land on surfaces owned by in-flight peer campaigns; the
  collision protocol trades speed for safety and may defer clusters whose
  owners are actively mid-fix.
- Grounding the renta cluster properly may reveal genuine engine or
  registry-data defects whose fixes are larger than test repair; those are
  in scope, with legal-grounding discipline, and may extend the plan.
- Environment-only packaging failures, if proven, are documented with
  evidence rather than "fixed" — the honest disposition when the defect is
  not in the repository.
