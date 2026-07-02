---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S09'
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
     The S09 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Confirm the existing grounded M100 calculation tests compute identical values before and after the parameter relocation, tolerating zero numeric drift and ## Scope

- `src/aeat/domain/calculations/registry/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm the existing grounded M100 calculation tests compute identical values before and after the parameter relocation, tolerating zero numeric drift

## Scope

- `src/aeat/domain/calculations/registry/tests`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->
- Update the grounded M100 Art. 85 calculation test to expect the registry-authored year-days parameter in formula provenance.
- Keep the external numeric oracle unchanged: the manual cadastral example still asserts `448.80`.
- Add neutral unrelated profile bindings required by the current Modelo 100 registry so the Art. 85 test reaches the formula under test.

## Outcome

- The grounded M100 Art. 85 test file passed: `5 passed`.
- Focused ruff check passed for the edited test file.
- No expected calculation values changed.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
- Pytest log: `_scratch-codex/w2_s09_m100_art85_pytest.log`.
- Ruff log: `_scratch-codex/w2_s09_ruff.log`.
