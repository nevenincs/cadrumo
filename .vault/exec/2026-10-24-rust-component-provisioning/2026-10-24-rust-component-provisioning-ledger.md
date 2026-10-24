---
tags:
  - '#exec'
  - '#rust-component-provisioning'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:2a74b757071993ef34126947be4836e75877ffaf2db507c2e34a397dfd58c17c'
related:
  - "[[2026-10-24-rust-component-provisioning-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `rust-component-provisioning` ledger

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

- `S01` `A` `src/cadrumo/_data/dependencies/local_ai_models.toml`
- `S01` `A` `src/cadrumo/_data/dependencies/local_ai_program.toml`
- `S01` `M` `src/cadrumo/_data/dependencies/browser_archives.toml`
- `S01` `A` `src/cadrumo/core/local_ai_pins.py`
- `S01` `M` `src/cadrumo/core/model_catalogue.py`
- `S01` `A` `src/cadrumo/core/tests/test_local_ai_pins.py`
- `S01` `M` `src/cadrumo/application/browser_archive_pins.py`
- `S01` `M` `src/cadrumo/application/tests/test_browser_archive_pins.py`
- `S01` `M` `src/cadrumo/application/tests/test_provisioning_browser_item.py`
- `S01` `M` `dev/env/browser_archive_pins.py`
- `S01` `A` `dev/env/local_ai_pins.py`
- `S01` `A` `dev/env/tests/test_local_ai_pins.py`
- `S01` `M` `dev/packaging/tests/test_native_layout_entrypoints.py`
- `S01` `M` `justfile`
- `S01` `M` `native/package-layout.json`
- `S01` `M` `native/platforms/linux-aarch64.json`
- `S01` `M` `native/platforms/linux-x86-64.json`
- `S01` `M` `native/platforms/macos-arm64.json`
- `S01` `M` `native/application/Cargo.toml`
- `S01` `M` `native/application/Cargo.lock`
- `S01` `M` `native/application/src/lib.rs`
- `S01` `M` `native/application/src/value.rs`
- `S01` `M` `native/application/src/filesystem.rs`
- `S01` `A` `native/application/src/provisioning/mod.rs`
- `S01` `A` `native/application/src/provisioning/pins.rs`
- `S01` `A` `native/application/src/provisioning/url.rs`
- `S01` `M` `native/desktop/src-tauri/Cargo.lock`
- `S01` `M` `native/installer/Cargo.lock`
- `S01` `M` `native/launch_guard/Cargo.lock`
- `S01` `M` `native/manager/Cargo.lock`
- `S01` `M` `native/interpreter_host/Cargo.lock`
- `S01` `verify:` `uv run --no-sync pytest -q -p no:cacheprovider pins catalogue layout coverage (128 tests)` -> `pass`
- `S01` `verify:` `cargo test --offline --no-fail-fast --manifest-path native/application/Cargo.toml (lib 42)` -> `pass`
- `S01` `verify:` `cargo test --test package_inspection linked_root_and_deep_root_ancestor_are_refused` -> `fail`
- `S01` `verify:` `cargo clippy --all-targets -- -D warnings` -> `pass`
- `S01` `verify:` `cargo fmt -- --check` -> `pass`
- `S01` `verify:` `cargo deny check advisories bans licenses sources` -> `pass`
- `S01` `verify:` `ruff check and format plus ty check on touched files` -> `pass`
- `S01` `verify:` `just check-operation-contract-manifest` -> `pass`
- `S01` `verify:` `python -m dev.env.local_ai_pins --check` -> `pass`
- `S01` `by:` `high-implementation-engineer`
- `S02` `M` `native/application/src/component.rs`
- `S02` `A` `native/application/src/provisioning/transfer.rs`
- `S02` `A` `native/application/src/provisioning/connection.rs`
- `S02` `A` `native/application/src/provisioning/http.rs`
- `S02` `A` `native/application/src/provisioning/proxy.rs`
- `S02` `A` `native/application/src/provisioning/failure.rs`
- `S02` `A` `native/application/src/provisioning/test_servers.rs`
- `S02` `M` `native/application/src/provisioning/mod.rs`
- `S02` `M` `native/application/src/error/mod.rs`
- `S02` `M` `native/application/src/installation.rs`
- `S02` `M` `native/application/src/lib.rs`
- `S02` `M` `native/application/tests/application.rs`
- `S02` `M` `native/application/Cargo.toml`
- `S02` `M` `native/application/Cargo.lock`
- `S02` `M` `native/desktop/src-tauri/Cargo.lock`
- `S02` `M` `native/installer/Cargo.lock`
- `S02` `M` `native/launch_guard/Cargo.lock`
- `S02` `M` `native/manager/Cargo.lock`
- `S02` `M` `native/interpreter_host/Cargo.lock`
- `S02` `verify:` `cargo test --offline --no-fail-fast --manifest-path native/application/Cargo.toml (lib 68, application 25)` -> `pass`
- `S02` `verify:` `cargo test --test package_inspection linked_root_and_deep_root_ancestor_are_refused` -> `fail`
- `S02` `verify:` `cargo clippy --all-targets -- -D warnings` -> `pass`
- `S02` `verify:` `cargo clippy --all-targets --features platform -- -D warnings` -> `pass`
- `S02` `verify:` `cargo fmt -- --check` -> `pass`
- `S02` `verify:` `cargo deny check advisories bans licenses sources` -> `pass`
- `S02` `by:` `high-implementation-engineer`

## Notes

- `S01` `package_inspection` junction fixture fails creating a junction whose path holds non-ASCII text through cmd.exe; unrelated to this change
- `S01` PackageInputs.cmake unchanged: the pins live under src/, which `cadrumo_source_inputs` already globs into the wheel inputs; the layout's `component_pins` path locates them for Rust
- `S01` lint-imports: 1 broken contract from a concurrent session's `cadrumo.tests.llm_vision_evidence_support` edit, unrelated
- `S02` `package_inspection` junction fixture failure is the same pre-existing non-ASCII junction path issue as S01
- `S02` ureq removed: the transfer and preflight need stage-exact classification and a proxy address that never reaches a third-party Debug or log, so the engine speaks HTTP/1.1 over rustls itself; rustls and webpki-roots were already in the graph and ring is a dev-dependency for the in-test certificate
