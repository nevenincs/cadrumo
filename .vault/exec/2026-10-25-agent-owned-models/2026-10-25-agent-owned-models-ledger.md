---
tags:
  - '#exec'
  - '#agent-owned-models'
date: '2026-10-25'
modified: '2026-10-25'
body_schema: 'body-v2'
body_hash: 'sha256:20111e087790d0e32421926953deca7a0e78ae5bff5ab700c58f5796cef5ad54'
related:
  - "[[2026-10-25-agent-owned-models-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `agent-owned-models` ledger

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

- `S06` `D` `src/cadrumo/domain/transactions/model_tier.py`
- `S06` `M` `src/cadrumo/domain/transactions/llm.py`
- `S06` `M` `src/cadrumo/domain/transactions/__init__.py`
- `S06` `M` `dev/quality/metadata/import_load_targets.json`
- `S06` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S06` `verify:` `ruff check+format` -> `pass`
- `S06` `verify:` `ty check src/cadrumo/domain/transactions` -> `pass`
- `S06` `verify:` `lint-imports` -> `pass`
- `S06` `verify:` `pytest src/cadrumo/domain/transactions dev/quality/tests/test_import_load_worker.py` -> `pass`
- `S06` `by:` `implementer`
- `S07` `A` `dev/quality/tests/test_no_model_definitions.py`
- `S07` `verify:` `ruff check+format` -> `pass`
- `S07` `verify:` `ty check dev/quality/tests/test_no_model_definitions.py` -> `pass`
- `S07` `verify:` `lint-imports` -> `pass`
- `S07` `verify:` `pytest dev/quality/tests/test_no_model_definitions.py` -> `pass`
- `S07` `by:` `implementer`
