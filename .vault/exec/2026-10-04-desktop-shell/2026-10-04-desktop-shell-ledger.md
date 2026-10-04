---
tags:
  - '#exec'
  - '#desktop-shell'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:25d149f26c892b0c755aec4826d76a9ab834de424363b67bb9034e34a9cdbe3b'
related:
  - "[[2026-10-04-desktop-shell-plan]]"
---

# `desktop-shell` ledger

## Changes

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
- `S03` `verify:` `after moving the bridge to the browser-reported parent origin (plan: origins computed at runtime): pytest -m integration test_docs_desktop_flavor.py 16 tests` -> `pass`
- `S03` `verify:` `mutation check: bridge without the source check, with a document bubble-phase key listener, or without the top-window check is each caught by one browser gate` -> `pass`
- `S03` `verify:` `desktop English whole-scope build re-run with the final conf.py: 561 pages, 0 remote loaded resources, bridge first on every page, pagefind present` -> `pass`
- `S01` `A` `dev/packaging/native/docs_build.py`
- `S01` `A` `dev/packaging/native/docs_stage.py`
- `S01` `A` `dev/packaging/native/package_inventory.py`
- `S01` `A` `native/cmake/Docs.cmake`
- `S01` `A` `dev/packaging/tests/test_native_docs_staging.py`
- `S01` `A` `dev/packaging/tests/test_native_delegated_inventory.py`
- `S01` `M` `dev/packaging/native/assemble.py`
- `S01` `M` `dev/packaging/native/cmake_build.py`
- `S01` `M` `dev/packaging/native/installation.py`
- `S01` `M` `dev/packaging/tests/test_native_installation.py`
- `S01` `M` `native/cmake/BuildPaths.cmake`
- `S01` `M` `native/cmake/Packaging.cmake`
- `S01` `M` `native/desktop/CMakeLists.txt`
- `S01` `M` `native/CONTRACT.md`
- `S01` `M` `native/package-layout.json`
- `S01` `M` `native/interpreter/bootstrap.py`
- `S01` `M` `native/application/src/package.rs`
- `S01` `M` `native/application/tests/application.rs`
- `S01` `M` `dev/docs/terminology/cli_projection.py`
- `S01` `verify:` `pytest dev/packaging docs staging, delegated inventory, installation, layout entrypoints (79 passed, 2 skipped)` -> `pass`
- `S01` `verify:` `cargo test application crate via CTest application.rust` -> `pass`
- `S01` `verify:` `real python.exe --check-package with delegated docs, tamper and unlisted falsifiers` -> `pass`
- `S01` `verify:` `CADRUMO-BUILD-RUNTIME verify-package docs-off Release ZIP` -> `pass`
- `S01` `verify:` `cmake desktop-host-build full four-language docs build` -> `fail`
- `S01` `by:` `orchestrator`
- `S01` `M` `dev/packaging/native/docs_build.py`
- `S01` `M` `dev/packaging/tests/test_native_docs_staging.py`
- `S01` `verify:` `pytest test_native_docs_staging.py (15 passed) and ruff, format, ty` -> `pass`

## Notes

- `S02` Live tests used build 1761 Release acceptance package (2026-10-03) relocated to scratch with current src/cadrumo overlaid on site-packages; no current package could be built. Launch carries no new fields until Group B consumers land (orchestrator ruling A).
- `S03` docs-build recipe not run to completion: the full build refuses at the cli-sequence gate on the stale shared .authority (pre-existing; reproduced on the web flavor without S03 involvement)
- `S03` `test_docs_build.py:` `test_a_changed_source_check_builds_the_stub_its_build_generates` (stale authority) and `test_docs_build_directory_contains_only_canonical_html` (doctrees, locale-logs left in the shared build root on 2026-10-03/04 by other runs) fail pre-existing
- `S02` Added the plan's `channel_interceptor` (shell/channel.rs) and a table-driven dispatcher token test after first logging; tauri test feature added as a dev-dependency for mock-runtime tests.
- `S01` S01 stays open: en refuses at the stale-authority sequence gate; no-op rebuild, touch-rebuild, Release docs bundle and runtime rendering unproven until one full docs build succeeds
- `S01` Committed jointly with CADRUMO-BUILD-RUNTIME's console entrypoint change in a87038dd6d; `cli_projection` stale-import fix in 233a8c2e33
