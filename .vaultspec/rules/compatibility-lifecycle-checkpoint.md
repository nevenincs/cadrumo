---
name: compatibility-lifecycle-checkpoint
---

# Persisted-data compatibility posture is regime-switched by a one-way core constant

## Rule

The persisted-data compatibility posture is governed by `aeat.core.COMPATIBILITY_REGIME`,
a one-way constant flipped `PRE_RELEASE -> RELEASED` ONLY by an accepted checkpoint ADR
whose same commit also freezes `aeat.core.RELEASED_FORMAT_FLOORS` at the then-current
per-format durability floors. The regime MUST NOT be read from `Settings`/env, and the
enforcing gates MUST NOT be skipped, weakened, or monkeypatched.

- **Pre-checkpoint (`PRE_RELEASE`, today):** `no-legacy-compatibility` governs unchanged —
  delete-not-migrate, durability floors may chase the current version, no read-tolerance
  of pre-current shapes. Installing the dormant regime constant, the empty upgrader
  registries, and the regime-aware gates is NOT "maintaining forward-compat" — it is the
  same blessed category as a `max_supported_version` ceiling; it reads no old shapes and
  migrates nothing.
- **Post-checkpoint (`RELEASED`):** for every persisted format (secure-object, bundle,
  sealed archive, and any new format enrolled at birth) the durability floor is FROZEN at
  its released value; every version bump MUST land, in the same commit, its one-hop
  upgrader (the archive tier: a version-aware reader), a committed pre-bump serialized
  fixture, and a restorability test that loads the old bytes through the real production
  read path; strict persisted-read models stay `extra="forbid"` with the pre-validation
  upgrade hop as the ONLY sanctioned tolerance point; a persisted-model shape change rides
  a version bump + upgrader, never a loosened model. `no-legacy-compatibility` still bars
  read-tolerance of shapes nothing released wrote, and bars shims/aliases, in BOTH regimes —
  it narrows to "no legacy beyond the released floor", it does not die.

## Why

The `released-data-durability` campaign installed the per-format mechanism (version
ceilings, empty per-hop upgrader registries, chain-upgrade on read, the archive floor-pin)
but left the TRANSITION ungoverned: nothing defined WHEN the posture flips from the
pre-release delete-not-migrate regime to the post-release durability-mandatory regime, WHAT
flips, or WHAT enforces it — so "decide at the checkpoint" was itself an open deferral that
would surface as a stranded-taxpayer-data hazard on the first post-release version bump. A
runtime/env flag can silently differ per machine or CI and be patched in its own gate; a
compliance regime must instead be a property of the codebase commit. Making the checkpoint
a one-way repo-committed constant plus a version-milestone tripwire gives the transition a
conscious owner (the flip commit), a trigger (the tripwire that reds CI if a 1.0 is cut
unflipped), and gate-enforced teeth, while changing zero behaviour today. Recorded in ADR
`2026-07-09-compatibility-lifecycle-adr`; companion to `no-legacy-compatibility` (which
governs the pre-release regime verbatim) and `released-data-durability` (which built the
mechanism this rule switches).

## How

- **Good:** post-flip, a bundle `v3 -> v4` bump lands the raw-mapping upgrader in
  `BUNDLE_PAYLOAD_UPGRADERS`, a committed `v3` serialized fixture, and a test that loads the
  `v3` bytes through the real deserialize path and asserts strict equality — all in one
  commit.
- **Good:** pre-flip, raising the archive version and its floor together (delete-not-migrate),
  with the floor-pin gate green because `expected_floor(PRE_RELEASE, ...) == current`.
- **Good:** a new persisted format enrolls its floor/version + an (empty) upgrader registry +
  its lineage gate at birth, in both regimes.
- **Bad:** post-flip, raising any durability floor above its released value to dodge writing
  an upgrader — the frozen-floor gate refuses it.
- **Bad:** flipping `COMPATIBILITY_REGIME` back to `PRE_RELEASE`, or reading the regime from
  `Settings`/env, or loosening a persisted read model to `extra="ignore"` instead of
  versioning the shape.
- **Bad:** fabricating an old-version fixture or a real upgrader BEFORE a genuine
  post-checkpoint bump needs it — `no-legacy-compatibility` forbids inventing shapes nothing
  wrote; the harness ships empty and vacuous until then.

## Source

ADR `2026-07-09-compatibility-lifecycle-adr` (accepted), decided by an authorized fable
architecture pass and approved by the operator, resolving the transition the
`2026-07-08-released-data-durability-adr` left ownerless. Companion rules:
`no-legacy-compatibility` (pre-release posture, unchanged), `aeat-schema-central-config`,
`sensitive-financial-data-secure-storage-only`. Enforced by the regime-aware lineage gates
and the central `test_compatibility_lifecycle_gate` (version tripwire + one-way coherence +
enrollment).
