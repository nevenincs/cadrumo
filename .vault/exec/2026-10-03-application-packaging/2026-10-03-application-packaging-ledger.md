---
tags:
  - '#exec'
  - '#application-packaging'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:32e5e98152b339bd7bda639e461c69c4fe96a17cd9f877f1db01d1bdc3de811b'
related:
  - "[[2026-10-03-application-packaging-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `application-packaging` ledger

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

- `S01` `A` `native/CONTRACT.md`
- `S01` `A` `native/package-layout.json`
- `S01` `A` `.vault/adr/2026-10-03-application-packaging-interpreter-foundation-adr.md`
- `S01` `M` `.vault/adr/2026-10-03-application-packaging-adr.md`
- `S01` `M` `.vault/research/2026-10-03-application-packaging-research.md`
- `S01` `verify:` `canonical ownership and Windows Linux macOS mapping review` -> `pass`
- `S02` `A` `native/toolchain.json`
- `S02` `A` `native/CMakeLists.txt`
- `S02` `A` `native/platform/Cargo.toml`
- `S02` `A` `native/platform/Cargo.lock`
- `S02` `A` `native/platform/include/cadrumo_platform.h`
- `S02` `A` `native/platform/src/lib.rs`
- `S02` `A` `native/platform/src/consumer.rs`
- `S02` `A` `native/platform/tests/consumer.c`
- `S02` `A` `dev/packaging/native/__init__.py`
- `S02` `A` `dev/packaging/native/generate.py`
- `S02` `A` `dev/packaging/native/build.ps1`
- `S02` `A` `dev/packaging/native/provision.py`
- `S02` `verify:` `MSVC SDK Rust pinned native build and C static DLL Rust consumers` -> `pass`
- `S02` `verify:` `fresh official SDK SHA256 and 77 locked Windows dependency wheels` -> `pass`
- `S02` `A` `native/interpreter/host.c`
- `S02` `A` `native/interpreter/python.c`
- `S03` `A` `native/interpreter/bootstrap.py`
- `S03` `A` `dev/packaging/native/assemble.py`
- `S03` `A` `dev/packaging/native/product.py`
- `S03` `verify:` `fresh product wheel build and package assembly` -> `pass`
- `S03` `verify:` `ruff check format and ty native Python tooling` -> `pass`
