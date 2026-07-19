---
name: no-legacy-compatibility
trigger: always_on
---

# No legacy or backwards-compatibility support

## Rule

This is an unreleased pre-beta project with no released data and no deployed
callers. Carry ZERO legacy code: no migration of old on-disk formats, no
read-tolerance of pre-current data shapes, no deprecated aliases, no retired
field handling, no version-upgrade ALTER passes, no "old serialised record"
coercion branches. When a format, schema, key derivation, or API shape changes,
DELETE the old surface and its tests outright — never add a bridge, fallback,
or compatibility shim to read what an earlier version of THIS app wrote. The
canonical state is the only state; old is deleted, not maintained.

## Why

Per operator directive 2026-06-10 (backing inventory
`2026-06-10-zero-legacy-purge-research`): no released version's data must survive an
upgrade, so every migration pass, read-tolerance branch, and "legacy path" is dead
weight that obscures the canonical flow and defends behaviour no caller needs. This
is the deletion-side companion to `aeat-architecture-boundaries` (which forbids
INTRODUCING shims); this one mandates REMOVING legacy surfaces that already exist.

## How

Keep/delete distinctions (each normative):

- **Delete, do not bridge.** Delete a from-birth deterministic-key migration
  module, its bootstrap call site, and harness — do not refactor it.
- **Refuse, do not tolerate.** A read path for a written-from-birth
  envelope/prefix/typed shape RAISES on a missing prefix (corruption now), never
  silently returns the raw legacy form.
- **CREATE is not migration — keep it.** Fresh-schema CREATE/bootstrap that
  materialises the current shape on first access is forward-functional; an ALTER
  pass upgrading an OLDER table is legacy — delete it.
- **External-world variability is not our legacy — keep it.** Resilience for AEAT
  portal variations, BOE corpus formats, PDF producer quirks, and AEAT regulatory
  revisions (each modelo revision year is CURRENT law for its filing year).
- **AEAT regulatory status is never CODE legacy — never conflate.** A real modelo
  still supported (e.g. `Modelo.M037`) is a CURRENT product feature. Only delete a
  surface that exists to read or migrate data an OLDER VERSION OF THIS APP wrote.
- **A forward version FIELD is not legacy — keep it.** A `schema_version` marker or
  a `max_supported_version` ceiling that refuses a FUTURE shape is
  forward-compatibility; only code that BRANCHES on an OLD version is legacy.
- **Bad:** `if payload is None: payload = load(_legacy_cleartext_key(...))` (a read
  fallback for pre-hardening records that cannot exist), or an `ensure_*_columns`
  ALTER loop adding today's columns to a table an older version CREATEd — delete both.
- **Key-management caution:** deleting a key-schedule / DEK-derivation branch can
  strand encrypted data; confirm the creation path mints only the current schedule
  before deleting an "old" one — owner-gated, not autonomous.

## Source

Operator directive 2026-06-10 (`chore/eliminate-shims`); inventory
`2026-06-10-zero-legacy-purge-research`. Companion: `aeat-architecture-boundaries`.

## Status

Active and unchanged for the pre-release regime, governing in full while
`cadrumo.core.COMPATIBILITY_REGIME` is `PRE_RELEASE`: delete-not-migrate, floors
chase current, no read-tolerance of pre-current shapes. The transition to the
post-release regime is governed by `compatibility-lifecycle-checkpoint` (ADR
`2026-07-09-compatibility-lifecycle-adr`), switched on the one-way
`COMPATIBILITY_REGIME` constant. At the flip this rule narrows to "no legacy beyond
the released durability floor": read-tolerance of shapes nothing released wrote, and
shims/aliases, stay forbidden in both regimes. Installing the dormant regime
constant, empty upgrader registries, and the regime-aware gates does not violate
this rule — they read no old shapes and migrate nothing (same blessed category as
the `max_supported_version` forward-ceiling this rule keeps).
