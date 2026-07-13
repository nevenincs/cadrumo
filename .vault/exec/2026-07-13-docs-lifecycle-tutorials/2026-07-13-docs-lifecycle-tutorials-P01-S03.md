---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S03'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-lifecycle-tutorials with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Merge classify-with-llm.md, classify-with-llm-evidence.md, and setup-llm-classification.md into one consolidated LLM-assisted-classification page and ## Scope

- `sweep inbound links`
- `delete the merged pages`
- `docs/how-to/classify-with-llm.md docs/how-to/classify-with-llm-evidence.md docs/how-to/setup-llm-classification.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Merge classify-with-llm.md, classify-with-llm-evidence.md, and setup-llm-classification.md into one consolidated LLM-assisted-classification page

## Scope

- `sweep inbound links`
- `delete the merged pages`
- `docs/how-to/classify-with-llm.md docs/how-to/classify-with-llm-evidence.md docs/how-to/setup-llm-classification.md`

## Description

- Rewrite `docs/how-to/classify-with-llm.md` as the single consolidated
  LLM-assisted-classification page with the "This page covers the ..."
  opening: provider setup (absorbing `setup-llm-classification.md`), the
  suggestion preview, the four-terminal review loop, saturation and manual
  derivation, and the full evidence-reading workflow (absorbing
  `classify-with-llm-evidence.md`) including on-host vs cloud paths, the
  consent gates, auto-split, document protections, the settings table, and
  provenance.
- Drop the duplicated "short version" evidence section, the duplicated
  review-loop prose, and the duplicated privacy paragraphs; keep one copy of
  each fact.
- Sweep inbound references: the how-to index's three LLM grid cards
  collapsed to one, two toctree entries removed, `workstation-setup.md`
  retargeted (twice) to the consolidated page's provider-setup anchor.
- Delete `docs/how-to/classify-with-llm-evidence.md` and
  `docs/how-to/setup-llm-classification.md` via `git rm`.

## Outcome

Three pages (~630 lines) are now one page (~330 lines) with every command
and consent rule preserved. Grep confirms zero remaining references to the
deleted filenames outside build artifacts.

## Notes

All commands were carried verbatim from the source pages, which were
authored against the live surface; the campaign-wide conformance gate at
P05.S16 re-verifies them.
