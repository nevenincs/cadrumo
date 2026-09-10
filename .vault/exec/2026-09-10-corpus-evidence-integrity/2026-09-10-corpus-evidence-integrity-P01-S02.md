---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:437be28fc697a415e9e964728abcc5fc8dab5bebe5bef9658c7f1f0c496e3cc1'
step_id: 'S02'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
