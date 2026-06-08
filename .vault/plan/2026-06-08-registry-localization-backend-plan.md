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



- [ ] `P01.S01` - Research schema structures and localization files; `src/aeat/domain/calculations/registry/`.
- [ ] `P01.S02` - Draft the ADR defining the architecture for translatable schema metadata; `.vault/adr/2026-06-08-registry-localization-backend-adr.md`.

### Phase `P02` - backend data backfill of manuals

Backfill missing Renta and IVA manual handbooks under src/aeat/_data/corpus/manuals/ to complete the legal referencing pipeline.

- [ ] `P02.S03` - Backfill missing years/parts for Renta manual PDFs and metadata; `src/aeat/_data/corpus/manuals/renta/`.
- [ ] `P02.S04` - Backfill missing years/parts for IVA manual PDFs and metadata; `src/aeat/_data/corpus/manuals/iva/`.

### Phase `P03` - schema localization backend implementation

Extend the registry compiler and data schema to support translatable help text and invariant localization values.

- [ ] `P03.S05` - Extend CasillaDefinition and models with localization properties; `src/aeat/domain/calculations/registry/_schema_surfaces.py`.
- [ ] `P03.S06` - Update registry compiler to support translatable string notations; `src/aeat/domain/calculations/registry/_loader.py`.
- [ ] `P03.S07` - Add unit and roundtrip tests for schema localization attributes; `src/aeat/domain/calculations/registry/tests/`.

### Phase `P04` - locale extensions and translation rollout

Author localized help files and roll out translations mapping translatable string notations to schema invariants.

- [ ] `P04.S08` - Create localization files extensions for the existing TOML schemas; `src/aeat/locales/`.
- [ ] `P04.S09` - Update CLI command handlers to display localized help texts; `src/aeat/entrypoints/cli/`.
- [ ] `P04.S10` - Verify end-to-end integration and run validation tests; `src/aeat/tests/`.

## Description

This plan defines the engineering steps to design and implement translation and localization support directly in the model schema registry backend. This allows localizing both invariant labels and helper/hint texts while preserving the integrity of official Spanish labels. It also outlines the backfill of missing Renta and IVA manuals under `src/aeat/_data/corpus/manuals/` to complete the legal referencing pipeline.

## Parallelization

* Phase `P01` (Research and ADR) must be executed sequentially first.
* Phase `P02` (Backend data backfill) and Phase `P03` (Schema localization backend implementation) can run concurrently.
* Phase `P04` (Locale extensions and rollout) depends on both `P02` and `P03` and must be executed last.

## Verification

* The ADR `2026-06-08-registry-localization-backend-adr.md` is fully defined and accepted.
* The missing manual PDFs and manifests under `src/aeat/_data/corpus/manuals/` are present and verify cleanly.
* All unit and roundtrip tests for schema localization attributes pass.
* The locales parity gates (`test_parity.py` and `test_locale_translation_honesty.py`) pass.
