---
tags:
  - '#exec'
  - '#modelo-runtime-performance'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:1cf0c0cfa64072836bf0ddde758eb4b704240bd81817fd927f377a55495d0221'
related:
  - "[[2026-10-07-modelo-runtime-performance-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `modelo-runtime-performance` ledger

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

- `S02` `M` `src/cadrumo/application/operations/registry_schema_validation.py`
- `S02` `A` `src/cadrumo/application/operations/tests/test_schema_generator_parity.py`
- `S02` `A` `src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py`
- `S02` `verify:` `uv run --no-sync pytest -m unit src/cadrumo/application/operations/tests/test_schema_generator_parity.py src/cadrumo/application/operations/tests/test_registry_schema_validation.py src/cadrumo/application/operations/tests/test_schema_binding.py src/cadrumo/application/operations/tests/test_contract_invariants.py src/cadrumo/application/operations/tests/test_registry.py src/cadrumo/application/operations/tests/test_public_contracts.py src/cadrumo/application/operations/tests/test_typed_financial_operand_contract.py src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py --basetemp=.tmp/perf-s02-final-pytest -q` -> `pass`
- `S02` `verify:` `uv run --no-sync ty check src/cadrumo/application/operations/registry_schema_validation.py src/cadrumo/application/operations/tests/test_schema_generator_parity.py src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py` -> `pass`
- `S02` `verify:` `uv run --no-sync basedpyright src/cadrumo/application/operations/registry_schema_validation.py` -> `pass`
- `S02` `verify:` `uv run --no-sync pyrefly check src/cadrumo/application/operations/registry_schema_validation.py` -> `pass`
- `S02` `verify:` `uv run --no-sync ruff check src/cadrumo/application/operations/registry_schema_validation.py src/cadrumo/application/operations/tests/test_schema_generator_parity.py src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py` -> `pass`
- `S02` `verify:` `uv run --no-sync ruff format --check src/cadrumo/application/operations/registry_schema_validation.py src/cadrumo/application/operations/tests/test_schema_generator_parity.py src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py` -> `pass`
- `S02` `verify:` `actual alternating production-registry wall median 3.151s to 2.484s; CPU3.109s to 2.438s with identical contracts` -> `pass`
