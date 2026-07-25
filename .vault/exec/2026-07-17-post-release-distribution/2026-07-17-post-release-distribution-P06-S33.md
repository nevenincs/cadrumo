---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S33'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace post-release-distribution with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S33 and 2026-07-17-post-release-distribution-plan placeholders are machine-filled by
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
     The DONE 7d20b2d984, marketplace publish is atomic, the whole cohort validates before any mutation so a refusal leaves the tree byte-identical, and the multi-plugin case that was entirely uncovered now has both a refusal test and a success test. GATE, the pre-fix loop leaves a torn tree so the atomicity test discriminates and ## Scope

- `dev/packaging/marketplace_publish.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# DONE 7d20b2d984, marketplace publish is atomic, the whole cohort validates before any mutation so a refusal leaves the tree byte-identical, and the multi-plugin case that was entirely uncovered now has both a refusal test and a success test. GATE, the pre-fix loop leaves a torn tree so the atomicity test discriminates

## Scope

- `dev/packaging/marketplace_publish.py`

## Description

- Split validation from mutation, so the whole cohort validates before anything is written.
- Add a multi-plugin refusal test asserting the marketplace is byte-identical afterwards.
- Add a multi-plugin success test, so the path is proven to work and not merely to fail safely.

## Outcome

A refusal now mutates nothing. Validation previously ran inside the mutation loop, so a two-plugin cohort whose second entry had no tree left the first already replaced and the index unmerged.

## Notes

Every prior test cohort declared exactly one plugin, so this entire class was uncovered while the module's docstring claimed both operations were idempotent. That claim was false on the refusal path and is now corrected. Simulating the pre-fix loop leaves a torn tree, which is what makes the new test discriminating. Semantic search was degraded for the whole of this work: the code index served roughly a fifth of the tree while reporting itself healthy, so a search miss was worthless as evidence. Discovery was done by direct directory listings, file reads, and targeted pattern search instead.
