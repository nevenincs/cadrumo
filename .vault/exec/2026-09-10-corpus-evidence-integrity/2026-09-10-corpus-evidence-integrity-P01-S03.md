---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:ea61e2f2977e6106c06b843a4ed85e5da6b28e8785091e0975fa034e1f59a7b8'
step_id: 'S03'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

# Replace the hand-shaped Ley 12/2002 article 29 excerpt with the real BOE consolidated text of the Concierto Economico provision

## Scope

- `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`

## Changes

- `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html.extracted.md`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
