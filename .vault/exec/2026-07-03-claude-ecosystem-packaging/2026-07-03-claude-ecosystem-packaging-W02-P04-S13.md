---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S13'
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
     The S13 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Add a corpus-binary resolution seam that resolves a _data/corpus path from the aeat tree first, then the aeat_data companion package root and ## Scope

- `src/aeat/core/resources/_boundary.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a corpus-binary resolution seam that resolves a _data/corpus path from the aeat tree first, then the aeat_data companion package root

## Scope

- `src/aeat/core/resources/_boundary.py`

## Description

- Add the corpus-binary resolution seam to the bundled-data locator: a `_data/corpus/...` path resolves from the `aeat` package tree first, then falls back to the `aeat_data` companion package root (mirrored relative paths); a missing companion import means not-present, never an exception leak.
- Keep the single `importlib.resources` boundary discipline — the seam lives in the locator, not at call sites.
- Commit `fc0f30bd55`.

## Outcome

- Full-checkout and split-install corpus reads are uniform through one locator.

## Notes

Record authored by the coordinator from the verified commit at HEAD: the executing agent's session was terminated by the account rate limit before it could report. Gate re-verified post-hoc: the seam + companion test files pass (7 passed).
