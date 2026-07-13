---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S05'
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
     The S05 and 2026-07-13-docs-terminology-search-plan placeholders are machine-filled by
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
     The Author the preprocess rule file for the four corpus source kinds and add the strict preprocess-check repo gate test and ## Scope

- `.vaultragpreprocess.toml`
- `dev/docs/preprocess/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the preprocess rule file for the four corpus source kinds and add the strict preprocess-check repo gate test

## Scope

- `.vaultragpreprocess.toml`
- `dev/docs/preprocess/tests/`

## Description

- Author repo-root `.vaultragpreprocess.toml`: four rules routing normatives
  HTML, corpus PDFs, `.xls`, and `.xlsx` through the hook command with
  `on_error = "skip"` and per-kind timeouts.
- Validate with `vaultspec-rag preprocess check --json` (v0.2.28): 4 rules.
- Add the CI-safe structural gate in `dev/docs/preprocess/tests/test_hook.py`
  (validates the TOML shape without importing the upstream package).

## Outcome

Committed in `485ac85614`. Two live catches: the original `*.xls*`
pattern also matched `.xls.extracted.md` sidecars (split into explicit
`.xls`/`.xlsx` rules), and upstream requires the
`VAULTSPEC_RAG_PREPROCESS_ENABLED=1` opt-in before rules take effect.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
