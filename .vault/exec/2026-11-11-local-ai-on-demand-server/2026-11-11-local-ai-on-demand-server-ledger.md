---
tags:
  - '#exec'
  - '#local-ai-on-demand-server'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:2ac25ec31ac0e7948b46172d75a63caeab1028962f70e2ff384d959a9058b110'
related:
  - "[[2026-11-11-local-ai-on-demand-server-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `local-ai-on-demand-server` ledger

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

- `S01` `M` `native/application/src/provisioning/local_ai/supervision.rs`
- `S01` `M` `native/application/src/provisioning/local_ai/supervision/tests.rs`
- `S01` `M` `native/application/src/provisioning/local_ai/llama_server/tests.rs`

## Notes

- `S01` cargo tests not run here: native builds are root-only; pending DESKTOP
