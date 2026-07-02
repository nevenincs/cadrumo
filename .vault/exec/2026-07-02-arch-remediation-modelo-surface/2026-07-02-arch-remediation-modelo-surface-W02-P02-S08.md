---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S08'
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
     The S08 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Delete the _M100_IMPUTATION_YEAR_DAYS constant from the generic formula runtime and read the value from the compiled snapshot instead and ## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete the _M100_IMPUTATION_YEAR_DAYS constant from the generic formula runtime and read the value from the compiled snapshot instead

## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->
- Delete the generic `_M100_IMPUTATION_YEAR_DAYS` constant from the formula runtime.
- Extend the M100 Art. 85 formula op contract to require a registry-authored imputation-year-days parameter.
- Read the parameter from the compiled snapshot and validate the supplied imputation days against that declared maximum.
- Add the year-days parameter operand to the 2024 and 2025 M100 Art. 85 formula declarations.

## Outcome

- Direct full-authority M100 calculations for 2024 and 2025 still computed casilla `0089` as `448.80`.
- The calculation trace for each year now includes `renta-<year>-imputacion-inmobiliaria-year-days` as a formula operand.
- Focused ruff check passed for the edited runtime file.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
- Verification log: `_scratch-codex/w2_s08_m100_direct_calc.log`.
- Ruff log: `_scratch-codex/w2_s08_ruff.log`.
