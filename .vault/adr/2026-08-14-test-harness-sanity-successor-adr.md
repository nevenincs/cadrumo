---
tags:
  - "#adr"
  - "#test-harness-sanity"
date: '2026-08-14'
related:
  - "[[2026-08-14-test-harness-sanity-two-lane-campaign-research]]"
supersedes:
  - '2026-07-08-test-worker-count-policy-adr'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:b185a997830540465ab05956d5a5a223d834414463a3ae1e2cc985108c3cd083'
---
# `test-harness-sanity` adr: `canonical fixture ownership and independently verdictable harness execution` | (**status:** `accepted`)

## Problem Statement

The test harness has no single enforceable ownership model spanning fixtures,
collection policy, expensive self-tests, and xdist width. Local duplication and
split hooks can preserve green subsets while different test surfaces observe
different fixtures or enforcement. Expensive installed-process and full-corpus
proofs also run inside the routine unit verdict, while the repository's active
worker hook reverses the accepted operator-only worker policy without a
successor decision.

This record establishes one coherent harness boundary. It extends the accepted
pytest-only and test-topology decisions, applies the CI rule that verdict
granularity follows determinism, and pivots from the operator-only authority in
`2026-07-08-test-worker-count-policy-adr`.

## Considerations

- Fixture equality is only a candidate signal; scope, autouse behavior,
  constraints, visibility, lifecycle, consumers, and semantic ownership decide
  substitutability. See `2026-08-14-test-harness-sanity-two-lane-campaign-research`.
- Test and fixture ownership remains at the narrowest package or architectural
  boundary, with the central harness reserved for genuinely cross-cutting
  policy. See `2026-06-05-test-topology-refactor-adr`.
- Real-behavior enforcement cannot be weakened through replacement controls,
  allowlists, suppressions, skips, or simulated harness proofs. See
  `2026-04-17-pytest-only-testing-adr`.
- Collection policy must reach every selected test from one root authority;
  subtree-local enforcement is not a repository invariant. See
  `2026-08-14-test-harness-sanity-two-lane-campaign-research`.
- Expensive deterministic harness proofs need a verdict separate from routine
  unit behavior, without inventing another architectural marker taxonomy. See
  `2026-08-05-ci-lane-deconflation-adr`.
- Worker width needs one repository-visible authority that applies to every
  `-n auto` invocation shape while preserving deliberate explicit overrides.
  See `2026-08-14-test-harness-sanity-two-lane-campaign-research`.

## Considered options

**Canonicalize fixtures from a semantic census at the narrowest common owner
(chosen).** This preserves fixture lifetime and visibility as explicit
constraints while removing substitutable definitions across every Python test
surface.

**Consolidate equal fixture bodies into one broad root conftest (rejected).**
This is mechanically simple but silently broadens visibility and can change
scope, autouse, and lifecycle semantics.

**Keep local definitions and add drift inventory only (rejected).** Detection
does not establish one authority and leaves every duplicate available to drift.

**Keep marker taxonomy at the root and banned-live-import policy in the central
subtree (rejected).** The split cannot enforce the live-import contract outside
that subtree.

**Keep expensive self-proofs in the unit lane (rejected).** The result remains
correct but makes routine unit verdicts pay for nested xdist pools and recursive
full-corpus collection.

**Use one dedicated deterministic harness lane (chosen).** Installed-hook,
real-process, and full-collection proofs keep real behavior and obtain their own
verdict without changing module ownership markers.

**Restore operator-set `PYTEST_XDIST_AUTO_NUM_WORKERS` as the only worker
authority (rejected).** It preserves uncapped solo auto-sizing but makes the
shared-host safety policy depend on every invocation remembering external
state.

**Make the project-branded hook authoritative for `-n auto` (chosen).** An unset
or invalid `CADRUMO_PYTEST_WORKERS` resolves to the repository default of six;
a valid value overrides that default, and explicit `-n <N>` remains the
deliberate escape hatch. The native pytest-xdist variable is no longer a second
authority.

## Constraints

- The accepted pytest-only and test-topology decisions are stable parents. This
  record does not change their real-behavior controls, execution/hex ownership
  taxonomy, or domain-local `tests/` topology.
- Fixture deletion requires a census record proving substitutability and naming
  the canonical owner. Broader visibility is not evidence of correct ownership.
- Canonicalization removes obsolete definitions and updates consumers directly;
  compatibility aliases, bridge fixtures, and transitional duplicate owners are
  forbidden.
- Canonicalization must preserve fixture name, scope, autouse behavior,
  constraints, teardown, and visibility unless a separately grounded behavior
  change is approved.
- Root collection enforcement must remain fail-closed for marker taxonomy and
  banned imports across all live-test locations, with no duplicate subtree
  traversal.
- The dedicated harness lane must exercise installed hooks and real child
  processes. Direct calls to pure helpers may complement but never replace those
  proofs.
