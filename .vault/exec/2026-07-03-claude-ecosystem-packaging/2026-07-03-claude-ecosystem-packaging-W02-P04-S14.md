---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S14'
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
     The S14 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Test the seam resolves a corpus binary identically whether it lives under the aeat tree or the aeat_data companion root and ## Scope

- `src/aeat/core/resources/tests/test_corpus_companion_seam.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Test the seam resolves a corpus binary identically whether it lives under the aeat tree or the aeat_data companion root

## Scope

- `src/aeat/core/resources/tests/test_corpus_companion_seam.py`

## Description

- Add `test_corpus_companion_seam.py` proving a corpus binary resolves identically whether it lives under the `aeat` tree or under an `aeat_data` companion root (real temp package on `sys.path` carrying a mirrored file — no mocks).
- Commit `c17aca069f`.

## Outcome

- The seam contract is locked by real-behaviour tests on both resolution paths.

## Notes

Record authored by the coordinator from the verified commit at HEAD: the executing agent's session was terminated by the account rate limit before it could report. Gate re-verified post-hoc at the coordinator: `pytest src/aeat/core/resources/tests/test_corpus_companion_seam.py` green.
