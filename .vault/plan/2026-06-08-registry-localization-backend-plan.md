---
tags:
  - '#plan'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
tier: L2
related:
  - '[[2026-06-08-registry-localization-backend-adr]]'
  - '[[2026-06-08-registry-localization-backend-research]]'
---


# `registry-localization-backend` `schema localization support implementation plan` plan

### Phase `P01` - research and architectural decisions

Research the existing schema structures and draft a binding ADR defining the localization extension strategy

- [x] `P01.S01` - Research schema structures and localization files; `src/aeat/domain/calculations/registry/`.
- [x] `P01.S02` - Draft the ADR defining the architecture for translatable schema metadata; `.vault/adr/2026-06-08-registry-localization-backend-adr.md`.

### Phase `P02` - backend data backfill of manuals

Backfill missing Renta and IVA manual handbooks under `src/aeat/_data/corpus/manuals/` and extract their structure to complete the legal referencing pipeline.

- [x] `P02.S03` - Backfill missing years/parts for Renta manual PDFs and metadata; `src/aeat/_data/corpus/manuals/renta/`.
- [x] `P02.S04` - Backfill missing years/parts for IVA manual PDFs and metadata; `src/aeat/_data/corpus/manuals/iva/`.
- [x] `P02.S11` - Generate structured `chapters.json` and `sections/` for backfilled manuals to transition out of degraded mode; `src/aeat/_data/corpus/manuals/`.

### Phase `P03` - schema localization backend implementation

Extend the registry compiler and data schema to support translatable help text and invariant localization values.

- [x] `P03.S05` - Extend `CasillaDefinition` and models with read-only `localized_labels` and `localized_help` dictionaries; `src/aeat/domain/calculations/registry/_schema_surfaces.py`.
- [x] `P03.S06` - Update loader to bypass `locales/` subdirectories during fragment discovery, parse hierarchical TOML translations, and perform strict schema validation; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `P03.S07` - Add unit and roundtrip tests for schema localization attributes; `src/aeat/domain/calculations/registry/tests/`.

### Phase `P04` - locale extensions and translation rollout

Author localized help files and roll out translations mapping translatable string notations to schema invariants.

- [x] `P04.S08` - Create local translation files under model-level and revision-level locales folders; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P04.S09` - Update CLI command handlers to display localized labels and help texts; `src/aeat/entrypoints/cli/`.
- [x] `P04.S10` - Add dedicated `test_registry_locales_parity.py` and verify end-to-end integration; `src/aeat/domain/calculations/registry/tests/`.

### Phase `P05` - historical Renta manuals structure backfill

Generate structured chapter and section layouts for Renta years 2020 through 2024 to transition them out of degraded mode.

- [x] `P05.S12` - Generate structured chapters.json and sections/ for Renta 2020 through 2024; `src/aeat/_data/corpus/manuals/renta/`.
- [x] `P05.S13` - Verify that all years 2020-2024 report structure_available: True; `src/aeat/_data/corpus/manuals/renta/`.

### Phase `P06` - historical IVA manuals backfill

Fetch and backfill IVA manual PDFs and structures for years 2020 through 2024.

- [x] `P06.S14` - Fetch historical IVA manual PDFs and verify manifest checksums; `src/aeat/_data/corpus/manuals/iva/`.
- [x] `P06.S15` - Generate structured chapters.json and sections/ for historical IVA manuals; `src/aeat/_data/corpus/manuals/iva/`.

### Phase `P07` - cross-reference registry verification

Implement compile-time validation to verify registry citations resolve against manual section structures.

- [x] `P07.S16` - Extend registry compile-time validator to check manuals cross-references; `src/aeat/domain/calculations/registry/`.
- [x] `P07.S17` - Write integration tests asserting reference validation failures on invalid citations; `src/aeat/domain/calculations/registry/tests/`.

### Phase `P08` - translation rollout

Roll out localized help text configurations for other major models.

- [x] `P08.S18` - Map localized labels and help text files for Modelo 100, Modelo 200, and Modelo 303; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P08.S19` - Assert localized parity verification passes for newly added revision packages; `src/aeat/domain/calculations/registry/tests/test_registry_locales_parity.py`.

### Phase `P09` - historical Renta Part 2 manuals backfill

Fetch and backfill structured directories and manifest files for Renta Part 2 (Deducciones Autonómicas) for years 2020 through 2024.

- [x] `P09.S20` - Add PartSpec configurations and fetch Renta Part 2 PDFs and manifests for 2020-2024; `src/aeat/domain/manuals/_fetch.py`.
- [x] `P09.S21` - Generate structured chapter and section layouts for historical Renta Part 2 manuals; `src/aeat/_data/corpus/manuals/renta/`.
- [x] `P09.S22` - Verify that Renta Part 2 manuals view for all years 2020-2024 reports structure_available: True; `src/aeat/_data/corpus/manuals/renta/`.


## Description

This plan defines the engineering steps to design and implement translation and localization support directly in the model schema registry backend. This allows localizing both invariant labels and helper/hint texts while preserving the integrity of official Spanish labels. It also outlines the backfill of missing Renta and IVA manuals under `src/aeat/_data/corpus/manuals/` and their structure extraction to complete the legal referencing pipeline.

In the extended phases, we expand the backfill to all historical manuals (Renta 2020-2024 and IVA 2020-2024, including Part 2 Deducciones Autonómicas for Renta) to transition them out of degraded mode, implement compile-time schema validation ensuring manuals citations are structurally valid, and roll out localized translations for other major model files.

## Parallelization

* Phase `P01` (Research and ADR) must be executed sequentially first.
* Phase `P02` (Backend data backfill) and Phase `P03` (Schema localization backend implementation) can run concurrently.
* Phase `P04` (Locale extensions and rollout) depends on both `P02` and `P03`.
* Phase `P05` (Historical Renta backfill), Phase `P06` (Historical IVA backfill), and Phase `P09` (Historical Renta Part 2 backfill) depend on Phase `P02` structures and can run concurrently.
* Phase `P07` (Cross-reference validation) depends on Phase `P05`, Phase `P06`, and Phase `P09` structure layouts being fully generated.
* Phase `P08` (Translation rollout) can run concurrently with Phase `P07`.

## Verification

* The ADR `2026-06-08-registry-localization-backend-adr.md` is fully defined and accepted.
* The manuals PDFs, manifests, and extracted structures under `src/aeat/_data/corpus/manuals/` are present and verify cleanly for all years 2020-2025 (Renta Part 1 & Part 2, and IVA).
* All unit, validation, and roundtrip tests for schema localization attributes pass.
* The dedicated `test_registry_locales_parity.py` runs successfully across all active modelos, and the main locales parity gates (`test_parity.py` and `test_locale_translation_honesty.py`) stay green.
* Registry compile-time validator strictly raises validation errors if any casilla `legal_refs` or `source_refs` fail to resolve to a valid manual section.
