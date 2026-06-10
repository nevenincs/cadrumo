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

There is no released version whose data must survive an upgrade, so every
migration pass scans for rows that cannot exist, every read-tolerance branch
guards against a shape nothing writes, and every "legacy path" is dead weight
that obscures the canonical flow and accretes test surface defending behaviour
no caller needs. Operator directive recorded 2026-06-10: "we should NOT be
supporting any legacy migration, legacy schema, legacy, retired or old
backwards compatibility. Basically old is to be deleted, and we're working
towards the future with ZERO legacy code support. This is an unreleased
pre-beta project. There's no backwards looking functionality support to
carry." This rule is the deletion-side companion to the architecture-boundaries
rule (which forbids INTRODUCING shims and deprecation paths); this one mandates
REMOVING the legacy surfaces that already exist. The zero-legacy-purge research
inventory (`2026-06-10-zero-legacy-purge-research`) is the worked deletion
backlog.

## How

- **Delete, do not bridge.** A from-birth deterministic key schema needs no
  migration from a randomized-key past — delete the migration module, its
  bootstrap call site, and its harness, not refactor it.
- **Refuse, do not tolerate.** When an envelope/prefix/typed shape is written
  from birth, the read path strips it and RAISES on a missing prefix (it can
  only mean corruption now), never silently returns the raw legacy form.
- **CREATE is not migration — keep it.** Fresh-schema CREATE/bootstrap that
  materialises the current shape on first access is forward-functional. An
  ALTER pass that upgrades an OLDER table to the current shape is legacy —
  delete it.
- **External-world variability is not our legacy — keep it.** Resilience for
  AEAT portal variations, BOE corpus formats, third-party PDF producer quirks,
  and AEAT regulatory revisions (each modelo revision year is CURRENT law for
  its filing year) is forward function, not backwards compatibility.
- **AEAT regulatory status is never evidence of CODE legacy — never conflate
  the two.** "AEAT (the Spanish tax authority) retired or superseded a modelo,
  revision, or rate as a matter of policy" is orthogonal to "our code carries a
  backwards-compatibility shim." A real modelo the application supports (e.g.
  `Modelo.M037`, no longer in general use but still supported) is a CURRENT
  product feature, not legacy code — keep it. Only delete a surface when it
  exists to read or migrate data that an OLDER VERSION OF THIS APP wrote.
- **A forward version FIELD is not legacy — keep it.** A `schema_version`
  marker that lets a future version read today's records, or a
  `max_supported_version` ceiling that refuses a FUTURE shape, is
  forward-compatibility. Only code that BRANCHES on an OLD version is legacy.
- **Bad:** `if payload is None: payload = load(_legacy_cleartext_key(...))` —
  a read fallback under the current hardened key for pre-hardening records that
  cannot exist on an unreleased app. Delete the function and the fallback.
- **Bad:** an `ensure_*_columns` ALTER loop that adds today's columns to a
  table an older version CREATEd. Delete it; the CREATE already has them.
- **Key-management caution:** deleting a key-schedule or DEK-derivation branch
  on inference can strand encrypted data. Confirm the creation path mints only
  the current schedule before deleting an "old" one; this is the single place
  where a wrong deletion is unrecoverable, so it is owner-gated, not autonomous.

## Source

Operator directive recorded 2026-06-10 during the quality-hardening campaign on
the `chore/eliminate-shims` branch. Backing inventory:
`2026-06-10-zero-legacy-purge-research`. Companion rule:
`aeat-architecture-boundaries` (no new shims / deprecation paths).
