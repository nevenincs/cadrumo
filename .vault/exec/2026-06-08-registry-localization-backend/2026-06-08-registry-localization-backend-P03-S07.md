---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P03.S07` execution record

Add unit and roundtrip tests for schema localization attributes.

## Action

Create a new test file `src/aeat/domain/calculations/registry/tests/test_registry_locales_loader.py` that verifies:
1. Localized labels and help texts are correctly compiled and attached to `CasillaDefinition` under both concept-continuity (modelo locales) and revision-local overrides.
2. Invalidation logic triggers correct caching/re-loading when locales files change.
3. Strict referential integrity validation: raising `RegistryValidationError` when translation keys contain unknown `casilla_id` or `continuidad_id`.
4. Serialization and deserialization (roundtrip) of localization attributes via Pydantic model serialization.

## Verification

Run pytest on the newly created test module and ensure all test cases pass.
