---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:d080025b5a251d26184e84d7ea30cd166c49ef38ab8e62637aa0d62323ce95cf'
step_id: 'S01'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

# Replace the two hand-shaped Orden HAC/1526/2024 excerpts with the real BOE consolidated text for article 1 and the disposicion final unica, verified against the live BOE record

## Scope

- `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html`

## Changes

- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html.extracted.md`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html.extracted.md`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`

## Notes

BOE marks the quoted amended heading of Orden EHA/1274/2007 article 1 with
`class="articulo"`. Its text is preserved verbatim but carried as a quoted
paragraph, because two such headings in one excerpt yield two extracted units
and the anchor contract requires one.
