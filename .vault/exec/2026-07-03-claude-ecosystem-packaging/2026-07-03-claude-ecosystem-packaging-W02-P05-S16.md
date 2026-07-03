---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S16'
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
     The S16 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Make verify_source_catalogue accumulate absent companion binaries into one loud advisory naming the missing set and the aeat[corpus-sources] install hint and ## Scope

- `src/aeat/domain/calculations/registry/_corpus_catalogue.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Make verify_source_catalogue accumulate absent companion binaries into one loud advisory naming the missing set and the aeat[corpus-sources] install hint

## Scope

- `src/aeat/domain/calculations/registry/_corpus_catalogue.py`

## Description

- Make `verify_source_catalogue` accumulate absent companion binaries into ONE loud advisory naming the missing set and the `aeat[corpus-sources]` install hint (`CORPUS_SOURCES_INSTALL_HINT`).
- Keep a NON-companion missing file (extracted text, normative html) a hard `RegistryValidationError` exactly as before.
- Commit `5a725a6fb9`.

## Outcome

- Split installs degrade loudly and instructively; full installs behave byte-identically.

## Notes

Record authored by the coordinator from the verified commit at HEAD: the executing agent's session was terminated by the account rate limit before reporting.
