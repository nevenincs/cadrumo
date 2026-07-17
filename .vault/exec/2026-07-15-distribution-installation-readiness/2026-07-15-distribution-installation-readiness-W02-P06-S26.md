---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S26'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-installation-readiness with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S26 and 2026-07-15-distribution-installation-readiness-plan placeholders are machine-filled by
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
     The Byte-compare the complete generated marketplace plugin tree with its source authority and ## Scope

- `src/cadrumo/agent/tests/test_marketplace_generation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Byte-compare the complete generated marketplace plugin tree with its source authority

## Scope

- `src/cadrumo/agent/tests/test_marketplace_generation.py`

## Description

- Run the marketplace byte-compare gate against the live source authority.
- Confirm the generated marketplace plugin tree is byte-compared with the
  authored agent-data source and the packaged wheel payload by the real
  generation tests, with no fixture or mock substitution.

## Outcome

- `src/cadrumo/agent/tests/test_marketplace_generation.py` passed 4/4 on
  2026-07-17 against the current source tree (48.8 seconds, real
  materialisation), proving the complete generated marketplace tree matches its
  source authority byte-for-byte. The same generation path produced the
  marketplace and plugin members of release cohort
  `616f48fcc2a748349cbfccb48952499523d3de82ad5ced1f5ec664b67024e16f` at source
  commit `044e48450e918648fd331072bda4767b47737d34`, and that generated
  marketplace installed and served correctly in the live plugin-install lane.

## Notes

- Implementation was landed by earlier campaign commits; this record closes the
  row on verification evidence produced by the plan owner.
