---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:35a2908056bd8cc9c8d756b28c40b8d60240ab23a9f2a1c9df6a3369ea694418'
step_id: 'S29'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Replace the Ley 35/2006 article 48 corpus capture with official text separated from editorial gloss

## Scope

- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`

## Changes

- `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`
- `verify:` `dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
