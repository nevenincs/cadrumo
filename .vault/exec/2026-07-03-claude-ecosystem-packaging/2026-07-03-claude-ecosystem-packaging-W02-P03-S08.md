---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S08'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Exclude _data/corpus source binaries (*.pdf, *.xls, *.xlsx) from the aeat wheel via hatchling wheel excludes and ## Scope

- `pyproject.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Exclude _data/corpus source binaries (*.pdf, *.xls, *.xlsx) from the aeat wheel via hatchling wheel excludes

## Scope

- `pyproject.toml`

## Description

- Add hatchling wheel excludes for `_data/corpus/**/*.pdf`, `**/*.xls`, `**/*.xlsx` in `pyproject.toml` so the published `aeat` wheel carries zero corpus source binaries.
- Absorb the in-scope consumer-gate fallout atomically in the same commit: `test_wheel_bundles_corpus_and_registry.py` and `smoke_core.py` expected-path lists now exclude the corpus binaries, and the Renta-PDF presence assertion is inverted to prove absence instead.
- Commit `0dbb97ddc6`.

## Outcome

- Measured slim wheel: 39.16 MB (down from 171.8 MB), zero corpus binaries, 18798 members (414 extracted markdown, 319 normative HTML, 16014 registry, 63 agent).

## Notes

No incidents. No skipped work.
