---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P03.S06` execution record

Update loader to bypass `locales/` subdirectories during fragment discovery, parse hierarchical TOML translations, and perform strict schema validation.

## Action

1. Excluded `locales/` paths from recursive fragment TOML discovery in `_merge_revision_directory` and `_discover_revision_sources` under `src/aeat/domain/calculations/registry/_loader.py`.
2. Implemented hierarchical translation file parsing from `modelos/<modelo>/locales/<locale>.toml` and `revisions/<revision>/locales/<locale>.toml`.
3. Validated translation keys against the schema elements (continuity IDs and casilla IDs) using strict Pydantic schemas, raising `RegistryValidationError` on mismatch.
4. Attached localized values to `localized_labels` and `localized_help` on `CasillaDefinition` raw payload prior to validation.

## Verification

Run unit/integration tests on schema compilation and verify locales loading behaviors.
