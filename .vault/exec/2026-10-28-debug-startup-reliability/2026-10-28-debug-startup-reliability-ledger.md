---
tags:
  - '#exec'
  - '#debug-startup-reliability'
date: '2026-10-28'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:ccfae980ba67745a0ddf7b3f6b1b059cf475ebae79f58b1bc370104988d2de1c'
related:
  - "[[2026-10-28-debug-startup-reliability-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `debug-startup-reliability` ledger

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

- `S02` `M` `src/cadrumo_runtime/host/profile_connection_services.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_extension_records.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_sessions.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_host.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_service_records.py`
- `S02` `verify:` `Ruff check and format owned5` -> `pass`
- `S02` `verify:` `ty check owned production4` -> `pass`
- `S02` `verify:` `focused service-record and admission interleavings8 across scoped runs` -> `pass`
- `S02` `verify:` `independent Sol medium integrated lifecycle source review` -> `pass`
- `S02` `by:` `Sol 6.1 high; root integration`

## Notes

- `S02` Initial owning fixture startup failed twice before regression bodies; final reruns passed, logs125649/130851/131345/132021 under2026-10-28 test-runs. Root aggregate gates remain running.
