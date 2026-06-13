---
tags:
  - '#adr'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - "[[2026-06-08-registry-localization-backend-research]]"
---



# `registry-localization-backend` adr: `schema localization support architecture` | (**status:** `accepted`)

## Problem Statement

Casilla labels are currently hardcoded in Spanish within the registry TOML files to satisfy the regulatory layout requirements of the AEAT. However, this conflation of data structure and presentation makes it difficult to localize helper/hint texts or labels for multilingual operator interfaces. At the same time, eagerly loading 15,291 Casilla labels in the core locales YAML files on CLI startup would introduce unacceptable performance latency. This ADR defines the architecture for lazy-loaded schema-local translations.

## Considerations

* Official Spanish labels are regulatory invariants and must remain accessible to workbook export engines.
* The operator interface supports localization into English (`en`), Catalan (`ca`), and Hungarian (`hu`).
* Core locales (`src/aeat/locales/`) must remain lightweight (~300KB) to ensure sub-second CLI startup.

## Constraints

* This architecture must not break existing workbook layout parity or validation rules.
* Model-local translations must not be loaded eagerly on CLI start; they must be parsed on demand during `ValidatedRegistryAuthority` loading.

## Implementation

1. **Schema Extension**: Modify `CasillaDefinition` in `src/aeat/domain/calculations/registry/_schema_surfaces.py` to carry `localized_labels: dict[str, str] = Field(default_factory=dict)` and `localized_help: dict[str, str] = Field(default_factory=dict)` fields. Keep `label` as the official Spanish invariant, accessible to export engines and validation rules.
2. **Model-Local Locales**: Place localized catalogues as `.toml` files under `revisions/<revision>/locales/<locale>.toml` (for revision-specific overrides matching `casilla_id`) and `modelos/<modelo>/locales/<locale>.toml` (for stable concept-level mappings matching `continuidad_id`).
3. **Lazy Registry Compilation**: The compiler in `src/aeat/domain/calculations/registry/_loader.py` must filter out any files under `locales/` subdirectories during recursive TOML fragment discovery (`_merge_revision_directory`) to prevent parsing them as schema/calculation fragments. However, these files must remain in `_modelo_directory_fingerprints` to trigger cache invalidation.
4. **Hardened Validation**: Introduce strict pydantic schemas for localization TOML files. Validate them at snapshot compile time to ensure referential integrity (every translated key corresponds to a valid `casilla_id` or `continuidad_id`), raising a `RegistryValidationError` on mismatch to prevent database pollution.
5. **UI Rendering**: During `registry_casillas` query or CLI rendering, resolve the active translation key using `casilla.localized_labels.get(locale, casilla.label)`.

## Rationale

This decision is backed by the `2026-06-08-registry-localization-backend-research` findings and operator directive. Eagerly loading 61k+ string combinations in the main application locale files would bloat startup times, whereas lazy-loading model-local files preserves both the regulatory Spanish invariants and UI flexibility with zero CLI bootstrap overhead. Skipping locales in recursive fragment compilation prevents parsing crashes while keeping their filesystem changes tracked for cache invalidation.

## Consequences

* **Gains**: Allows translation-ready help text and labels for 15,291 casillas without affecting startup latency; keeps core YAML catalogues thin; resolves changing descriptions cleanly across revisions.
* **Difficulties**: Requires maintaining parity between registry casilla IDs and their corresponding model-local translation files.
* **Mitigations**: Hardened schema-level validation at compile time blocks non-conformant or broken files from polluting the loading schema.

## Codification candidates

None.

