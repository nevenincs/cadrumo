---
tags:
  - '#plan'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
tier: L2
related:
  - '[[2026-09-10-sociedades-manual-coverage-coverage-contract-adr]]'
  - '[[2026-09-10-sociedades-manual-coverage-temporal-coverage-research]]'
modified: '2026-09-10'
body_schema: body-v2
body_hash: 'sha256:e450a9a204e8fccbf2339e7346d102762806432e6e3b8085b117ea1ec450f8fa'
---

<!-- RETIRED: S11 -->

# `sociedades-manual-coverage` plan

Make the bundled Sociedades manuals complete and explicit for the canonical 2022-2026 filing-year horizon without extending Modelo 200 authority.

## Description

This plan implements the accepted annual-manual coverage decision. The first phase establishes the data contract and its localized operator projection. The second acquires the two published missing years, records their exact authority windows, and removes cross-year manual citations from Modelo 200 dispositions without widening that model's authority. The final phase replaces development-only exceptions with a contract gate and regenerates the documentation-search projections from the live command graph.

## Steps

### Phase `P01` - Declare annual-manual coverage

Make every supported Sociedades year observable as published evidence or an explicitly re-checkable publication absence.

- [x] `P01.S01` - Introduce the typed Sociedades annual-manual coverage catalogue and validate its exact-year dispositions; `src/cadrumo/_data/registry/aeat/legal`.
- [x] `P01.S02` - Project covered, unacquired, and unpublished annual-manual states from the catalogue; `src/cadrumo/application/registry/corpus.py`.
- [x] `P01.S03` - Carry annual-manual coverage state through the stable CLI output contract; `src/cadrumo/entrypoints/cli`.
- [x] `P01.S04` - Localize Cadrumo-owned annual-manual coverage labels and status messages; `src/cadrumo/locales`.

### Phase `P02` - Ground and ship annual evidence

Acquire missing official annual material, bind it to its exact source window, and retain the independent Modelo 200 authority boundary.

- [x] `P02.S05` - Acquire and extract the official 2022 and 2023 Sociedades manual artefacts with provenance sidecars; `src/cadrumo/_data/corpus/manuals/sociedades`.
- [x] `P02.S06` - Enroll annual Sociedades sources in the legal registry with year-bounded applicability; `src/cadrumo/_data/registry/aeat/legal/is.toml`.
- [x] `P02.S07` - Narrow Modelo 200 family evidence references so annual manuals never ground an out-of-window year; `src/cadrumo/_data/registry/aeat/modelos/200/revisions`.

### Phase `P03` - Expose and verify the repaired boundary

Project the coverage result through the localized operator and generated documentation surfaces, then prove the package and search corpus remain coherent.

- [x] `P03.S08` - Replace Sociedades standing acquisition exceptions with catalogue-driven temporal coverage tests; `dev/corpus/tests/test_extraction_sidecar_freshness.py`.
- [x] `P03.S09` - Regenerate the CLI reference and Pagefind inputs from the live localized command graph; `dev/docs`.
- [x] `P03.S10` - Verify companion-package inclusion and the manual operator surface across the supported horizon; `packaging/cadrumo_data_manuals`.

## Parallelization

`P01.S01` precedes the operator, CLI, locale, and test projections. `P02.S05` must finish before source enrolment and the extraction freshness gate. `P02.S06` and `P02.S07` may proceed in parallel after the source catalogue shape is fixed. Documentation regeneration follows the CLI contract change. Packaging verification is last because it validates the assembled shipped surface.

## Verification

The plan is complete when the annual catalogue resolves every supported Sociedades year to either a verified local source within its own applicability interval or a dated official unpublished disposition; the 2022 and 2023 PDFs and corpus-text sidecars pass extraction freshness; the manual CLI renders all states in every output language; Modelo 200 does not cite annual manual evidence outside its year; generated CLI reference and Pagefind records agree with the live command graph; the manuals companion package contains the added PDFs; and focused unit, integration, corpus, documentation, and packaging checks pass.
