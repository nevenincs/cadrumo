---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:9c8db5991a9c9dc1ec528bbaf22e6414f0eec5400deaaefed20baeb78ae9d806'
step_id: 'S24'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Replace the hand-shaped Orden HAC/1526/2024 article corpus capture with official BOE-derived text

## Scope

- `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html`

## Changes

- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html`
- `verify:` `dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
