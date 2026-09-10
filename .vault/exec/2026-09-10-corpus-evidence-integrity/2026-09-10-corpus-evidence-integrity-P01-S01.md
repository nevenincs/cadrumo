---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:a0cd83c673f68f8fab4eb35690f056294a5a1f593cf17a6a219de7979d1c6b36'
step_id: 'S01'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
