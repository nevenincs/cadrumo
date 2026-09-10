---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:dcca833545a4597c32761c647e664f902286b7bb3bf5947af98648affcdbe50e'
step_id: 'S03'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace the hand-shaped Ley 12/2002 article 29 excerpt with the real BOE consolidated text of the Concierto Economico provision

## Scope

- `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`

## Changes

- `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html.extracted.md`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
