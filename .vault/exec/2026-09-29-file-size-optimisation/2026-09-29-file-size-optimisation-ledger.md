---
tags:
  - '#exec'
  - '#file-size-optimisation'
date: '2026-09-29'
modified: '2026-09-29'
body_schema: 'body-v2'
body_hash: 'sha256:e70d7741e3998161b66c5d076a22cabc585f409801ca06548692b0cb2253d9ca'
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
- `S02` `M` `dev/docs/sequence_directive.py`
- `S02` `M` `dev/docs/sequence_build_gate.py`
- `S02` `M` `dev/docs/sequences/checks.py`
- `S02` `M` `dev/docs/sequences/record_store.py`
- `S02` `A` `dev/docs/sequences/recorded_faults.py`
- `S02` `R` `dev/docs/tests/test_golden_records_no_crash.py` -> `dev/docs/sequences/tests/test_recorded_faults.py`
- `S02` `M` `dev/deploy/docs_static_site.py`
- `S02` `M` `dev/deploy/tests/test_docs_static_site.py`
- `S02` `M` `dev/docs/tests/test_docs_build.py`
- `S02` `M` `dev/docs/tests/test_sequence_build_gate.py`
- `S02` `M` `dev/docs/tests/test_sequence_directive.py`
- `S02` `M` `dev/docs/tests/test_sequence_goldens.py`
- `S02` `verify:` `pytest -m '' dev/docs/sequences/tests dev/docs/tests/test_sequence_directive.py dev/docs/tests/test_sequence_build_gate.py dev/deploy/tests/test_docs_static_site.py (372 passed)` -> `pass`
- `S02` `verify:` `ruff check + format` -> `pass`
- `S02` `verify:` `ty check on changed files` -> `pass`
- `S02` `verify:` `basedpyright on changed files (no new diagnostics vs baseline)` -> `pass`

## Notes

- `S01` The cli-sequence renderer still reads output from goldens until S02 lands; the docs build is not expected to pass between S01 and S02.
- `S02` The crash-marker and version-literal corpus scans over committed golden bodies became engine rules applied to every record at refresh and check, since goldens no longer hold output.
- `S02` The committed goldens are regenerated in S03; until then the committed-corpus check fails on the schema-2 goldens.
