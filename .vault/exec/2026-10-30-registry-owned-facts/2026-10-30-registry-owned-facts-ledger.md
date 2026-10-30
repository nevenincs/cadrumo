---
tags:
  - '#exec'
  - '#registry-owned-facts'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:68db57af74acf2f8770e7702474289c321394278396330242e30bf1f202e25aa'
related:
  - "[[2026-10-30-registry-owned-facts-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `registry-owned-facts` ledger

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

- `S01` `M` `src/cadrumo/application/modelo/dt12_advisory.py`
- `S01` `M` `src/cadrumo/application/filing/m190_context_validation.py`
- `S01` `M` `src/cadrumo/application/filing/m280_context_validation.py`
- `S01` `verify:` `pytest focused dt12 m190 m280` -> `pass`
- `S02` `M` `src/cadrumo/application/modelo/projection.py`
- `S02` `M` `src/cadrumo/application/calculations/m303_regimen_simplificado_annual_summary.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/m303_orden_constants.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/ledger_binding_validation.py`
- `S02` `verify:` `pytest focused registry and consumer suites` -> `pass`
- `S02` `verify:` `lint-imports` -> `fail`

## Notes

- `S01` Modelo 190 incapacity clave rule, Modelo 280 extinction key and Modelo 720 per-class subclaves move to S03, which adds their registry source
- `S02` lint-imports stops on a syntax error at `dev/tests/test_import_quality_gate.py:727,` outside this Step
