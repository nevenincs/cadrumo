---
name: no-legacy-compatibility
trigger: always_on
---

# No legacy or backwards-compatibility support

This project has no released data and no deployed callers. Carry ZERO legacy
code: no migration of old on-disk formats, no read-tolerance of pre-current data
shapes, no deprecated aliases, no retired-field handling, no version-upgrade
ALTER passes, no coercion branches for old serialised records. When a format,
schema, key derivation, or API shape changes, **DELETE the old surface and its
tests outright** — never add a bridge, fallback, or shim to read what an earlier
version of THIS app wrote.

Every migration pass and read-tolerance branch obscures the canonical flow and
defends behaviour no caller needs. This is the deletion-side companion to
`aeat-architecture-boundaries`, which forbids *introducing* shims.

## Distinctions, each normative

- **Delete, do not bridge.** Delete a from-birth migration module, its bootstrap
  call site, and its harness — do not refactor it.
- **Refuse, do not tolerate.** A read path for a written-from-birth envelope,
  prefix or typed shape RAISES on a missing prefix (that is corruption now) and
  never silently returns the raw legacy form.
- **CREATE is not migration; keep it.** Fresh-schema bootstrap that materialises
  the current shape on first access is forward-functional; an ALTER pass
  upgrading an OLDER table is legacy.
- **External-world variability is not our legacy; keep it.** Resilience for AEAT
  portal variations, BOE corpus formats, PDF producer quirks, and AEAT regulatory
  revisions — each modelo revision year is CURRENT law for its filing year.
- **AEAT regulatory status is never CODE legacy.** A real modelo AEAT still
  supports is a current product feature. Only delete a surface that exists to
  read or migrate data an OLDER VERSION OF THIS APP wrote.
- **A forward version FIELD is not legacy; keep it.** A `schema_version` marker or
  a `max_supported_version` ceiling refusing a FUTURE shape is
  forward-compatibility. Only code that BRANCHES on an OLD version is legacy.
- **Key-management caution:** deleting a key-schedule or DEK-derivation branch can
  strand encrypted data. Confirm the creation path mints only the current schedule
  first — owner-gated, not autonomous.

## The regime is a one-way core constant

The persisted-data compatibility posture is governed by
`cadrumo.core.COMPATIBILITY_REGIME`, flipped `PRE_RELEASE -> RELEASED` **only** by
an accepted checkpoint ADR whose same commit freezes
`cadrumo.core.RELEASED_FORMAT_FLOORS` at the then-current per-format durability
floors. The regime MUST NOT be read from `Settings` or the environment, and the
enforcing gates MUST NOT be skipped, weakened, or monkeypatched. A runtime flag
can differ per machine and be patched in its own gate; a repo-committed constant
has a conscious owner, a version-milestone tripwire, and gate teeth.

**Pre-checkpoint (today):** everything above governs unchanged — delete not
migrate, floors may chase the current version, no read-tolerance of pre-current
shapes.

**Post-checkpoint:** for every persisted format the durability floor is FROZEN at
its released value; every version bump MUST land, in the same commit, its one-hop
upgrader (for the archive tier, a version-aware reader), a committed pre-bump
serialized fixture, and a restorability test loading the old bytes through the
real production read path. Strict persisted-read models stay `extra="forbid"`
with the pre-validation upgrade hop as the ONLY sanctioned tolerance point, and a
persisted-model shape change rides a version bump plus upgrader, never a loosened
model. This rule then narrows to "no legacy beyond the released floor" —
read-tolerance of shapes nothing released wrote, and shims and aliases, stay
forbidden in both regimes.

Installing the dormant regime constant, the empty upgrader registries, and the
regime-aware gates does not violate this rule: they read no old shapes and
migrate nothing.

## How

- **Bad, post-flip:** raising any durability floor above its released value to
  dodge writing an upgrader; flipping the regime back; reading it from settings;
  or loosening a persisted read model instead of versioning the shape.
- **Bad, either regime:** fabricating an old-version fixture or upgrader before a
  genuine post-checkpoint bump needs one — that invents shapes nothing wrote.

Source: ADRs `2026-07-09-compatibility-lifecycle-adr`,
`2026-07-08-released-data-durability-adr`; inventory
`2026-06-10-zero-legacy-purge-research`. Enforced by the regime-aware lineage
gates and `test_compatibility_lifecycle_gate`.
