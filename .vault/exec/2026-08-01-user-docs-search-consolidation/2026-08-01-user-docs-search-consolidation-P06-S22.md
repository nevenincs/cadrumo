---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:cd571c127f0ab100e28a19b1b1cf9f28d21ff04668b2dc7acf167df2ad5cb8cd'
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
- Fresh focused formal review of `21436e572dce4ae84de9358fd990d8af30593aa4`: PASS with no findings.
- Browser/Pagefind API integration and exact M130 result: pending P06.S24; not run in this step.

## Notes

The implementation agents ran RAG discovery, `node --check`, and `git diff --check`. The focused Pagefind correction is committed and its fresh formal review returned PASS with no findings. Tests, builds, Pagefind compilation, deployment, and live probes were not run. P06.S24 still owns the browser/Pagefind integration and exact M130 result gate.

### 2026-08-05 exact-query source re-audit

Fresh vaultspec-rag searches over the active plan, the accepted consolidation ADR, the P06 enrollment research, and the exact-query execution records, followed by exact reads of the registry projection, unified record funnel, Pagefind injector, and shared browser controller, confirm the deterministic `modelo 130 casilla 15` source contract. The bundled M130 registry declaration carries canonical `id = "15"` and `number = "15"`; `_from_casilla()` preserves that identity and localized descriptions; `_content_for()` indexes the record title (`Modelo 130 · casilla 15`) plus aliases and descriptions; and `searchStructuredCasilla()` filters `kind = casilla`, validates normalized `modelo`/`number`/optional `segmento` metadata, and accepts only one returned target from `result.data().url`. Exact enrollment therefore does not depend on RAG relevance: it is a registry projection plus shipped-record and metadata contract. RAG remains the semantic matching source for non-structured user language.

This establishes source readiness only. The Pagefind build, exact browser result, rendered destination, projection census, and localized-definition gate remain unexecuted under the standing no-test/no-build boundary and belong to P06.S24. No source edit, test, build, Pagefind compilation, live probe, sweep, reindexing, model download, generated artifact, or deployment was performed.