- The harness lane is selected by explicit owned paths or recipe membership,
  not by introducing a runtime-cost marker that competes with the accepted
  execution and hexagonal taxonomies.
- The project worker hook governs only `-n auto`. CI and operators retain
  explicit-width authority through `CADRUMO_PYTEST_WORKERS` or `-n <N>`; no
  second environment variable may compete for the same resolution.
- The six-worker default and explicit CI widths require fresh solo, CI, and
  concurrent shared-host verification before campaign close. A materially
  different result requires an ADR amendment rather than silent code drift.
- Shared-worktree overlap changes sequencing and ownership coordination, never
  the codebase-wide census boundary.

## Implementation

### D1 - Census-backed fixture canonicalization

Inventory fixtures across root configuration, `src`, `dev`, and `packaging`.
For every candidate cluster, record decorator form, name, scope, autouse
behavior, constraints, teardown, consumers, visibility boundary, and nominated
owner. Consolidate only substitutable definitions at the narrowest common
owner. Move owner-specific behavior tests and their fixtures out of the central
harness when a narrower package owns them. Each migration slice removes the
redundant definitions atomically and proves collection and fixture reach from
every affected subtree.

### D2 - One root collection-policy authority

The repository-root collection surface becomes the sole owner of marker
taxonomy and banned-live-import enforcement. It applies both contracts to every
collected item and every live-marked module regardless of subtree. Child
conftests retain only genuinely local fixture behavior; they do not repeat the
root taxonomy traversal or define a narrower version of the live-import rule.

### D3 - One independently verdictable harness lane

Installed-hook worker resolution, real-process collection controls, and the
full-corpus collectability proof move out of routine unit execution into one
dedicated deterministic harness lane. The lane runs independently and reports
its own verdict. Pure worker-resolution logic and bounded malformed-module
controls remain in routine unit coverage where they do not create recursive
process or full-collection cost.

### D4 - Repository-owned xdist auto-width

The project-branded worker hook is the sole resolver for `-n auto` and defaults
to six workers. `CADRUMO_PYTEST_WORKERS` is the one named configuration override
for recipe and direct-pytest paths; an explicit `-n <N>` continues to bypass
auto resolution. The native `PYTEST_XDIST_AUTO_NUM_WORKERS` variable is not
consulted, eliminating dual authority. CI declares its intended width explicitly
instead of relying on the repository default.

### D5 - Two parallel implementation waves

The implementing roll-up plan has two parallel waves sharing this record's
ownership, collection, lane, and worker contracts. One wave owns the census and
fixture/test canonicalization. The other owns root-hook unification,
real-behavior inventory repairs, worker-policy reconciliation, and
expensive-proof lane enrollment. Their scopes may sequence around active peer
ownership, but neither wave may narrow the complete test-surface mandate.

## Rationale

The chosen design makes ownership explicit at each layer: fixtures belong to
the narrowest semantic owner, collection policy belongs to the repository root,
expensive deterministic proofs belong to a dedicated verdict, and `-n auto`
belongs to one project hook. That alignment is the knockout criterion because
each rejected alternative leaves either duplicate authority or an enforcement
gap.

The fixture decision implements, rather than competes with,
`2026-06-05-test-topology-refactor-adr`; the no-substitution constraint preserves
`2026-04-17-pytest-only-testing-adr`. The separate harness verdict applies the
determinism boundary from `2026-08-05-ci-lane-deconflation-adr` without treating
runtime cost as architecture.

The worker decision deliberately supersedes the operator-only direction of
`2026-07-08-test-worker-count-policy-adr`. The hook-ordering path that decision
deferred now exists as a real-process proof, while the current shared-host
contract needs a safe default that does not disappear when operator state is
absent. A repository default plus explicit CI and operator overrides is the
narrowest enforceable authority supported by the current harness evidence in
`2026-08-14-test-harness-sanity-two-lane-campaign-research`.

## Consequences

- Every fixture has one canonical owner justified by consumer and lifecycle
  constraints, reducing drift without broadening conftest visibility by default.
- Every live-marked module receives the same marker and banned-import policy
  from one root hook.
- Routine unit verdicts no longer absorb nested xdist-pool and recursive
  full-collection costs; those real proofs remain mandatory and visible in a
  dedicated verdict.
- Shared-host `-n auto` invocations fail safe to six workers when no override is
  supplied. CI and deliberate local runs must declare wider or narrower intent
  explicitly.
- The repository gives up native pytest-xdist environment-variable authority and
  uncapped auto-sizing by default. That is an intentional portability cost of
  making shared-host safety enforceable.
- Fixture canonicalization is broad, high-churn work. Census artifacts,
  collection proofs, and peer coordination are required to prevent deletions
  from becoming hidden visibility or lifecycle regressions.
- The harness lane adds another required CI verdict and therefore another
  surface whose enrollment, diagnostics, and blocking posture must remain
  independently maintained.
