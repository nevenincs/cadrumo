---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S07'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace fichero-boe-parity-gate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Unit-test the applicable-required restriction drops disposition-suppressed casillas and ## Scope

- `src/aeat/application/filing/tests/test_export_applicable_required_set.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Unit-test the applicable-required restriction drops disposition-suppressed casillas

## Scope

- `src/aeat/application/filing/tests/test_export_applicable_required_set.py`

## Description

- Add a Modelo 303 layout-level suppression test: the DID (refund) page casillas are representable under a refund disposition header (`D`) but not under a non-refund header (`I`), and non-refund representability is always a subset of refund representability.

## Outcome

Passes as part of the four-test P02 suite. Exercises suppression without needing a full 303 draft, since the helper takes only layout + headers + provider.

## Notes

Confirms the disposition-aware applicable restriction: casillas that only apply under an unselected disposition are excluded from the required set, so the gate does not false-panic on a legitimately-absent refund page.
