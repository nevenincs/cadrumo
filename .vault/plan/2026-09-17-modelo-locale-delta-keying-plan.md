---
tags:
  - '#plan'
  - '#modelo-locale-delta-keying'
date: '2026-09-17'
tier: L2
related:
  - '[[2026-09-17-modelo-locale-delta-keying-adr]]'
modified: '2026-09-17'
body_schema: body-v2
body_hash: 'sha256:13834e5a7babd3ae693ad1cbbcd2ba761ba9e8a82878055ba980a660f89edccd'
---

# `modelo-locale-delta-keying` plan

## Description

Approved 2026-09-17. Basis: operator directive in this session to collapse duplicated locale values, delete undeclared or unread duplicates, and author only genuinely unique locale data, mirroring registry delta keying.

Bring the Modelo locale catalogues to the registry's delta discipline and repair their content.

- Governing decision: `2026-09-17-modelo-locale-delta-keying-adr`, with evidence in `2026-09-17-modelo-locale-delta-keying-research`. It refines the label-inheritance requirement of `2026-09-09-registry-edition-authoring-adr` and keeps the read-time resolution of `2026-07-21-locale-key-resolution-adr`.
- `P01` makes resolution safe for values stored at less specific keys (locale barrier) and removes the one consumer that bypasses the key chain.
- `P02` moves the key universe and `dev/locales` tooling to canonical homes and adds a lossless collapse verb and purity gates.
- `P03` applies the collapse and deletes derived help and scaffold nulls.
- `P04` repairs placeholder and in-flight Spanish text, fills translations at canonical keys, and produces the wording-divergence worklist for source review.

## Parallelization

- The orchestrator owns `P01`, `P02` and `P03` (runtime, compiler and tooling code, catalogue-wide rewrites) and alone runs tests and commits.
- Localization workers own `P04.S11` and `P04.S06`: catalogue value edits through `python -m dev.locales set` or `set-batch` only, with no tests and no commits. They may run beside `P01` and `P02`, but must finish before `P03.S09` rewrites the catalogue files.
- `P04.S07` runs after `P03`, because translations land on the canonical keys the collapse establishes.
- `P04.S08` is read-only and may run at any time.

## Verification

- Resolved-text equivalence per locale, modelo, edition and casilla before and after `P03`, except for recorded repairs.
- Spanish label coverage and locale parity gates green.
- Purity gate green: zero restatements, zero inherited occurrence keys, zero null casilla leaves, zero template helps.

## Steps

### Phase `P01` - Resolver and consumer correctness

Make the runtime safe for a delta-keyed catalogue before any data moves.

- [x] `P01.S01` - add the Spanish-tier barrier to modelo localization resolution with barrier and fallback tests; `src/cadrumo/domain/calculations/registry/modelo_localization.py`.
- [x] `P01.S02` - resolve workspace casilla labels through the casilla key chain; `src/cadrumo/application/modelo/workspace.py`.

### Phase `P02` - Canonical key universe and collapse tooling

Teach dev/locales the canonical home of every casilla value and prove lossless collapse.

- [x] `P02.S12` - keep inherited label origins across provenance-only casilla storage overrides and republish; `dev/registry/compiler/loader_materialisation.py`.
- [x] `P02.S03` - emit occurrence keys only for stated casillas and keep continuity keys in the key universe; `dev/registry/compiler/loader.py`.
- [x] `P02.S04` - add a collapse verb computing canonical homes and proving resolved-text equivalence per locale; `dev/locales/`.
- [x] `P02.S05` - add a derived-help classifier and purity gate for restatements, inherited keys, null leaves and template helps; `dev/locales/`.

### Phase `P03` - Catalogue purification

Apply the collapse, remove derived help and scaffold nulls, and gate the purity invariants.

- [x] `P03.S09` - run the collapse across the four Modelo schema catalogues and record equivalence evidence; `src/cadrumo/locales/<locale>/modelo/schema/`.
- [x] `P03.S10` - delete derived help and scaffold null leaves and retire their generator; `src/cadrumo/locales/<locale>/modelo/schema/`.

### Phase `P04` - Content repair and translation

Repair placeholders and in-flight Spanish additions, then fill missing translations at canonical keys.

- [x] `P04.S11` - replace placeholder labels with same-box sibling text in every locale; `src/cadrumo/locales/<locale>/modelo/schema/`.
- [x] `P04.S06` - review the in-flight Spanish continuity additions against sibling or official text; `src/cadrumo/locales/es/modelo/schema/`.
- [x] `P04.S07` - fill missing en ca hu translations at canonical keys; `src/cadrumo/locales/{en,ca,hu}/modelo/schema/`.
- [x] `P04.S08` - produce the wording-divergence review worklist against official designs; `var/test-iter/label_audit/`.

## Parallelization

## Verification
