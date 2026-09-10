---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:59d2c2a730381c7fbb1cb1b142c51e158bb75b6fb86161f80e96255f7de10c10'
step_id: 'S27'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Replace the hand-shaped Orden EHA/3290/2008 corpus capture with official BOE-derived article captures

## Scope

- `src/cadrumo/_data/corpus/normatives/html/`

## Changes

- `D` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008.html`
- `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html`
- `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html`
- `verify:` `dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
