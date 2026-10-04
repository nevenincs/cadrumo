---
tags:
  - '#exec'
  - '#desktop-shell'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:346ce01ddcdc742ae4222d2454277a8d70007416741d71de3043bf9841aa7fd6'
related:
  - "[[2026-10-04-desktop-shell-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `desktop-shell` ledger

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

- `S02` `M` `native/desktop/src-tauri/src/environment.rs`
- `S02` `M` `native/desktop/src-tauri/src/python/environment.py`
- `S02` `M` `native/desktop/src-tauri/src/main.rs`
- `S02` `M` `native/desktop/src-tauri/src/app.rs`
- `S02` `M` `native/desktop/src-tauri/src/terminal/mod.rs`
- `S02` `A` `native/desktop/src-tauri/src/terminal/ipc.rs`
- `S02` `M` `native/desktop/src-tauri/src/terminal/tests.rs`
- `S02` `A` `native/desktop/src-tauri/src/docs/mod.rs`
- `S02` `A` `native/desktop/src-tauri/src/logs/mod.rs`
- `S02` `A` `native/desktop/src-tauri/src/shell/mod.rs`
- `S02` `A` `native/desktop/src-tauri/src/shell/token.rs`
- `S02` `A` `native/desktop/src-tauri/src/shell/token.js`
- `S02` `A` `native/desktop/tests/shell-token.test.mjs`
- `S02` `M` `native/desktop/src-tauri/Cargo.toml`
- `S02` `M` `native/desktop/src-tauri/Cargo.lock`
- `S02` `M` `.gitignore`
- `S02` `M` `src/cadrumo/core/logging.py`
- `S02` `M` `src/cadrumo/core/tests/test_logging_rotation.py`
- `S02` `verify:` `cmake --build build/s02-desktop-host --target desktop-host-test` -> `pass`
- `S02` `verify:` `cmake --build build/s02-desktop-host --target desktop-host-clippy` -> `pass`
- `S02` `verify:` `cargo fmt --check` -> `pass`
- `S02` `verify:` `node native/desktop/tests/headless.test.mjs` -> `pass`
- `S02` `verify:` `node --test native/desktop/tests/shell-token.test.mjs` -> `pass`
- `S02` `verify:` `pytest src/cadrumo/core/tests/test_logging_rotation.py` -> `pass`
- `S02` `verify:` `ruff check, ruff format --check, ty check on touched Python` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `M` `docs/conf.py`
- `S03` `A` `docs/_static/cadrumo-desktop-bridge.js`
- `S03` `M` `docs/_static/cadrumo-docs.js`
- `S03` `M` `dev/docs/build.py`
- `S03` `M` `dev/docs/tests/test_docs_build.py`
- `S03` `A` `dev/docs/tests/test_docs_desktop_flavor.py`
- `S03` `verify:` `pytest -m integration dev/docs/tests/test_docs_desktop_flavor.py (16 tests: real docs/conf.py Sphinx builds, Chromium bridge gates)` -> `pass`
- `S03` `verify:` `pytest -m unit dev/docs/tests/test_docs_build.py flavor tests` -> `pass`
- `S03` `verify:` `python -m dev.docs.build --flavor desktop --language en --out-dir <scratch> --isolated-source (sequence check skipped in scratch only): 561 pages, 0 remote loaded resources, bridge before cadrumo-docs.js on every page, pagefind present` -> `pass`
- `S03` `verify:` `ruff check, ruff format --check, ty check on touched Python` -> `pass`
- `S03` `by:` `opus-s03-executor`
- `S02` `A` `native/desktop/src-tauri/src/shell/channel.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/mod.rs`
- `S02` `verify:` `cmake --build build/s02-desktop-host --target desktop-host-test` -> `pass`
- `S02` `verify:` `cmake --build build/s02-desktop-host --target desktop-host-clippy` -> `pass`
- `S02` `verify:` `node native/desktop/tests/headless.test.mjs` -> `pass`

## Notes

- `S02` Live tests used build 1761 Release acceptance package (2026-10-03) relocated to scratch with current src/cadrumo overlaid on site-packages; no current package could be built. Launch carries no new fields until Group B consumers land (orchestrator ruling A).
- `S03` docs-build recipe not run to completion: the full build refuses at the cli-sequence gate on the stale shared .authority (pre-existing; reproduced on the web flavor without S03 involvement)
- `S03` `test_docs_build.py:` `test_a_changed_source_check_builds_the_stub_its_build_generates` (stale authority) and `test_docs_build_directory_contains_only_canonical_html` (doctrees, locale-logs left in the shared build root on 2026-10-03/04 by other runs) fail pre-existing
- `S02` Added the plan's `channel_interceptor` (shell/channel.rs) and a table-driven dispatcher token test after first logging; tauri test feature added as a dev-dependency for mock-runtime tests.
