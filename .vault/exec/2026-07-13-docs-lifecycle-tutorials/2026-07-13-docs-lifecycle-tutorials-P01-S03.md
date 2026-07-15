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
