---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:2acf46d12825fd0724ab4731a2ef4215a37207fa5c19ae7d439739fe796ed463'
step_id: 'S31'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Replace the Ley 12/2002 corpus capture with official BOE-derived text

## Scope

- `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`

## Changes

- `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`
- `verify:` `dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
