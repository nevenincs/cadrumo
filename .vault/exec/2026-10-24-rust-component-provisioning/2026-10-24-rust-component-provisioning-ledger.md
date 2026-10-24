---
tags:
  - '#exec'
  - '#rust-component-provisioning'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:c1a6fd6a0d9978dcf6b72e26c5658ed55468f31bf4d32abecda7639af7691103'
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
- `S03` `A` `native/application/src/provisioning/network.rs`
- `S03` `M` `native/application/src/provisioning/mod.rs`
- `S03` `M` `native/application-environment.toml`
- `S03` `verify:` `cargo test --offline --manifest-path native/application/Cargo.toml --lib (74, network 6)` -> `pass`
- `S03` `verify:` `cargo clippy --all-targets -- -D warnings` -> `pass`
- `S03` `verify:` `cargo fmt -- --check` -> `pass`
- `S03` `verify:` `pytest dev/packaging/native/tests/test_application_environment.py test_file_contract_json_and_contract_rs_agree[linux-x86-64]` -> `fail`
- `S03` `by:` `high-implementation-engineer`
- `S04` `A` `native/application/src/provisioning/items.rs`
- `S04` `A` `native/application/src/provisioning/state.rs`
- `S04` `A` `native/application/src/provisioning/plan.rs`
- `S04` `A` `native/application/src/provisioning/activity.rs`
- `S04` `A` `native/application/src/provisioning/receipts.rs`
- `S04` `M` `native/application/src/provisioning/mod.rs`
- `S04` `A` `native/application/src/canonical_json.rs`
- `S04` `M` `native/application/src/person_operations.rs`
- `S04` `M` `native/application/src/lib.rs`
- `S04` `M` `native/application/src/filesystem.rs`
- `S04` `M` `native/application/src/component.rs`
- `S04` `verify:` `cargo test --offline --no-fail-fast --manifest-path native/application/Cargo.toml (lib 94, application 25, installation 22)` -> `pass`
- `S04` `verify:` `cargo test --test package_inspection linked_root_and_deep_root_ancestor_are_refused` -> `fail`
- `S04` `verify:` `cargo test --lib --features platform person_operations (28)` -> `pass`
- `S04` `verify:` `cargo clippy --all-targets -- -D warnings` -> `pass`
- `S04` `verify:` `cargo clippy --all-targets --features platform -- -D warnings` -> `pass`
- `S04` `verify:` `cargo fmt -- --check` -> `pass`
- `S04` `by:` `high-implementation-engineer`
- `S16` `A` `src/cadrumo/application/dependency_withdrawal.py`
- `S16` `M` `src/cadrumo/application/dependency_setup_operation.py`
- `S16` `M` `src/cadrumo/application/local_reader_operation.py`
- `S16` `M` `src/cadrumo/entrypoints/dependency_operation_composition.py`
- `S16` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S16` `A` `src/cadrumo/entrypoints/tests/test_python_provisioning_withdrawn.py`
- `S16` `M` `src/cadrumo/entrypoints/tests/test_dependency_setup_operation.py`
- `S16` `M` `src/cadrumo/entrypoints/tests/test_dependency_quick_check_bound.py`
- `S16` `M` `src/cadrumo/application/tests/test_local_reader_operation_access.py`
- `S16` `verify:` `withdrawal, setup operation, quick check, local reader access, registry conformance, wording, contracts, CLI provision parity, MCP progress relay, session hold, local reader operation, operation composition pytest (221)` -> `pass`
- `S16` `verify:` `ruff, ty, lint-imports (30 kept), check-operation-contract-manifest` -> `pass`
- `S16` `M` `src/cadrumo/application/dependency_registry.py`
- `S16` `M` `src/cadrumo/application/dependency_withdrawal.py`
- `S16` `M` `src/cadrumo/entrypoints/tests/test_python_provisioning_withdrawn.py`
- `S16` `M` `src/cadrumo_runtime/adapters/worker_authorization.py`
- `S16` `M` `src/cadrumo_runtime/host/tests/test_runtime_server_start_authority.py`
- `S16` `M` `src/cadrumo_runtime/host/tests/frontend/core/adapters/outbound/model_runtime/tests/test_runtime_server_containment.py`
- `S16` `verify:` `withdrawal, setup, access, conformance, contracts, provision parity, MCP relay, session hold, server start authority, local reader operation, operation composition pytest (222)` -> `pass`
- `S16` `verify:` `runtime server containment pytest (6)` -> `pass`
- `S16` `verify:` `ruff, ty, lint-imports (30 kept)` -> `pass`

## Notes

- `S01` `package_inspection` junction fixture fails creating a junction whose path holds non-ASCII text through cmd.exe; unrelated to this change
- `S01` PackageInputs.cmake unchanged: the pins live under src/, which `cadrumo_source_inputs` already globs into the wheel inputs; the layout's `component_pins` path locates them for Rust
- `S01` lint-imports: 1 broken contract from a concurrent session's `cadrumo.tests.llm_vision_evidence_support` edit, unrelated
- `S02` `package_inspection` junction fixture failure is the same pre-existing non-ASCII junction path issue as S01
- `S02` ureq removed: the transfer and preflight need stage-exact classification and a proxy address that never reaches a third-party Debug or log, so the engine speaks HTTP/1.1 over rustls itself; rustls and webpki-roots were already in the graph and ring is a dev-dependency for the in-test certificate
- `S03` `test_file_contract_json_and_contract_rs_agree[linux-x86-64]` fails on the Linux desktop dependency evidence in `dev/packaging/native/linux_desktop_runtime.py;` all four recorded digests (desktop Cargo.lock and Cargo.toml, application and platform Cargo.toml) were already stale before S01, and S01/S02 add application Cargo.toml and desktop lock drift (toml, rustls, webpki-roots; ureq leaves the application, the desktop keeps its loopback-only ureq without TLS); no native sys crate changed; the refresh needs the evidence owner's review of every drifted input
- `S04` plan digest checked against the product's `dependency_plan_digest` for the same plan (df55d305...)
- `S04` canonical JSON writer moved out of `person_operations` into `canonical_json` so the ungated plan digest and the relay share one spelling
- `S04` free space is measured by the host and passed in: the crate forbids unsafe code and no safe volume query is in its graph; an unmeasured volume is never enough
- `S04` `package_inspection` junction fixture failure is the pre-existing non-ASCII junction path issue
- `S16` Owner ruling 2026-10-24: Python must not provision; the Python path is withdrawn now, ahead of its P05.S14 deletion. Setup is unavailable on every surface until the components role lands; status still names what is missing. The local AI quick check takes about 1.1 s warm and 2.2 s cold with or without withdrawal, near its 2 s bound (pre-existing).
- `S16` review correction withdrawn-full-check-relabelled: a registry without full checks answers a full request with its quick check and labels the rows quick; review correction runtime-owner-start-residual: the runtime admits no operation's request to start the local model program
