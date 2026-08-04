---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:7a3a73ef28ebfbee85199caf33d89f4c4697dbf17f470ad9af9ba24299f7b3a3'
step_id: 'S22'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Add a structured modelo/casilla exact-search route that resolves the canonical record and destination before lexical fallback

## Scope

- `docs/_static/cadrumo-docs.js`

## Description

- Ground the shared controller and Pagefind filter metadata with RAG and exact symbol confirmation.
- Parse unambiguous modelo/casilla addresses without copying registry data into JavaScript.
- Resolve one matching shipped casilla record before the normal card/page ladder, preserving fallback for ambiguous or older indexes.

## Outcome

Commits `a4281864a9e31438ccc9b536657cb89d7576020f` and `21436e572dce4ae84de9358fd990d8af30593aa4` add and correct a structured casilla fast path using shipped Pagefind metadata. It normalizes presentation padding and locale accents, uses the awaited Pagefind `data.url`, supports canonical segmented forms, refuses ambiguous segmented-modelo addresses, and leaves ordinary Pagefind ranking unchanged when the structured address cannot be resolved.

## Tracking

- M130/casilla-15 structured address path: implemented in code.
- Stable target comes from the injected Pagefind record: implemented in code.
- Segmented-modelo ambiguity protection: implemented in code.
- Formal review found the structured path read `result.url`; `21436e572dce4ae84de9358fd990d8af30593aa4` now uses the URL returned by `result.data()`.
- Browser/Pagefind API integration and exact M130 result: pending P06.S24; not run in this step.

## Notes

The implementation agents ran RAG discovery, `node --check`, and `git diff --check`. The focused Pagefind correction is committed, but a fresh review and P06.S24 runtime gate are required. Tests, builds, Pagefind compilation, deployment, and live probes were not run. The step must not be marked closed until P06.S24 acceptance passes.
