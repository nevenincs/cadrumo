---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S18'
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
     The S18 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Add an anti-tautology test that a corrupted PRESENT corpus binary still hard-fails the byte-exact hash gate and ## Scope

- `src/aeat/domain/calculations/registry/tests/test_corpus_catalogue_companion.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add an anti-tautology test that a corrupted PRESENT corpus binary still hard-fails the byte-exact hash gate

## Scope

- `src/aeat/domain/calculations/registry/tests/test_corpus_catalogue_companion.py`

## Description

- Add the anti-tautology proof that a corrupted PRESENT corpus binary still hard-fails the byte-exact hash gate: copy a real cited binary to a temp source root, flip bytes, assert `RegistryValidationError`.
- Commit `1a9a6802a7`.

## Outcome

- The companion-aware branch cannot weaken present-binary integrity: corruption is proven to still fail loudly.

## Notes

Record authored by the coordinator from the verified commit at HEAD; gate re-verified post-hoc (companion test module 5 passed).
