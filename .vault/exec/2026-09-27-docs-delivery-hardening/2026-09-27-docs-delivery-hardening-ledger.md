---
tags:
  - '#exec'
  - '#docs-delivery-hardening'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:29a0572dd03d54dd9c52c6c60a3f4f2f8fb040da18e8f6ce503b4a50489b5561'
related:
  - "[[2026-09-27-docs-delivery-hardening-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `docs-delivery-hardening` ledger

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

- `S01` `A` `dev/deploy/docs_asset_manifest.py`
- `S01` `A` `dev/deploy/docs_asset_delivery.py`
- `S01` `M` `dev/deploy/r2_objects.py`
- `S01` `A` `dev/deploy/tests/test_docs_asset_delivery.py`
- `S01` `verify:` `Focused publisher tests 7 passed; Ruff and ty` -> `pass`
