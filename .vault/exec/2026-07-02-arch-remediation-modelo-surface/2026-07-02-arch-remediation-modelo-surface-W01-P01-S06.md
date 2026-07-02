---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S06'
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
     The S06 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Confirm the M210 continuity suite and the convenio-doble-imposicion suites pass unmodified against the typed outcome and ## Scope

- `src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm the M210 continuity suite and the convenio-doble-imposicion suites pass unmodified against the typed outcome

## Scope

- `src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`

## Description

- Run the M210 formula-runtime contract suite.
- Run the M210 convenio rate-resolution verification suite.
- Run the M210 IRNR multi-year continuity suite.

## Outcome

The focused W1 continuity gate passed: `32 passed in 22.49s`.

## Notes

Full pytest output is stored in `_scratch-codex/w1_m210_convenio_pytest.log`.
