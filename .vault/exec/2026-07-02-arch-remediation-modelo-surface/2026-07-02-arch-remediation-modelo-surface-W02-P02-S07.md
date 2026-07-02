---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S07'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-modelo-surface with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Declare the M100 imputation-year-days value as a registry parameter on the M100 revisions in the registry authoring tree so it rides the loader and compiler and ## Scope

- `src/aeat/_data/registry/aeat/modelos/100` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare the M100 imputation-year-days value as a registry parameter on the M100 revisions in the registry authoring tree so it rides the loader and compiler

## Scope

- `src/aeat/_data/registry/aeat/modelos/100`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->
- Declare `renta-2024-imputacion-inmobiliaria-year-days` as an integer days parameter on the Modelo 100 2024 Art. 85 parameter bundle.
- Declare `renta-2025-imputacion-inmobiliaria-year-days` as an integer days parameter on the Modelo 100 2025 Art. 85 parameter bundle.
- Ground both parameters on the same Art. 85 manual source family as the existing imputed-real-estate rate parameters.

## Outcome

- The M100-only registry loader accepted the updated Modelo 100 authoring tree and confirmed both new parameter ids are present.
- Existing Art. 85 pytest could not be used as a clean S07 gate because full authority loading currently fails on unrelated Modelo 131 2025 internal-only casilla WIP before any M100 calculation executes.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
- Verification log: `_scratch-codex/w2_s07_m100_direct_load.log`.
- Blocked broader log: `_scratch-codex/w2_s07_m100_art85_pytest.log`.
