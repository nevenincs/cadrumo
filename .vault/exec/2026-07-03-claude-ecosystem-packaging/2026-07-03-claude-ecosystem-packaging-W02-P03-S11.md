---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S11'
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
     The S11 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Add a test that the aeat-data wheel packages exactly the corpus binaries under aeat_data with mirrored relative paths and nothing else and ## Scope

- `dev/packaging/tests/test_aeat_data_distribution.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a test that the aeat-data wheel packages exactly the corpus binaries under aeat_data with mirrored relative paths and nothing else

## Scope

- `dev/packaging/tests/test_aeat_data_distribution.py`

## Description

- Add `dev/packaging/tests/test_aeat_data_distribution.py` proving the built `aeat-data` companion packages exactly the tracked corpus binaries with mirrored relative paths, and nothing else.
- Assert version parity between the `aeat-data` distribution and the root `aeat` package.
- Add a per-file `ruff` `S603`/`S607` ignore for the subprocess build invocation this test drives.
- Commit `1762e2a483`.

## Outcome

- 3/3 tests passed.

## Notes

No incidents. No skipped work.
