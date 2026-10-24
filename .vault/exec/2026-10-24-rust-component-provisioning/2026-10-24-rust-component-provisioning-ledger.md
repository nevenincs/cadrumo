---
tags:
  - '#exec'
  - '#rust-component-provisioning'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:2517bebb1cc6e4d6d282194892c1ba2833a8ab890556eee9d6af2dd54aefd0a7'
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
- `S02` `M` `native/application/src/provisioning/transfer.rs`
- `S02` `M` `native/application/src/provisioning/http.rs`
- `S02` `M` `native/application/src/provisioning/connection.rs`
- `S02` `M` `native/application/src/provisioning/network.rs`
- `S02` `verify:` `cargo test --no-fail-fast (lib 100 passed; package_inspection linked_root_and_deep_root_ancestor_are_refused pre-existing non-ASCII junction failure)` -> `pass`
- `S02` `verify:` `cargo clippy --all-targets -- -D warnings` -> `pass`
- `S02` `verify:` `cargo clippy --all-targets --features platform -- -D warnings` -> `pass`
- `S02` `verify:` `rustfmt --edition 2024 --check src/provisioning/*.rs` -> `pass`
- `S02` `by:` `implementation-engineer-high`
- `S04` `M` `native/application/src/provisioning/activity.rs`
- `S04` `M` `native/application/src/provisioning/state.rs`
- `S04` `M` `native/application/src/provisioning/receipts.rs`
- `S04` `verify:` `cargo test --no-fail-fast (lib 104 passed; package_inspection linked_root_and_deep_root_ancestor_are_refused pre-existing non-ASCII junction failure)` -> `pass`
- `S04` `verify:` `cargo clippy --all-targets -- -D warnings` -> `pass`
- `S04` `verify:` `cargo clippy --all-targets --features platform -- -D warnings` -> `pass`
- `S04` `verify:` `rustfmt --edition 2024 --check src/provisioning/*.rs` -> `pass`
- `S04` `by:` `implementation-engineer-high`
- `S01` `A` `dev/env/local_ai_model_pins.py`
- `S01` `M` `dev/env/local_ai_pins.py`
- `S01` `A` `dev/env/tests/test_local_ai_model_pins.py`
- `S01` `A` `dev/env/tests/data/ollama_manifests/moondream_1.8b.json`
- `S01` `A` `dev/env/tests/data/ollama_manifests/qwen2.5_3b.json`
- `S01` `A` `dev/env/tests/data/ollama_manifests/qwen2.5vl_3b.json`
- `S01` `A` `dev/env/tests/data/ollama_manifests/qwen2.5vl_7b.json`
- `S01` `A` `dev/env/tests/data/ollama_manifests/qwen3-vl_2b.json`
- `S01` `A` `dev/env/tests/data/ollama_manifests/qwen3_1.7b.json`
- `S01` `M` `src/cadrumo/_data/dependencies/local_ai_models.toml`
- `S01` `M` `native/application/src/provisioning/pins.rs`
- `S01` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.json`
- `S01` `verify:` `just pin-local-ai --check` -> `pass`
- `S01` `verify:` `uv run --no-sync python -m dev.env.local_ai_pins --only models (registry manifests re-derived every committed digest and size unchanged)` -> `pass`
- `S01` `verify:` `pytest dev/env/tests/test_local_ai_model_pins.py dev/env/tests/test_local_ai_pins.py src/cadrumo/core/tests/test_local_ai_pins.py src/cadrumo/core/tests/test_model_catalogue.py dev/packaging/tests/test_native_layout_entrypoints.py (76 passed)` -> `pass`
- `S01` `verify:` `pytest dev/quality/tests/test_import_load_worker.py (cadrumo target set stale on cadrumo.application.dependency_withdrawal, committed in c002a7769a outside this Step)` -> `fail`
- `S01` `verify:` `ruff check, ruff format --check, ty check on the touched dev files` -> `pass`
- `S01` `verify:` `lint-imports --config .importlinter --no-cache (30 kept)` -> `pass`
- `S01` `verify:` `cargo test --lib provisioning::pins (5 passed), cargo clippy --all-targets with and without --features platform -D warnings, rustfmt --check` -> `pass`
- `S01` `by:` `implementation-engineer-high`
- `S05` `A` `native/application/src/provisioning/browser.rs`
- `S05` `M` `native/application/src/provisioning/receipts.rs`
- `S05` `M` `native/application/src/provisioning/mod.rs`
- `S05` `verify:` `cargo test --offline --no-fail-fast on an export of HEAD plus this Step (lib 113, application 25, installation 22; package_inspection linked_root_and_deep_root_ancestor_are_refused pre-existing non-ASCII junction failure)` -> `pass`
- `S05` `verify:` `cargo test --lib --features platform provisioning::browser (9)` -> `pass`
- `S05` `verify:` `cargo clippy --all-targets -- -D warnings` -> `pass`
- `S05` `verify:` `cargo clippy --all-targets --features platform -- -D warnings` -> `pass`
- `S05` `verify:` `rustfmt --edition 2024 through stdin on browser.rs receipts.rs mod.rs` -> `pass`
- `S05` `by:` `implementation-engineer-high`
- `S07` `A` `native/application/src/provisioning/local_ai/mod.rs`
- `S07` `A` `native/application/src/provisioning/local_ai/loopback.rs`
- `S07` `A` `native/application/src/provisioning/local_ai/program.rs`
- `S07` `A` `native/application/src/provisioning/local_ai/program/tests.rs`
- `S07` `A` `native/application/src/provisioning/local_ai/fake_ollama.rs`
- `S07` `M` `native/application/src/provisioning/mod.rs`
- `S07` `M` `native/application/src/provisioning/pins.rs`
- `S07` `M` `native/application/src/provisioning/proxy.rs`
- `S07` `M` `native/application/src/component.rs`
- `S07` `M` `native/application/tests/application.rs`
- `S07` `M` `native/application/Cargo.toml`
- `S07` `M` `native/application/Cargo.lock`
- `S07` `M` `native/desktop/src-tauri/Cargo.lock`
- `S07` `M` `native/installer/Cargo.lock`
- `S07` `M` `native/interpreter_host/Cargo.lock`
- `S07` `M` `native/launch_guard/Cargo.lock`
- `S07` `M` `native/manager/Cargo.lock`
- `S07` `verify:` `cargo test --no-fail-fast (lib 125, application 25; package_inspection linked_root_and_deep_root_ancestor_are_refused pre-existing non-ASCII junction failure)` -> `pass`
- `S07` `verify:` `cargo clippy --all-targets -- -D warnings` -> `pass`
- `S07` `verify:` `cargo clippy --all-targets --features platform -- -D warnings` -> `pass`
- `S07` `verify:` `rustfmt --edition 2024 --check through stdin on the touched files` -> `pass`
- `S07` `verify:` `cargo deny --locked check advisories bans licenses sources (application, desktop, manager)` -> `pass`
- `S07` `by:` `implementation-engineer-high`

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
- `S02` review correction: transfer-source-fallback, retry-first-wait, http-unbounded-loops
- `S04` review correction: activity-finish-race, interrupted-hidden-by-observation, receipt-timestamp-interop, setup-selection-vs-button; a `not_in_this_build` block also outranks an interruption beside the hardware block, because Resume cannot change either
- `S01` review correction: model-pins-without-generator, browser-pin-source-hosts; the load-target inventories gain only this Step's modules `(dev.env.local_ai_model_pins,` plus `dev.env.local_ai_pins` and `cadrumo.core.local_ai_pins` that S01 left out); other sessions' uncommitted inventory lines stay uncommitted
- `S05` S05 completion marker read from the bundled driver 1.64.0-beta-1791568591000, lib/coreBundle.js: browserDirectoryToMarkerFilePath writes and reads `<build>/INSTALLATION_COMPLETE` (lines 33877-33878, 34056-34057); the out-of-process installer main() removes the build folder, extracts the zip, chmods the executable 0o755 and writes the empty marker last (33939-33951); downloadBrowserWithProgressBar skips a build whose marker exists (33724); launch checks only that the executable exists (executablePathOrDie, 34488-34494) and on win-x64 runs winldd PrintDeps.exe unless a fresh `DEPENDENCIES_VALIDATED` exists (34979-34995), which the engine never writes; .links entries (34887-34906) feed only the vendor's stale-build collection and are not written
- `S05` S05 component.rs is being reworked by the parallel local AI lane, so the bounded zip extraction is a browser-local copy of its rules rather than a shared factoring; verification ran on an index export because that lane's uncommitted `local_ai` files do not compile yet
- `S07` S07 archive bounds measured on the 0.40.10 archives by streaming each through its decompressor (zip central directory by range request) and summing members, links counted at their target's size: win 2230768655 B/80, linux-x64 5001030082 B/80, linux-arm64 3819535364 B/51, mac 610445869 B/59; bound is 6x the pinned download and 1024 members
- `S07` S07 the Linux and macOS archives carry 28, 17 and 10 symbolic links for versioned libraries; extraction creates no link: each link that resolves inside the archive to a regular file is placed as a hard link of that file, and any other link is refused
- `S07` S07 the server inherits the engine's containment: a crash ends it only where the owner hosts the engine in a kill-on-close job (the crate forbids unsafe and has no job API); an orderly stop unloads models, then ends the server
