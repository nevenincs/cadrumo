---
tags:
  - '#plan'
  - '#macos-platform'
date: '2026-10-30'
tier: L1
related:
  - '[[2026-10-08-canonical-environment-darwin-transport-adr]]'
  - '[[2026-10-08-application-distribution-darwin-versioned-installation-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
modified: '2026-10-31'
body_schema: body-v2
body_hash: 'sha256:2e0088643dcc9976dbbf3461a1bf00eb8d6f89e2971959eccce6e1f302cca214'
---

# `macos-platform` plan

## Description

Approved 2026-10-30. Basis: the user pre-approved plans and ADRs for macOS bring-up and directed that the accepted architecture be implemented for macOS arm64 without new ADRs unless necessary.

Bring Cadrumo to a working build, package and run on macOS arm64: configure and compile the native graph, repair platform-dependent Python failures, enable the desktop shell, assemble the payload and author the application wrapper and DMG. Decision coverage: the darwin transport ADR governs socket placement (S04, S05); the desktop-shell, runtime-manager and packaging-interpreter ADRs govern the shell, manager and payload (S02, S04, S05); the darwin versioned-installation ADR is proposed and its scoped PKG, receipt and LaunchAgent stages stay outside this plan, which delivers the existing DragNDrop DMG with an unsigned or ad-hoc signed bundle (S06, S07). Signing and notarization need certificates that are not available here.

## Steps

- [x] `S01` - Admit the macOS configure path: case-insensitive build-path guards and a developer recipe that resolves the reviewed Apple clang, SDK, Rust root and Darwin assembly tools as explicit cache inputs; `native/cmake/BuildPaths.cmake, native/cmake/BinaryDirectory.cmake, native/cmake/BuildLog.cmake, justfile, native/CONTRACT.md`.
- [x] `S02` - Compile the native backend (platform, launch guard, manager, application crates and the C interpreter host/bridge) for aarch64-apple-darwin and pass its CTest cases; `native/platform, native/launch_guard, native/manager, native/application, native/interpreter, native/interpreter_host, native/cmake/platforms`.
- [x] `S03` - Repair macOS-specific Python suite failures (paths, sockets, locking, process and platform branches) found by the baseline run; `src/, dev/, tests under owning packages`.
- [x] `S04` - Enable the desktop shell on macOS: GUI availability, a per-user single-instance lock in the Darwin transport namespace, and a Tauri build of the desktop host; `native/desktop/src-tauri/src/launch.rs, native/desktop/src-tauri/src/shell/single_instance, native/desktop/src-tauri/Cargo.toml`.
- [x] `S05` - Assemble the full macOS payload: PBS CPython SDK, wheelhouse, agent runtime, Mach-O relocation and ad-hoc signing into the flat bundle; `native/cmake/Packaging.cmake, native/cmake/PythonDistribution.cmake, dev/packaging/native/platforms/macos.py, native/platforms/macos-arm64.json`.
- [x] `S06` - Author the macOS application wrapper: .app bundle with Info.plist, icon and nested signed payload, packaged into the CPack DragNDrop DMG; `native/cmake/distribution/CMakeLists.txt, native/desktop/src-tauri, native/package-layout.json`.
- [ ] `S07` - Verify the assembled bundle and DMG on macOS: CTest verify and verify-package, launch the desktop app, runtime and CLI from the extracted bundle; `native/cmake/ReleaseVerification.cmake, native/tests`.
- [x] `S08` - Add the POSIX runtime client for the desktop: a Unix-socket runtime transport beside the Windows pipe in the application and platform crates, then lift the macOS refusals in desktop app start, supervision, sign-in, agent launcher, terminal and process containment; `native/application/src/lib.rs, native/application/src/view_stream.rs, native/platform/src, native/desktop/src-tauri/src/app.rs, native/desktop/src-tauri/src/manager.rs, native/desktop/src-tauri/src/shell, native/desktop/src-tauri/src/agent`.
- [x] `S09` - Remove the native Development-versus-Installed image classification so native storage resolution follows the environment-driven root alone, matching the Python storage owner, and let a Debug manager start against it; `native/platform/src/storage.rs, native/manager/src/main.rs, native/platform/src/conformance_tests.rs`.
- [x] `S10` - Contain the supervised runtime when the macOS window host dies without a clean quit: bring the runtime's process group under the guardian or an equivalent kqueue-observed owner; `native/manager/src/supervision/launch.rs, native/platform/src`.
- [ ] `S11` - Render native macOS window chrome (traffic lights, no custom minimise/maximise/close) and correct the stale macOS contract wording, the interpreter executable path join and re-enable user docs in the payload; `native/desktop/frontend, native/desktop/src-tauri, native/CONTRACT.md, native/interpreter/posix/host.c`.
- [x] `S12` - Scope the desktop single-instance lock and the manager session lock and identifier by storage root on every host, so launches on different roots never hand off or contend and a standalone manager and desktop host on the same root recognise each other; admit an override root in Windows entry dispatch; amend the desktop-shell and runtime-manager decisions; `native/desktop/src-tauri/src/shell/single_instance, native/manager/src/main.rs, native/manager/src/macos/desktop_host.rs, native/manager/src/installation.rs, .vault/adr`.
- [ ] `S13` - Record every pre-log startup outcome (handoff, lock timeout, package refusal) durably and show its reason; align the relaunch wait with the shutdown and drain budget; treat a deterministic early runtime exit as terminal instead of retrying; `native/desktop/src-tauri/src/main.rs, native/desktop/src-tauri/src/startup_logging.rs, native/desktop/src-tauri/src/shell/single_instance, native/manager/src/supervision`.
- [ ] `S14` - Settle or durably record in-flight operations at quit so interrupted mutations stay UNKNOWN rather than lost, and stop logging session_unavailable as a failure on a normal quit; `native/desktop/src-tauri/src/app.rs, native/application/src/runtime_client.rs, src/cadrumo_runtime/host`.
- [ ] `S15` - Gate package sealing and the DMG on a runtime-role health check, rebuild the macOS bundle and DMG, and verify S10 containment and S11 window chrome (fullscreen inset, title-bar double-click, standard Window menu shortcuts) in the packaged app; `native/cmake/distribution/CMakeLists.txt, native/cmake/Packaging.cmake, native/desktop`.
- [ ] `S16` - Give native and Python tests an isolated transport namespace so they never write to the real per-user socket directory, and remove the stale test lock and socket files there; `native/platform/src, native/desktop/src-tauri/src/shell/single_instance, src/cadrumo_client/transport, native/manager/tests`.

## Parallelization

## Verification
