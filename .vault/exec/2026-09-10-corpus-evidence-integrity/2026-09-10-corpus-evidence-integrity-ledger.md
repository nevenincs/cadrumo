---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:cc36d5b20ba0f674febfc7ea2d1ef9f8152eee2be7f8593d1c86ad745f804706'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `corpus-evidence-integrity` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
- `S01` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html`
- `S01` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html.extracted.json`
- `S01` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html.extracted.md`
- `S01` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html`
- `S01` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html.extracted.json`
- `S01` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html.extracted.md`
- `S01` `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `S02` `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html`
- `S02` `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html.extracted.json`
- `S02` `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html.extracted.md`
- `S02` `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html`
- `S02` `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html.extracted.json`
- `S02` `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html.extracted.md`
- `S02` `D` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008.html`
- `S02` `D` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008.html.extracted.json`
- `S02` `D` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008.html.extracted.md`
- `S02` `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `S03` `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`
- `S03` `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html.extracted.json`
- `S03` `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html.extracted.md`
- `S03` `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `S04` `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`
- `S04` `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html.extracted.json`
- `S04` `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html.extracted.md`
- `S04` `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `S05` `M` `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `S05` `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `S15` `M` `src/cadrumo/_data/registry/aeat/legal/censo.toml`
- `S15` `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `S16` `M` `src/cadrumo/_data/registry/aeat/legal/irnr.toml`
- `S16` `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `S17` `M` `src/cadrumo/_data/registry/aeat/legal/iva.toml`
- `S17` `verify:` `uv run --no-sync aeat app registry verify` -> `pass`

## Notes

- `S01` BOE marks the quoted amended heading of Orden EHA/1274/2007 article 1 with
- `S01` `class="articulo"`. Its text is preserved verbatim but carried as a quoted
- `S01` paragraph, because two such headings in one excerpt yield two extracted units
- `S01` and the anchor contract requires one.
- `S02` The combined `orden-eha-3290-2008.html` was retired and replaced by one file per
- `S02` provision, matching the sibling `-art-6` / `-art-11` convention. BOE-faithful
- `S02` markup makes each article its own extracted unit, and anchor resolution requires
- `S02` a single unit per anchored file. The deletion is staged in the shared index.
- `S17` The prior excerpt was not merely unattributed but substantively wrong: it gave
- `S17` article 29 the invented title `Distribucion territorial de la recaudacion del
- `S17` Impuesto sobre el Valor Anadido`. The real article 29 is `Gestion e inspeccion
- `S17` del Impuesto`. All three former `required_text` phrases fail against the BOE text
- `S17` and were replaced.
