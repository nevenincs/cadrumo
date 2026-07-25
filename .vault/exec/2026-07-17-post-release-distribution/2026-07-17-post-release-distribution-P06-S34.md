---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S34'
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
     The S34 and 2026-07-17-post-release-distribution-plan placeholders are machine-filled by
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
     The DONE 7d20b2d984, plugin-name collision refuses instead of silently overwriting, index entries carry published_by and a cohort declaring a name another product published is refused, while an unattributed entry stays claimable so the first release adopting it is not deadlocked. GATE, the sibling tree and its attribution both survive a refused takeover and ## Scope

- `dev/packaging/marketplace_publish.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# DONE 7d20b2d984, plugin-name collision refuses instead of silently overwriting, index entries carry published_by and a cohort declaring a name another product published is refused, while an unattributed entry stays claimable so the first release adopting it is not deadlocked. GATE, the sibling tree and its attribution both survive a refused takeover

## Scope

- `dev/packaging/marketplace_publish.py`

## Description

- Carry the publishing product on each marketplace index entry.
- Refuse a cohort declaring a plugin name another product published.
- Leave an unattributed entry claimable, and infer the publisher for a single-plugin cohort.

## Outcome

A collision refuses instead of silently overwriting. Ownership was keyed on bare plugin name, so a cohort declaring a sibling's name replaced that sibling's tree and index entry with no warning.

## Notes

This is the same loss the module was written to prevent, reachable by a different route: narrowing the wholesale replacement stopped a release deleting every sibling plugin, and left it able to delete exactly one. An unattributed entry stays claimable deliberately, because refusing it would deadlock the first release that adopts ownership tracking. The shipped marketplace manifest publishes unchanged, since a single-plugin cohort infers its publisher. Semantic search was degraded for the whole of this work: the code index served roughly a fifth of the tree while reporting itself healthy, so a search miss was worthless as evidence. Discovery was done by direct directory listings, file reads, and targeted pattern search instead.
