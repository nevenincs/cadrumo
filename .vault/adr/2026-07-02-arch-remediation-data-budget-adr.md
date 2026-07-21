---
tags:
  - '#adr'
  - '#arch-remediation-data-budget'
date: '2026-07-02'
modified: '2026-07-17'
related:
  - '[[2026-07-02-aeat-architecture-review-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-05-15-corpus-registry-packaging-adr]]'
  - '[[2026-07-06-arch-remediation-data-budget-research]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---

# `arch-remediation-data-budget` adr: `Whole-tree and split-distribution data budgets` | (**status:** `accepted`)

## Problem Statement

Bundled data grew from roughly 311 MiB to 516 MiB without a decision gate. The
later wheel split moved corpus source binaries into two mandatory companions,
which made a single root-wheel size check insufficient: growth could hide in a
companion or in the remaining command-bearing payload. The budget must cover
the whole logical product and each physical artifact slice.

## Decision

Keep three complementary limits, measured from tracked source ownership:

- the complete `src/cadrumo/_data` tree stays at or below 550 MiB;
- the command-bearing runtime slice — the tree minus companion-owned corpus
  source binaries — stays at or below 230 MiB; and
- each `cadrumo-data-*` companion wheel remains below PyPI's 100 MB per-file
  limit.

The runtime and companion-owned source slices must sum exactly to the whole
tree. A split cannot make bytes disappear from budget accounting. Tests and
test fixtures are outside the shipped-data slices and remain excluded from all
three distributions.

## Constraints

- Reviewed corpus, registry, terminology, and agent data remain available to an
  installed cohort; budgeting cannot weaken legal grounding.
- `cadrumo` requires both companions at its exact version. Budget-driven
  partitioning is not an optional degraded product mode.
- Companion ownership is disjoint and exhaustive over split-owned corpus
  binaries. Derived corpus surfaces stay in the command-bearing wheel.
- Budget arithmetic has one executable authority and reports both bytes and
  human-readable MiB/MB consistently.
- Raising a ceiling or changing ownership requires an explicit reviewed
  architecture decision. A silent constant bump is forbidden.

## Implementation

`src/cadrumo/tests/test_data_size_budget.py` measures the whole tree, runtime
slice, companion-owned slice, and their exact sum. The companion packaging
gates build both real wheels, verify their disjoint/exhaustive ownership,
version equality, and file-size cap. Root-wheel gates prove tests and split
source binaries are absent while required runtime data remains.

When a companion approaches its cap, rebalance along a declared corpus
top-level seam or introduce another exact-version companion. When the runtime
slice approaches its cap, remove dead derived data or record a reviewed reason
for growth; do not smuggle runtime data into a companion whose ownership
contract does not fit.

## Rationale

The whole-tree ceiling governs product growth; slice ceilings govern whether
that product can still be distributed. Exact sum and ownership checks close the
evasion introduced by physical splitting. This preserves the accepted offline
corpus architecture while turning the next material increase into a visible
decision.

## Consequences

- Growth cannot hide behind the root/companion boundary.
- Every release pays a small build-and-measure cost for truthful artifact size
  evidence.
- A corpus-heavy campaign may force repartitioning or a reviewed budget change;
  that failure is the intended control, not incidental CI noise.
