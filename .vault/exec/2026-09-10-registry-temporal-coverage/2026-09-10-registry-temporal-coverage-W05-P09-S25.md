---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:2c172d58778f8c9ecdd9c76bac8c7c70df99ba0df4f74558f46e982ad5364c27'
step_id: 'S25'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Replace the hand-shaped Orden HAC/1526/2024 final-provision corpus capture with official BOE-derived text

## Scope

- `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html`

## Changes

- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html`
- `verify:` `dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
