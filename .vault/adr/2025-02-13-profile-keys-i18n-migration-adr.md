---
tags:
  - '#adr'
  - '#profile-keys-i18n-migration'
date: '2025-02-13'
modified: '2025-02-13'
related:
  - '[[2025-02-13-profile-keys-i18n-migration-exec]]'
  - '[[2026-04-12-trilingual-i18n-research]]'
  - '[[2026-05-12-schema-driven-wizard-research]]'
  - '[[2026-06-04-profile-keys-i18n-migration-research]]'
---

# `profile-keys-i18n-migration` adr

## Context

The profile-key execution record moved user-facing key descriptions out of
hardcoded Python values and into the locale catalogs. That change is small
but architectural: it decides whether descriptive copy belongs to the key
registry or to the translation system.

## Decision

- Keep profile-key identifiers and structural metadata in Python, but move
  human-facing descriptions into the locale catalogs.
- Update the profile-key registry helpers to stop carrying per-locale copy
  inline.
- Back the migration with direct tests of the key registry surface after
  the refactor.

## Consequences

- Profile-key copy is translated through the same mechanism as the rest of
  the operator surface.
- The key registry remains structural instead of becoming a parallel i18n
  store.
- Future description updates can land in locale catalogs without touching
  domain identifiers.
