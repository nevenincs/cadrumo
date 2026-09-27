---
tags:
  - '#exec'
  - '#registry-conformance-rectification'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:a2411b3cc999531eae7ee258a01deaec4a5d7d051633437667ff516db1d411c1'
related:
  - "[[2026-09-27-registry-conformance-rectification-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `registry-conformance-rectification` ledger

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
- `S04` `M` `dev/registry/registry_collapse_verification.py`
- `S04` `M` `dev/registry/tests/test_registry_collapse_verification.py`
- `S04` `verify:` `pytest dev/registry/tests/test_registry_collapse_verification.py` -> `pass`
- `S01` `M` `dev/registry/registry_collapse_verification.py`
- `S01` `M` `dev/registry/tests/test_registry_collapse_verification.py`
- `S01` `verify:` `registry_collapse_verification --modelo 100 no_live_mutation` -> `pass`

## Notes

- `S04` Classified as a comparison artefact: family_dispositions is a typed Mapping; shares the S01 commit because both change the same comparator module
