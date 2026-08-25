---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:9d2ddae21f9095b094657f5ba44034ef094b2b1faf120eeb767904fa4d60d89b'
step_id: 'S06'
related:
  - '[[2026-06-04-docs-sphinx-ux-plan]]'
---

# `docs-sphinx-ux` `W01.P02.S06`

Scope: `W01.P02.S06`.

## Description

Connect the Furo light and dark logos through theme options.
Connect the custom stylesheet and favicon through `docs/conf.py`.
Remove the generic Sphinx logo assignment after browser review showed it duplicated the Furo logos.

## Outcome

The browser review now shows exactly one visible sidebar logo and the expected non-official title.
`uv run --no-sync ruff check docs/conf.py` passed.

## Notes

The browser packet is served from the generated review output for human inspection.
The human brand approval step remains open.
