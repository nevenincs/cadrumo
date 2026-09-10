---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:39fa57ef674d0502fda7c7f7208c7021d2efc1d09b00b84c3d3b5cf7dba3e852'
step_id: 'S04'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace the hand-shaped Ley 35/2006 article 48 law text with the real BOE consolidated text and drop the appended editorial section from the corpus file

## Scope

- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`

## Changes

- `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html.extracted.md`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
