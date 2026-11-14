---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-11-14'
modified: '2026-11-15'
body_schema: 'body-v2'
body_hash: 'sha256:9d3f62983609fde0c36537d197ea1eb0e213d008d61b4a1e8fd225bfad3e09b3'
related:
  - "[[2026-11-14-source-casilla-integration-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `source-casilla-integration` ledger

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

- `S05` `M` `dev/registry/mappings/modelo_840/2003/0002-pagina01.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/casillas/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/constructs/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/export/0001-record-m840-pagina01.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/export/_generation.provenance.json`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/form_layouts/0001-form-layout.toml`
- `S05` `M` `src/cadrumo/core/filing_producer_key.py`
- `S05` `M` `src/cadrumo/locales/ca/modelo/schema/840.yml`
- `S05` `M` `src/cadrumo/locales/en/modelo/schema/840.yml`
- `S05` `M` `src/cadrumo/locales/es/modelo/schema/840.yml`
- `S05` `M` `src/cadrumo/locales/hu/modelo/schema/840.yml`
- `S05` `verify:` `target-current 840` -> `pass`
- `S05` `verify:` `conformance valid/runtime-load/integrity` -> `pass`
