---
tags:
  - '#adr'
  - '#compatibility-lifecycle'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:bafea829e45f1be5cfcd046832cad8fa0ffbbb7afe8f2e77297c03ca34f2d37f'
related:
  - "[[2026-07-09-compatibility-lifecycle-research]]"
  - '[[2026-09-02-compatibility-lifecycle-ci-policy-rehome-research]]'
---
# `compatibility-lifecycle` adr: `compatibility-lifecycle checkpoint: regime-switched dormant durability governance` | (**status:** `accepted`)

## Problem Statement

Two binding operator directives pull apart across time. Pre-release, the
`no-legacy-compatibility` rule stands unchanged — delete-not-migrate, durability
floors chase the current version, no read-tolerance of pre-current shapes. Post-
release, struct compatibility and multi-year persistence of a taxpayer's filed
data become MUSTS (the routine floor is the LGT four-year prescription; the
`released-data-durability` ADR already observes the floor "can effectively never
move for filed taxpayer data"). The durability campaign installed the
mechanism — version ceilings, empty per-hop upgrader registries, chain-upgrade on
read, and the archive floor-pin — but left the TRANSITION ungoverned: nothing
defines WHEN the posture flips, WHAT flips, or WHAT enforces it. "Decide at the
checkpoint" is itself a deferral. This ADR decides the governance now, as a
dormant, regime-switched gate that is a no-op today and activates on a one-line,
ADR-gated flip. It is the compatibility-lifecycle companion to
`released-data-durability` (which built the per-format mechanism) and to the
`no-legacy-compatibility` rule (which governs the pre-release regime unchanged).

## Considerations

- The `no-legacy-compatibility` rule already blesses "a `max_supported_version`
  ceiling that refuses a FUTURE shape" as forward-compatibility to keep, and the
  archive floor-pin test is standing precedent that a gate binding future authors
  is not maintained-compatibility code. A regime constant, empty registries, and
  test-time assertions read no old shapes, migrate nothing, and tolerate nothing —
  they are policy metadata, the same category as the blessed forward version
  field. The line: constants / gates / empty-registries / scaffolds are
  installable now; actual upgraders, version-aware readers, and old-shape fixtures
  remain forbidden until a real post-checkpoint bump needs them.
- The three persisted formats and their current versions/floors: secure-object
  (`SECURE_OBJECT_DURABILITY_FLOOR = 1`), bundle (`BUNDLE_SCHEMA_VERSION = 3`),
  sealed archive (`_ARCHIVE_SCHEMA_VERSION = _ARCHIVE_DURABILITY_FLOOR = 2`).
- A compliance regime must not vary per machine, be silently unset in CI, or be
  monkeypatchable in its own enforcing gate — which rules out `Settings` (env/
  `.env`-populated, `override_settings`-patchable).

## Considered options

- **Checkpoint as a `Settings`/env flag** — rejected. `Settings` is
  environment-populated and test-overridable; a compliance regime must be a
  property of the codebase commit, not the runtime environment or a CI variable.
- **Checkpoint as an on-disk released-data marker** — rejected. Per-installation
  and invisible to CI, where the enforcement lives; it answers "does this machine
  hold released data", not "may this codebase drop a format".
- **Checkpoint as a version milestone alone** — rejected as primary (release-please
  moves versions automatically; the flip must be conscious) but KEPT as a tripwire.
- **Chosen — a one-way repo-committed core constant + a version-milestone
  tripwire.** `COMPATIBILITY_REGIME` (`PRE_RELEASE` → `RELEASED`) decides; the
  tripwire (`regime is PRE_RELEASE` ⇒ package version `< 1.0.0`) catches forgetting
  to flip before the first release. The constant is the conscious owner of the
  transition; the milestone is the safety net.

## Constraints

- Builds ON the existing durability substrate (`_schema_lineage.py`, `_bundle.py`,
  `_service.py` and their lineage-gate tests); it must not duplicate or weaken
  them, and the refactor must be behaviour-identical while `PRE_RELEASE`.
- The enforcing gate must be testable without monkeypatching (per the durability
  ADR's no-patching constraint): the `RELEASED` branch is exercised via pure
  predicates fed synthetic `(regime, floors)` inputs, not a mutated global.
- Import hygiene: the core policy is consumed through the `aeat.core` facade; each
  tier gate keeps its own private constants intra-package.

## Implementation

A new `aeat.core.compatibility_lifecycle` module carries the `CompatibilityRegime`
enum, the one-way `COMPATIBILITY_REGIME` constant, a `RELEASED_FORMAT_FLOORS`
mapping (`None` until the flip), and PURE policy predicates that take explicit
parameters — `expected_floor(regime, format_key, current_version, released_floors)`
and a `lineage_obligations(...)` returning the violated obligations. The three
per-tier lineage gates become regime-aware: while `PRE_RELEASE` they assert exactly
what they assert today (`expected_floor(PRE_RELEASE, key, current, None) == current`),
and post-flip they additionally assert floor-freeze at the released value,
upgrader-chain completeness from the released floor, and cross-version fixture
coverage. One central repo-wide gate asserts the version-milestone tripwire, the
one-way coherence invariant (`RELEASED_FORMAT_FLOORS` populated ⇔ regime `RELEASED`),
and enrollment (every populated floor key maps to a live tier). An empty
fixture-corpus harness (directory + vacuous coverage assertion) ships now. The
whole mechanism is DORMANT today — no read path changes by a byte, registries stay
empty — yet its `RELEASED` branch is proven correct by synthetic-input tests. The
escalation is precise: the floor-pin's "a version bump needs a conscious decision"
gate becomes, post-flip, "upgrader mandatory + committed old fixture + restorability
proof through the real read path," switched by the constant. Governance is a
COMPANION rule `compatibility-lifecycle-checkpoint` authored at the vaultspec source
(no-legacy stays verbatim, gaining only a Status cross-reference).

## Rationale

The decision resolves the transition the durability ADR left ownerless: the flip
gets a conscious owner (the flip commit), a trigger (the tripwire), and teeth
(regime-switched gates), while changing zero behaviour today. It honours the
operator's pre-release ruling (no forward-compat maintained now) because installing
a dormant gate is categorically the blessed forward-field/ceiling shape, not
maintained compatibility code — the same reasoning the archive floor-pin already
relies on. Grounded in the read-only decision pass over the durability substrate
and the `no-legacy-compatibility` carve-outs (see the research doc).

## Consequences

- Good: the pre→post-release transition acquires an owner, a trigger, and
  gate-enforced teeth, closing the durability ADR's "the flip has no owner" gap;
  zero behaviour change today; the pre-release posture is not weakened by one line
  of read-path code.
- Accepted cost: a second constant surface to keep coherent (mitigated by the
  coherence + enrollment gates); post-flip version bumps become materially more
  expensive (fixture + upgrader + restorability test) — which is the point.
- Neutral: read-repair (re-persisting chain-upgraded rows at current) stays out of
  scope, as the durability ADR already ruled.
- The only genuinely deferred items are the literal future flip commit and the real
  upgraders / version-aware readers / old-shape fixtures that `no-legacy-compatibility`
  correctly forbids fabricating before a real post-checkpoint bump exists; the
  calendar date of the flip is the operator's release call, bounded by the tripwire
  to no later than the 1.0 cut.
