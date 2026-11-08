---
tags:
  - '#exec'
  - '#prior-carry-attestation'
date: '2026-11-08'
modified: '2026-11-08'
body_schema: 'body-v2'
body_hash: 'sha256:ca37abd2caff0a001da7ee48a9426dc18dbb78b70d592637c578bd1ab350d535'
related:
  - "[[2026-11-08-prior-carry-attestation-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `prior-carry-attestation` ledger

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

- `S01` `M` `src/cadrumo/application/modelo/calculate_input.py`
- `S01` `M` `src/cadrumo/application/modelo/calculation_bucket_actions.py`
- `S01` `M` `src/cadrumo/application/modelo/calculation_helpers.py`
- `S01` `M` `src/cadrumo/application/modelo/calculation_operation.py`
- `S01` `M` `src/cadrumo/application/modelo/caller_context.py`
- `S01` `M` `src/cadrumo/application/modelo/edit_admission.py`
- `S01` `M` `src/cadrumo/application/modelo/edit_execution.py`
- `S01` `M` `src/cadrumo/application/modelo/edit_models.py`
- `S01` `M` `src/cadrumo/domain/modelos/calculation_revision_operator_layer.py`
- `S01` `M` `src/cadrumo/domain/modelos/tests/test_calculation_revision_operator_layer.py`
- `S01` `A` `src/cadrumo/entrypoints/tests/profile_persistence/test_m100_carry_attestation.py`
- `S01` `verify:` `pytest-test_m100_carry_attestation` -> `pass`
- `S01` `verify:` `pytest-test_calculation_revision_operator_layer` -> `pass`

## Notes

- `S01` 18-failures-in-payer-fact-and-cli-calculate-suites-reproduce-on-feature/tui-HEAD
