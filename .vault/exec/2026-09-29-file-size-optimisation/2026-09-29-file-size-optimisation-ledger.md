---
tags:
  - '#exec'
  - '#file-size-optimisation'
date: '2026-09-29'
modified: '2026-09-29'
body_schema: 'body-v2'
body_hash: 'sha256:9b1076d2a8b643cf723cc7b90ca0e58da72f4a5729b9cad2627454a73f430b6e'
related:
  - "[[2026-09-29-file-size-optimisation-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `file-size-optimisation` ledger

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

- `S01` `A` `dev/docs/sequences/record_store.py`
- `S01` `M` `dev/docs/sequences/golden_store.py`
- `S01` `M` `dev/docs/sequences/compare.py`
- `S01` `M` `dev/docs/sequences/checks.py`
- `S01` `M` `dev/docs/sequences/cli.py`
- `S01` `M` `dev/docs/conftest.py`
- `S01` `M` `dev/docs/sequences/tests/test_compare.py`
- `S01` `M` `dev/docs/sequences/tests/test_cli.py`
- `S01` `M` `dev/docs/sequences/tests/test_setup_frame_goldens.py`
- `S01` `M` `dev/docs/sequences/tests/test_reader_frame_output_advisory.py`
- `S01` `R` `dev/docs/sequences/tests/test_golden_frame_stream_coherence.py` -> `dev/docs/sequences/tests/test_frame_coherence.py`
- `S01` `verify:` `pytest -m '' dev/docs/sequences/tests (272 passed)` -> `pass`
- `S01` `verify:` `ruff check + format --check` -> `pass`
- `S01` `verify:` `ty check on changed files` -> `pass`
- `S01` `verify:` `basedpyright on changed files (no new diagnostics vs baseline)` -> `pass`

## Notes

- `S01` The cli-sequence renderer still reads output from goldens until S02 lands; the docs build is not expected to pass between S01 and S02.
