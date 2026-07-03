---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S15'
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
     The S15 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Give verify_source_file a companion-aware absent branch: present binary stays byte-exact hash-enforced, absent-but-companion-declared binary returns an accumulable advisory rather than hard-failing and ## Scope

- `src/aeat/domain/calculations/registry/_corpus_catalogue.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Give verify_source_file a companion-aware absent branch: present binary stays byte-exact hash-enforced, absent-but-companion-declared binary returns an accumulable advisory rather than hard-failing

## Scope

- `src/aeat/domain/calculations/registry/_corpus_catalogue.py`

## Description

- Give `verify_source_file` the companion-aware absent branch: a PRESENT binary stays byte-exact SHA-256 hash-enforced exactly as before; an absent binary whose catalogue entry classifies into the corpus-binaries companion set returns an accumulable `CorpusCompanionAdvisory` instead of hard-failing.
- Derive the companion classification from the catalogue data (`is_companion_corpus_binary`), never a hardcoded list.
- Commit `8bcdf00eac`.

## Outcome

- Present-binary semantics unchanged; companion absence is representable without silence.

## Notes

Record authored by the coordinator from the verified commit at HEAD: the executing agent's session was terminated by the account rate limit before reporting.
