---
name: no-legacy-compatibility
trigger: always_on
---

# No legacy or backwards-compatibility support

## Rule

This project has no released data and no deployed callers. Carry ZERO legacy
code: no migration of old on-disk formats, no read-tolerance of pre-current data
shapes, no deprecated aliases, no retired-field handling, no version-upgrade
ALTER passes, no coercion branches for old serialised records. When a format,
schema, key derivation, or API shape changes, **DELETE the old surface and its
tests outright** — never add a bridge, fallback, or compatibility shim to read
what an earlier version of THIS app wrote. The canonical state is the only
state.

## Why

No released version's data must survive an upgrade, so every migration pass,
read-tolerance branch, and legacy path is dead weight that obscures the
canonical flow and defends behaviour no caller needs. This is the deletion-side
companion to `aeat-architecture-boundaries`, which forbids *introducing* shims;
this one mandates *removing* the legacy surfaces that already exist.

## How

Each distinction below is normative.

- **Delete, do not bridge.** Delete a from-birth deterministic-key migration
  module, its bootstrap call site, and its harness — do not refactor it.
- **Refuse, do not tolerate.** A read path for a written-from-birth envelope,
  prefix, or typed shape RAISES on a missing prefix — that is corruption now —
  and never silently returns the raw legacy form.
- **CREATE is not migration; keep it.** Fresh-schema CREATE or bootstrap that
  materialises the current shape on first access is forward-functional. An ALTER
  pass upgrading an OLDER table is legacy — delete it.
- **External-world variability is not our legacy; keep it.** Resilience for AEAT
  portal variations, BOE corpus formats, PDF producer quirks, and AEAT
  regulatory revisions — each modelo revision year is CURRENT law for its filing
  year.
- **AEAT regulatory status is never CODE legacy.** A real modelo still supported
  by AEAT is a current product feature. Only delete a surface that exists to
  read or migrate data an OLDER VERSION OF THIS APP wrote.
- **A forward version FIELD is not legacy; keep it.** A `schema_version` marker
  or a `max_supported_version` ceiling that refuses a FUTURE shape is
  forward-compatibility. Only code that BRANCHES on an OLD version is legacy.
- **Bad:** a read fallback to a pre-hardening key for records that cannot exist;
  an `ensure_*_columns` ALTER loop adding today's columns to a table an older
  version created.
- **Key-management caution:** deleting a key-schedule or DEK-derivation branch
  can strand encrypted data. Confirm the creation path mints only the current
  schedule before deleting an "old" one — owner-gated, not autonomous.

## Scope

This rule governs in full while `cadrumo.core.COMPATIBILITY_REGIME` is
`PRE_RELEASE`. `compatibility-lifecycle-checkpoint` governs the one-way
transition. At that flip this rule **narrows** to "no legacy beyond the released
durability floor" — read-tolerance of shapes nothing released wrote, and shims
and aliases, stay forbidden in both regimes. Installing the dormant regime
constant, the empty upgrader registries, and the regime-aware gates does not
violate this rule: they read no old shapes and migrate nothing, the same blessed
category as the forward version ceiling above.

## Source

Operator directive; inventory `2026-06-10-zero-legacy-purge-research`.
Companions: `aeat-architecture-boundaries`,
`compatibility-lifecycle-checkpoint`.
