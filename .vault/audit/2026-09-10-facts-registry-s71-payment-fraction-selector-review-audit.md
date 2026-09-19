---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:7b3645cef2eda41b375ecf0172d4197d3e4640b6cc34aa0699396538d1f68082'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S71 payment-fraction selector review`

## Scope

Reviewed W03.P13.S71 only: the two BOE redaction captures and source rows, the three Article 109/110 authored selector facts, the M036 evidence bridge, adapter retirement, and focused tests. Excluded concurrent S64/S72 and unrelated dirty worktree changes.

## Findings

### art110-selector-conflates-law-and-modelo131 | high | A single live selector has incompatible legal applicability

The new Article 110 fact adds `B05` from the article wording and M036 table, but the exact same identifier is consumed as the Modelo 131 agrarian activity selector. The existing transaction test records that `B05` must be excluded because Modelo 131 cannot present pesca, and warns specifically against this Article 110-based expansion. The selector becomes live from 2026-03-26, yet its sources do not include the form-specific authority needed to change Modelo 131 scope. This makes fishing enter the Modelo 131 casilla-05 path without its required grounding and loses the distinction between a broad Article 110 rule and a form-specific selector.

## Recommendations

Resolve `art110-selector-conflates-law-and-modelo131` before accepting S71: retain a Modelo 131-specific, form-grounded selector excluding `B05`, and introduce a separate broad Article 110 selector only if a consumer requires it; then rewire consumers and add tests for both applicability boundaries. If the intended change is that Modelo 131 now accepts pesca, capture and cite the official Modelo 131 authority and replace the contradictory behavior-level test with an equally specific proof.
