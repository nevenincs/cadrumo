---
tags:
  - '#reference'
  - '#compatibility-lifecycle'
date: '2026-07-10'
modified: '2026-07-10'
related:
  - "[[2026-07-09-compatibility-lifecycle-adr]]"
---

# `compatibility-lifecycle` reference: `release-checkpoint flip checklist`

## Summary

The mechanical spec for the ONE remaining compatibility-lifecycle action — the release
checkpoint flip — and the two honesty-review LOW findings whose enforcement is
deliberately deferred to it. The dormant mechanism (ADR `2026-07-09-compatibility-lifecycle-adr`,
commits `ffb2f94605` / `0a3367f56d` / `4f521273d2`) is live today; this document makes the
flip a mechanical, gate-verified change so nothing is left ambiguous. Every item below is
FORBIDDEN to build before the flip: writing an upgrader/reader/fixture for a version that
does not yet exist would fabricate enforcement for a flip that has not happened, violating
`no-legacy-compatibility` — the same reason the dormant mechanism ships inert. The gates
force each item at the flip; this checklist names them.

### When: the trigger

Flip at the first release that can put a real taxpayer's persisted data outside the dev
team — operationally the 1.0 cut. The tripwire
`test_pre_release_regime_keeps_the_package_below_the_one_point_zero_milestone`
(`src/aeat/tests/test_compatibility_lifecycle_gate.py`) reds CI if a 1.0 is cut while the
regime is still `PRE_RELEASE`. Flipping earlier is permitted by making the flip commit.

### The flip commit (single, ADR-gated)

1. Set `COMPATIBILITY_REGIME = CompatibilityRegime.RELEASED` in
   `src/aeat/core/compatibility_lifecycle.py`.
2. Populate `RELEASED_FORMAT_FLOORS` with the then-current per-format versions (today's
   values: `{"secure_object": 1, "bundle": 3, "archive": 2}` — re-read them at flip from
   the tier constants, do not trust this snapshot).
3. Populate `_RELEASED_FORMAT_CURRENT_VERSIONS` (`test_compatibility_lifecycle_gate.py`)
   with the SAME keys — the coherence gate `test_every_flip_time_constant_moves_together`
   (added in `4f521273d2`) refuses a flip that populates one map but not the other.
4. Land an accepted release-checkpoint ADR (supersedes/extends
   `2026-07-09-compatibility-lifecycle-adr`).
5. Run the full lineage + compat suite: the three tier floor gates now assert floor-freeze
   (`floor == RELEASED_FORMAT_FLOORS[key]`), and the central coherence/enrollment/coverage
   gates activate. All must be green with the frozen floors before the release is cut.

### Addressing honesty-review LOW #1 — wire the upgrader arm to live state

The predicate `lineage_obligations`'s `missing_upgraders` axis is proven correct
synthetically (`src/aeat/core/tests/test_compatibility_lifecycle.py`) but is not driven by a
live gate today — the central coverage gate passes `has_registered_upgraders_for_gap=True`
because that axis is not the corpus gate's. INTERIM enforcement is already live and must be
kept: the pre-existing chain-completeness tests cover `range(floor, current)` per format —
`test_every_registered_namespace_upgrade_chain_is_complete` (secure-object),
`test_bundle_upgrade_chain_is_complete_from_floor_to_current` (bundle), and the archive
importable-range test. AT FLIP (and at each later post-floor bump): register the one-hop
upgrader (`register_secure_object_schema_upgrader` / `BUNDLE_PAYLOAD_UPGRADERS`) for the new
gap in the same commit as the version bump; the chain tests then red until it exists. No
change is needed to the dormant mechanism to make this enforceable — the chain tests are the
gate; the predicate axis is the policy definition the flip narrative cites.

### Addressing honesty-review LOW #2 — archive restorability test

The archive tier has no dispatch registry, so no chain gate structurally proves a
version-aware `read_sealed_archive` reader exists. The companion rule
`compatibility-lifecycle-checkpoint` mandates the enforcement instead: any post-flip archive
version bump MUST, in the same commit, add the version-aware reader AND a hand-written
restorability test that seals a real prior-version archive and restores it through the
production `bucket_maintenance` import path (asserting strict-equality reconstitution).
Until such a bump, `_ARCHIVE_DURABILITY_FLOOR == _ARCHIVE_SCHEMA_VERSION` holds (nothing to
restore). This test CANNOT be written before the flip without fabricating a shape nothing
released wrote (a `no-legacy-compatibility` violation), which is exactly why it is a
flip-commit deliverable, not a today-item.

### Per-bump discipline (post-flip, recurring)

Every persisted-format version bump after the flip lands, in one commit: the one-hop
upgrader (archive: the version-aware reader), a committed pre-bump serialized fixture under
`src/aeat/_data/compat_fixtures/<format>/`, and a restorability test loading the old bytes
through the real read path. The floor stays frozen; the coverage gate (keyed off
`lineage_obligations`) reds until the fixture exists. This is the durability contract the
whole mechanism exists to force.
