---
tags:
  - '#exec'
  - '#retenciones-workflow'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:ef3e87edac0ca1e0829eee565ab98296e955e91dc111ec51765ece57e0770b6b'
related:
  - "[[2026-09-24-retenciones-workflow-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `retenciones-workflow` ledger

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
- `S01` `M` `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `S01` `A` `src/cadrumo/domain/calculations/registry/tests/test_withholding_devengo_grouping.py`
- `S01` `M` `src/cadrumo/application/calculations/row_set_assembly.py`
- `S01` `verify:` `pytest test_withholding_devengo_grouping, registry -k withholding, test_withholding_producer, test_row_set_assembly` -> `pass`

## Notes

- `S01` test_grouping_dispatch_coverage fails on per_type2_record from the Modelo 180 row bindings (b7b4e95d20), pre-existing and outside this Step
