---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:715c53cafe627bf7907c8ce87e342d516338c710ac7cfb12bd3d628b7b3387d0'
step_id: 'S07'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# replace the first-page route list with a scannable task grid

## Scope

- `docs/index.md`

## Description

Verified the scannable task grid landed via the `docs-lifecycle-tutorials` feature
(commit `961104f678`) rather than under `docs-sphinx-ux`. `docs/index.md` renders an
eight-card `sphinx_design` grid (`::::{grid} 1 2 2 4`) under "Where to start", one card
per primary route (quickstart, IRPF lifecycle, IVA lifecycle, profile setup, import
transactions, classify transactions, filing calendar, filing spine).

## Outcome

Step closed as already-satisfied. No new commit required; this record documents the
verification only.

## Notes

Read `docs/index.md` at HEAD (lines 32-106) and confirmed eight `grid-item-card`
entries with `:link:` targets resolving to real how-to pages.
