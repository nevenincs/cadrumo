---
tags:
  - '#exec'
  - '#binding-consumer-closure'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:67fd19d5c499a609ffde90ec6c765dcd01ce415cef06f97e58f4fda371026145'
related:
  - "[[2026-10-02-binding-consumer-closure-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `binding-consumer-closure` ledger

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

- `S01` `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/bindings/0001-declarations.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/form_layouts/0001-form-layout.toml`
- `S01` `M` `dev/registry/mappings/modelo_360/2010/0002-pagina01.toml`
- `S01` `M` `dev/registry/mappings/modelo_360/2010/0003-pagina02.toml`
- `S01` `M` `src/cadrumo/application/modelo/work_form.py`
- `S01` `M` `src/cadrumo/application/modelo/tests/test_work_form_binding_labels.py`
- `S01` `R` `src/cadrumo/entrypoints/tests/test_modelo_wire_input_alias.py` -> `src/cadrumo/entrypoints/tests/test_modelo_casilla_wire_slot.py`
- `S01` `verify:` `python -m dev.registry.conformance valid` -> `pass`
- `S01` `verify:` `python -m dev.registry.form_layout generate --modelo 360 --check` -> `pass`
- `S01` `verify:` `pytest test_work_form_binding_labels test_work_form_grids test_modelo_casilla_wire_slot test_row_bindings_are_consumed -m 'unit or integration' (23)` -> `pass`
- `S01` `verify:` `basedpyright, ty, pyrefly on changed modules` -> `pass`
