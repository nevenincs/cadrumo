---
name: compatibility-lifecycle-checkpoint
---

# Persisted-data compatibility posture is regime-switched by a one-way core constant

## Rule

The persisted-data compatibility posture is governed by `cadrumo.core.COMPATIBILITY_REGIME`,
a one-way constant flipped `PRE_RELEASE -> RELEASED` ONLY by an accepted checkpoint ADR
whose same commit also freezes `cadrumo.core.RELEASED_FORMAT_FLOORS` at the then-current
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

Per ADR `2026-07-09-compatibility-lifecycle-adr`, the `released-data-durability` campaign
built the per-format mechanism but left the TRANSITION ungoverned — WHEN the posture flips,
WHAT flips, and WHAT enforces it were an open deferral that would surface as a
stranded-taxpayer-data hazard on the first post-release bump. A runtime/env flag can
silently differ per machine and be patched in its own gate, so the regime is instead a
one-way repo-committed constant plus a version-milestone tripwire — a conscious owner (the
flip commit), a trigger (CI reds if a 1.0 is cut unflipped), and gate teeth, changing zero
behaviour today.

## How

- **Good:** post-flip, a bundle `v3 -> v4` bump lands the raw-mapping upgrader in
  `BUNDLE_PAYLOAD_UPGRADERS`, a committed `v3` serialized fixture, and a test loading the
  `v3` bytes through the real deserialize path asserting strict equality — all one commit;
  a new persisted format enrolls its floor/version + an (empty) upgrader registry + its
  lineage gate at birth, in both regimes.
- **Bad:** post-flip, raising any durability floor above its released value to dodge writing
  an upgrader (the frozen-floor gate refuses it); flipping `COMPATIBILITY_REGIME` back to
  `PRE_RELEASE`, reading the regime from `Settings`/env, or loosening a persisted read model
  to `extra="ignore"` instead of versioning the shape.
- **Bad:** fabricating an old-version fixture or a real upgrader BEFORE a genuine
  post-checkpoint bump needs it — `no-legacy-compatibility` forbids inventing shapes nothing
  wrote; the harness ships empty and vacuous until then.

## Source

ADR `2026-07-09-compatibility-lifecycle-adr` (resolving `2026-07-08-released-data-durability-adr`).
Companion: `no-legacy-compatibility`, `aeat-schema-central-config`,
`sensitive-financial-data-secure-storage-only`. Enforced by the regime-aware lineage gates
and `test_compatibility_lifecycle_gate` (version tripwire + one-way coherence + enrollment).
