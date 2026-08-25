---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:ce1f59984233fb8cc7362d310f4e498ffa945018a186514221e1875e2ef9a053'
step_id: 'S03'
related:
  - '[[2026-06-04-docs-sphinx-ux-plan]]'
---

# `docs-sphinx-ux` `W01.P01.S03`

Scope: `W01.P01.S03`.

## Description

Declare the published-site base URL placeholder through `AEAT_DOCS_BASE_URL`.
Configure OpenGraph site name, type, image, and description length.
Keep sitemap generation inactive until a canonical base URL is provided.

## Outcome

The documentation site now has a clear metadata path for future publication without inventing an unstable public URL.
The single-page review build loaded the metadata configuration and produced HTML successfully.

## Notes

The review build intentionally excluded linked pages, so its unresolved-link warnings are packet-scoped and not a full-site quality signal.
