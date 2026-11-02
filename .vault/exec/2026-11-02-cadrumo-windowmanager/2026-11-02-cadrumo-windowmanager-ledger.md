---
tags:
  - '#exec'
  - '#cadrumo-windowmanager'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:0945e1e239a07dc4166ffa1d02e6a690e187491d438e4ee6b59e2fb8fd49bceb'
related:
  - "[[2026-11-02-cadrumo-windowmanager-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `cadrumo-windowmanager` ledger

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

- `S01` `A` `native/desktop/frontend/src/shell/docking.ts`
- `S01` `M` `native/desktop/frontend/src/shell/layout.ts`
- `S01` `A` `native/desktop/frontend/tests/live/docking.unit.ts`
- `S01` `verify:` `node --test tests/live/docking.unit.ts` -> `pass`
- `S01` `verify:` `tsc --noEmit` -> `pass`
- `S01` `verify:` `eslint .` -> `pass`
- `S01` `by:` `CADRUMO-WINDOWMANAGER`

## Notes

- `S01` Semantic discovery unavailable: client 0.6.0 / service 0.6.4 mismatch; owning ADR listing and static source discovery used.
