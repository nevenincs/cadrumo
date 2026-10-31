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
body_hash: 'sha256:bb80b651af18e7ff464d18d1347a3beb5a9fb7f7bca52dd6f158c265b1fa68b5'
---

# `macos-platform` plan

## Description

Approved 2026-10-30. Basis: the user pre-approved plans and ADRs for macOS bring-up and directed that the accepted architecture be implemented for macOS arm64 without new ADRs unless necessary.

Bring Cadrumo to a working build, package and run on macOS arm64: configure and compile the native graph, repair platform-dependent Python failures, enable the desktop shell, assemble the payload and author the application wrapper and DMG. Decision coverage: the darwin transport ADR governs socket placement (S04, S05); the desktop-shell, runtime-manager and packaging-interpreter ADRs govern the shell, manager and payload (S02, S04, S05); the darwin versioned-installation ADR is proposed and its scoped PKG, receipt and LaunchAgent stages stay outside this plan, which delivers the existing DragNDrop DMG with an unsigned or ad-hoc signed bundle (S06, S07). Signing and notarization need certificates that are not available here.

## Steps

- [ ] `S01` - Admit the macOS configure path: case-insensitive build-path guards and a developer recipe that resolves the reviewed Apple clang, SDK, Rust root and Darwin assembly tools as explicit cache inputs; `native/cmake/BuildPaths.cmake, native/cmake/BinaryDirectory.cmake, native/cmake/BuildLog.cmake, justfile, native/CONTRACT.md`.
- [x] `S02` - Compile the native backend (platform, launch guard, manager, application crates and the C interpreter host/bridge) for aarch64-apple-darwin and pass its CTest cases; `native/platform, native/launch_guard, native/manager, native/application, native/interpreter, native/interpreter_host, native/cmake/platforms`.
- [ ] `S03` - Repair macOS-specific Python suite failures (paths, sockets, locking, process and platform branches) found by the baseline run; `src/, dev/, tests under owning packages`.
- [ ] `S04` - Enable the desktop shell on macOS: GUI availability, a per-user single-instance lock in the Darwin transport namespace, and a Tauri build of the desktop host; `native/desktop/src-tauri/src/launch.rs, native/desktop/src-tauri/src/shell/single_instance, native/desktop/src-tauri/Cargo.toml`.
- [ ] `S05` - Assemble the full macOS payload: PBS CPython SDK, wheelhouse, agent runtime, Mach-O relocation and ad-hoc signing into the flat bundle; `native/cmake/Packaging.cmake, native/cmake/PythonDistribution.cmake, dev/packaging/native/platforms/macos.py, native/platforms/macos-arm64.json`.
- [ ] `S06` - Author the macOS application wrapper: .app bundle with Info.plist, icon and nested signed payload, packaged into the CPack DragNDrop DMG; `native/cmake/distribution/CMakeLists.txt, native/desktop/src-tauri, native/package-layout.json`.
- [ ] `S07` - Verify the assembled bundle and DMG on macOS: CTest verify and verify-package, launch the desktop app, runtime and CLI from the extracted bundle; `native/cmake/ReleaseVerification.cmake, native/tests`.
- [ ] `S08` - Add the POSIX runtime client for the desktop: a Unix-socket runtime transport beside the Windows pipe in the application and platform crates, then lift the macOS refusals in desktop app start, supervision, sign-in, agent launcher, terminal and process containment; `native/application/src/lib.rs, native/application/src/view_stream.rs, native/platform/src, native/desktop/src-tauri/src/app.rs, native/desktop/src-tauri/src/manager.rs, native/desktop/src-tauri/src/shell, native/desktop/src-tauri/src/agent`.
- [ ] `S09` - Remove the native Development-versus-Installed image classification so native storage resolution follows the environment-driven root alone, matching the Python storage owner, and let a Debug manager start against it; `native/platform/src/storage.rs, native/manager/src/main.rs, native/platform/src/conformance_tests.rs`.

## Parallelization

## Verification
