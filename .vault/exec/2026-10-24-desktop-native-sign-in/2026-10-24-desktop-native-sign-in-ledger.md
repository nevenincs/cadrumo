---
tags:
  - '#exec'
  - '#desktop-native-sign-in'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:e152068cc4480b8085910298e435c23dd8a389ffc880f1c7d3af860af4aa290c'
related:
  - "[[2026-10-24-desktop-native-sign-in-plan]]"
---

# `desktop-native-sign-in` ledger

## Changes

- `S01` `M` `native/application/src/runtime_client.rs`
- `S01` `M` `native/desktop/src-tauri/src/shell/sign_in/watch.rs`
- `S01` `M` `.vault/adr/2026-10-04-application-sign-in-adr.md`
- `S01` `M` `.vault/adr/2026-10-04-desktop-shell-adr.md`
- `S01` `verify:` `cargo test --features platform --lib runtime_client` -> `pass`
- `S01` `verify:` `cargo clippy --features platform --all-targets -D warnings` -> `pass`
- `S02` `A` `native/application/src/person_operations.rs`
- `S02` `M` `native/application/src/lib.rs`
- `S02` `verify:` `cargo test --features platform --lib person_operations` -> `pass`
- `S02` `verify:` `cargo clippy --features platform --all-targets -D warnings` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `M` `native/application/src/runtime_client.rs`
- `S03` `M` `native/desktop/src-tauri/src/agent/person.rs`
- `S03` `A` `native/desktop/src-tauri/src/agent/person/native.rs`
- `S03` `A` `native/desktop/src-tauri/src/agent/person/scripted.rs`
- `S03` `M` `native/desktop/src-tauri/src/shell/presentation.rs`
- `S03` `M` `native/desktop/src-tauri/src/shell/setup/mod.rs`
- `S03` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S03` `verify:` `cmake --build build/windows-x64 --config Debug --target desktop-host-unit-test` -> `pass`
- `S03` `verify:` `cmake --build build/windows-x64 --config Debug --target desktop-host-unit-clippy` -> `pass`
- `S04` `M` `native/application/src/runtime_client.rs`
- `S04` `M` `dev/runtime_lifecycle/native_client_live.py`
- `S04` `verify:` `CADRUMO_AUTHORITY_ROOT=build/windows-x64/product/build/source/.authority python -m dev.runtime_lifecycle.native_client_live (3 runs)` -> `pass`
- `S03` `M` `native/desktop/src-tauri/src/agent/person/native.rs`
- `S03` `verify:` `cmake --build build/windows-x64 --config Debug --target desktop-host-unit-test` -> `pass`
- `S03` `M` `native/application/src/person_operations.rs`
- `S03` `M` `.vault/adr/2026-10-04-application-sign-in-adr.md`
- `S03` `verify:` `cmake --build build/windows-x64 --config Debug --target desktop-host-unit-test` -> `pass`
- `S03` `verify:` `cmake --build build/windows-x64 --config Debug --target desktop-host-unit-clippy` -> `pass`

## Notes

- `S03` `runtime_client.rs` also carries the S04 live-test additions; non-Windows desktop compile not run on this host
- `S04` measured: password sign-in 244/504/244 ms, receipt resume 63/48/53 ms; a stored desktop sign-in is admitted only from the installed desktop image, so the packaged window's persisted sign-in is not exercised here
- `S03` review fix: a session the window releases no longer broadcasts Retired
- `S03` user ruling 2026-10-24 'lift': reply bound raised from 64 KiB to the relay's 16 MiB document bound
- `S03` plan-close review fixes (audit 2026-10-24-desktop-native-sign-in-audit); diagnostics finding deferred
