---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:3fd575769a8e35cbb93b5d76ad9ed5897d03828a5d249481922051964deb62be'
step_id: 'S08'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# make safety and responsibility routes visually persistent

## Scope

- `docs/index.md`

## Description

Verified `docs/index.md` carries an above-the-fold `{important}` admonition (lines
17-23) stating Cadrumo is not tax advice, is not affiliated with AEAT, does not replace
official tools, and that the operator files and remains responsible; it links
`disclaimer.md` for the full text. The admonition sits before the "Where to start" grid,
so it is visually persistent on first load rather than buried in a route.

## Outcome

Step closed as already-satisfied. No new commit required; this record documents the
verification only.

## Notes

Read `docs/index.md` at HEAD and confirmed the `{important}` block precedes all
navigation content.
