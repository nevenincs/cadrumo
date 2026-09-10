---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:9dae049539fc41e031b3486201cd6089f62e9ebaa4be1d9a99c91f50d5065155'
step_id: 'S04'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

# Replace the hand-shaped Ley 35/2006 article 48 law text with the real BOE consolidated text and drop the appended editorial section from the corpus file

## Scope

- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`

## Changes

- `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html.extracted.md`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
