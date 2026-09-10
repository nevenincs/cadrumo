---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:684a2ae8ec973a5952e05f22de21610e93139dd8ae9492b26e60fe5a9fe99171'
step_id: 'S02'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

# Replace the hand-shaped Orden EHA/3290/2008 excerpt with the real BOE consolidated text for articles 1 and 4, preserving both existing anchors

## Scope

- `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008.html`

## Changes

- `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html`
- `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html.extracted.json`
- `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html.extracted.md`
- `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html`
- `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html.extracted.json`
- `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html.extracted.md`
- `D` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008.html`
- `D` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008.html.extracted.json`
- `D` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008.html.extracted.md`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`

## Notes

The combined `orden-eha-3290-2008.html` was retired and replaced by one file per
provision, matching the sibling `-art-6` / `-art-11` convention. BOE-faithful
markup makes each article its own extracted unit, and anchor resolution requires
a single unit per anchored file. The deletion is staged in the shared index.
