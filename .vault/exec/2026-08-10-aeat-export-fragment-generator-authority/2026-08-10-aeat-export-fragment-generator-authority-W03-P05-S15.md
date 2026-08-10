---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f1d383a9c7dc54318dcee0fe36fb1b1518bb52037a9f7760ffe79e7c950a158c'
step_id: 'S15'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-export-fragment-generator-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-08-10-aeat-export-fragment-generator-authority-plan placeholders are machine-filled by
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
     The Prove offset, length, source-anchor, target-revision, and generated-file mutations are detected and ## Scope

- `dev/registry/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove offset, length, source-anchor, target-revision, and generated-file mutations are detected

## Scope

- `dev/registry/tests/`

## Description

- Add a real-filesystem publication gate covering offset, length, source-anchor, target-revision, and output-byte mutation of a freshly rendered candidate.
- Exercise the production loader, provenance verifier, and atomic publication boundary for every mutation rather than reconstructing layout logic in the test.
- Assert candidate refusal before cutover and byte-identical preservation of both the live export and the revision's non-export authority.
- Run independent review against the accepted generator-authority decision and hard-cut legacy rule.

## Outcome

All five mutation classes fail closed before a journal, backup, or live export change. The independent review found no critical, high, or medium issue and confirmed no legacy reader, merge, copy, or fallback surface was added.

## Notes

Focused generator-authority tests passed 50/50; Ruff, format, and file-scoped BasedPyright passed. No data loss, persistent failure, or Git lock occurred.
