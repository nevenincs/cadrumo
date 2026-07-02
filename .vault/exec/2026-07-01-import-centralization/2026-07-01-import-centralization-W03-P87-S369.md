---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S369'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace import-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S369 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Retarget setup_answers._ccaa() to resolve CCAA from the public aeat.domain.contribuyente facade instead of the private aeat.domain.contribuyente._ccaa submodule and ## Scope

- `src/aeat/core/setup_answers.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retarget setup_answers._ccaa() to resolve CCAA from the public aeat.domain.contribuyente facade instead of the private aeat.domain.contribuyente._ccaa submodule

## Scope

- `src/aeat/core/setup_answers.py`

## Description

- Retargeted `_ccaa()`'s deferred `importlib.import_module` call from the private `aeat.domain.contribuyente._ccaa` submodule to the public `aeat.domain.contribuyente` package facade, keeping `.CCAA` attribute access and the same lazy-resolution cycle-break technique.
- Verified live: `aeat.domain.contribuyente` carries `CCAA` in its `__all__`, so the retarget resolves identically.

## Outcome

Committed alongside S364, S368, and S388 in one commit (`b6aafa707`). `src/aeat/core/tests -k setup_answers` and `src/aeat/domain/deadlines/tests` green; `pytest --collect-only -q src/aeat` clean.

## Notes

None.
