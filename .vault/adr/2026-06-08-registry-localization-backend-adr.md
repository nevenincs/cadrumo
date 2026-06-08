---
tags:
  - '#adr'
  - '#registry-localization-backend'
date: '2026-06-08'
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

1. **Schema Extension**: Modify `CasillaDefinition` to carry optional `localized_label` and `localized_help` fields, or support translatable key string notations (e.g. `tr()`) that are resolved at load time.
2. **Model-Local Locales**: Place localized string catalogues in subdirectory namespaces under each modelo revision folder, for example `src/aeat/_data/registry/aeat/modelos/<modelo>/locales/<locale>.toml` (or `.json`).
3. **Lazy Registry Compilation**: The `ValidatedRegistryAuthority` compiler will load these registry-specific locales dynamically when the corresponding `ModeloRevision` snapshot is compiled, avoiding eager core locales bloat.
4. **CLI Handler Resolution**: Update the discover/describe CLI command outputs to format and print localized labels and hints based on the active session's language.

## Rationale

This decision is backed by the `2026-06-08-registry-localization-backend-research` findings. Eagerly loading 61k+ string combinations in the main application locale files would bloat startup times, whereas lazy-loading model-local files preserves both the regulatory Spanish invariants and UI flexibility with zero CLI bootstrap overhead.

## Consequences

* **Gains**: Allows translation-ready help text and labels for 15,291 casillas without affecting startup latency; keeps core YAML catalogues thin.
* **Difficulties**: Requires maintaining parity between registry casilla IDs and their corresponding model-local translation files.

## Codification candidates

None.
