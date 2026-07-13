---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S03'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-terminology-search with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-13-docs-terminology-search-plan placeholders are machine-filled by
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
     The Inventory the synonym candidate queue (mined, unratified) and commit the inventory with a ratify-or-clear disposition per candidate and ## Scope

- `dev/docs/terminology/_synonym_mining.py`
- `.vault/audit/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Inventory the synonym candidate queue (mined, unratified) and commit the inventory with a ratify-or-clear disposition per candidate

## Scope

- `dev/docs/terminology/_synonym_mining.py`
- `.vault/audit/`

## Description

- Read `src/cadrumo/_data/terminology/ratification/synonym-candidates.json`.
- Run `python -m dev.docs.terminology.synonyms validate`.

## Outcome

Queue is healthy: three candidates, each with an explicit status and
review reason (e.g. `prorateo` ratified as a hidden search form for
`prorrata`); validate reports clean. No unratified backlog; no action this
wave.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
