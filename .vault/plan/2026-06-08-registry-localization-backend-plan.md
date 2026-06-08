---
tags:
  - '#plan'
  - '#registry-localization-backend'
date: '2026-06-08'
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
- [x] `P02.S11` - Generate structured `chapters.json` and `sections/` for backfilled manuals to transition out of degraded mode.

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

## Description

This plan defines the engineering steps to design and implement translation and localization support directly in the model schema registry backend. This allows localizing both invariant labels and helper/hint texts while preserving the integrity of official Spanish labels. It also outlines the backfill of missing Renta and IVA manuals under `src/aeat/_data/corpus/manuals/` and their structure extraction to complete the legal referencing pipeline.

## Parallelization

* Phase `P01` (Research and ADR) must be executed sequentially first.
* Phase `P02` (Backend data backfill) and Phase `P03` (Schema localization backend implementation) can run concurrently.
* Phase `P04` (Locale extensions and rollout) depends on both `P02` and `P03` and must be executed last.

## Verification

* The ADR `2026-06-08-registry-localization-backend-adr.md` is fully defined and accepted.
* The manuals PDFs, manifests, and extracted structures under `src/aeat/_data/corpus/manuals/` are present and verify cleanly.
* All unit, validation, and roundtrip tests for schema localization attributes pass.
* The dedicated `test_registry_locales_parity.py` runs successfully, and the main locales parity gates (`test_parity.py` and `test_locale_translation_honesty.py`) stay green.

