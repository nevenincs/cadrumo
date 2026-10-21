# Rust native crates and their build

There is no Cargo workspace. `native/application`, `manager`, `installer`, `launch_guard`, `platform` and the Tauri crate in `native/desktop/src-tauri` each have their own manifest and `Cargo.lock`.

- **`cadrumo-application`** is a library with no binary: package verification, version discovery, publication state and child processes. Its `platform` feature pulls in `cadrumo-platform`.
- **`cadrumo-platform`** is the sole owner of storage-root, launch-profile and child-environment policy. It exposes a fixed-width C ABI: an `rlib` from Cargo, and a `staticlib` and `cdylib` built by CMake.
- **`cadrumo-manager`** is the per-user runtime manager binary.
- **`cadrumo-installer`** is a `cdylib`/`rlib` of MSI custom-action exports plus the `cadrumo-msi-maintenance` runner. Its manifest is not platform-gated; `lib.rs` gates the MSI modules to Windows and CMake builds the target only on Windows.
- **`cadrumo-launch-guard`** is a C-ABI `staticlib`.
- **Interpreter hosts:** the hosts in `native/interpreter` (`posix/host.c`, `windows/host.c`, bridge `python.c`) are C and link the platform and launch-guard static libraries.
- **Desktop crate:** consumes application, platform and installer, and on Windows also `cadrumo-manager`.

[manager](../../../../native/manager/Cargo.toml#L16), [platform](../../../../native/platform/Cargo.toml#L8), [desktop](../../../../native/desktop/src-tauri/Cargo.toml#L23), [installer gates](../../../../native/installer/src/lib.rs#L3).

CMake owns every Rust build, and Cargo owns dependency freshness.

- **Toolchain:** `rust` in `native/toolchain.json` (1.96.0, with per-target triples) is a floor; any newer release is admitted. There is no `rust-toolchain.toml` or `.cargo` config, and manifests state only `rust-version = "1.96"`.
- **Toolchain resolution:** `RustToolchain.cmake` is shared by every host. An explicit `CADRUMO_RUST_ROOT` wins; when it is empty, `rustup which rustc` resolves the active toolchain once and caches it. It then compares `rustc --version` with the floor.
- **Cargo wrapper:** `cadrumo_cargo_command` wraps each call with `RUSTC`, `RUSTDOC`, `CARGO_TARGET_DIR` and linker settings. `CARGO_TARGET_DIR` is `cargo/native` in the binary directory; the installer uses `cargo/installer`. Targets run `cargo build --locked --target <triple> --profile dev|release`.
- **Windows toolchain environment:** adds `RUSTFLAGS=-C target-feature=+crt-static`, `LIB` and `INCLUDE`, and passes `CMAKE_LINKER` straight to Cargo. POSIX goes through linker admission.
- **Targets:** `rust_application` and `rust_manager` build with ALL; `rust_platform`, `rust_launch_guard` and `rust_installer` build on request, the installer only on Windows.
- **Generated contract:** `native_contract` generates `contract.rs`, `.h` and `.json`. Platform and manager read it through `CADRUMO_CONTRACT_RS` with `include!(env!(...))`, so a bare `cargo` invocation fails to compile. The launch guard's `build.rs` reads `CADRUMO_NATIVE_CONTRACT`.
- **CTest cases:**
  - `application.rust` and `application.package` (900 s, `RESOURCE_LOCK package_inventory`);
  - `manager.rust` and `manager.supervision` (`--test-threads=1`);
  - `installer.rust` (Windows);
  - `launch_guard.rust` and `launch_guard.<host>`;
  - `platform.resolver` on both families, plus `platform.linker_contract` and `platform.invocation` on POSIX, and `platform.static`, `platform.dll` and `platform.rust` on Windows.
- **Recipes and clippy:** no `just` recipe runs cargo, clippy or rustfmt. Reach a single target with `just build-native <Config> <target>`. Clippy runs as the CMake targets `check_manager_lifecycle`, `check_installer` (warnings denied) and the desktop project's `desktop-host-clippy`.

[toolchain](../../../../native/toolchain.json#L2), [resolution](../../../../native/cmake/RustToolchain.cmake#L1), [Rust.cmake](../../../../native/cmake/Rust.cmake#L3), [Windows env](../../../../native/cmake/platforms/Windows.cmake#L58), [manager targets](../../../../native/cmake/Manager.cmake#L48), [installer targets](../../../../native/cmake/Installer.cmake#L21), [application tests](../../../../native/application/CMakeLists.txt#L49), [platform tests](../../../../native/cmake/platforms/Windows.cmake#L202), [recipe](../../../../justfile#L683).

The platform crate composes every packaged image's process environment from the generated contract. That contract is compiled from `native/application-environment.toml`.

- `launch::select` picks a launch profile from the image and its exact arguments.
- `define_environment` admits only the profile's base groups, operator groups, pins and slots, then removes every name the profile does not admit.
- `prepared_environment` returns that environment and creates its pinned directories without starting Python or changing the calling process. The desktop shell calls it to launch packaged children.
- The declaration, its profiles and the conformance checks are covered in [the environment contract reference](environment-contract.md).

[select](../../../../native/platform/src/launch.rs#L213), [define](../../../../native/platform/src/launch.rs#L332), [filter](../../../../native/platform/src/launch.rs#L430), [prepared](../../../../native/platform/src/lib.rs#L177), [desktop caller](../../../../native/desktop/src-tauri/src/environment.rs#L248), [cleared names](../../../../native/platform/src/storage.rs#L600).

The manager supervises the packaged runtime host. It starts `bin/cadrumo-runtime` with `--storage-root`, `--storage-identity`, `--expected-version` and `--supervised`.

- **Supervisor:** a state machine with readiness and heartbeat bounds, bounded drain and termination, and a restart policy that backs off to 60 s and allows a bounded number of restarts per 600 s window.
- **Adoption:** an existing owner is adopted only when its boot record matches pid, creation time and session, and its image matches the installed runtime. Otherwise it is reported foreign and never stopped.
- **Ownership:** a session mutex, a per-user start claim and a Quit marker.
- **Windows IPC:** a named pipe with a closed request grammar. The peer is checked for session, SID, image and liveness.
- **Cutover:** starts a designated successor that must reach an authenticated acknowledgement before the hand-over commits.
- **No launch-context refusal on start:** elevation, Session 0 and a missing desktop do not stop the manager. The tray and the startup-failure dialog appear only when a desktop is available. Recovery follows the process lifetime rather than the session's connection state.
- **Platforms:** only Windows has a run path. Elsewhere `main` writes `manager_platform_unavailable` and exits with the startup-failure code. These are source-level controls; containment and race behaviour need OS-level testing.

[launch](../../../../native/manager/src/supervision/launch.rs#L141), [non-Windows exit](../../../../native/manager/src/main.rs#L59), [supervisor](../../../../native/manager/src/supervision/supervisor.rs#L39), [restart policy](../../../../native/manager/src/supervision/restart.rs#L38), [ownership](../../../../native/CONTRACT.md#L1674), [startup contract](../../../../native/CONTRACT.md#L1731), [peer check](../../../../native/manager/src/ipc/windows.rs#L246).

The installer runner reads a verified plan and drives an MSI transaction.

- It checks artifact digests and admits ownership and scope.
- An owner pipe authenticates `msiexec`, and read-only Restart Manager checks look for files in use.
- It installs the version and registration MSIs, then records publication after commit.
- `unregister` and `remove-version` are separate maintenance operations.

The launch guard takes the package's removal lease before CPython loads, and grants removal exclusion only.

The C hosts refuse `LD_*`/`DYLD_*` on POSIX and restrict DLL search on Windows. They load the pinned CPython and the bridge, then call `cadrumo_python_main`. That function refuses any CPython other than the generated pin before an isolated start and Python bootstrap.

[runner](../../../../native/installer/src/runner.rs#L31), [Restart Manager](../../../../native/installer/src/windows.rs#L1), [launch guard](../../../../native/launch_guard/src/lib.rs#L14), [POSIX host](../../../../native/interpreter/posix/host.c#L52), [Windows host](../../../../native/interpreter/windows/host.c#L87), [bridge](../../../../native/interpreter/python.c#L33).

Scoped observations needing a check against current code:

- **Elevation vocabulary:** adoption no longer rejects an elevated runtime, and no production emitter of the runtime's elevated-token exit was found. `ForeignReason::Elevated` (marked historical) and the `ElevatedTokenRefused` exit and stand-down reasons remain in the vocabulary, so a reader can mistake them for a live refusal. The governing text is the runtime lifecycle policy in [the local runtime reference](04-external-integrations-and-local-runtime.md).
- **POSIX custody clear:** it compares the identity of two no-follow opens, then unlinks by name, which leaves a window between the second open and the unlink.
- **Exit code 1:** the exit classifier counts code 1 as a launch failure, while the Windows supervision module names 1 as the forced-termination code.
- **Abort profiles:** the platform manifest's `panic = "abort"` profiles apply only when it is the root package.

[adoption](../../../../native/manager/src/supervision/adoption.rs#L47), [stand-down](../../../../native/manager/src/supervision/supervisor.rs#L360), [clear](../../../../native/manager/src/custody/posix.rs#L193), [exit codes](../../../../native/manager/src/supervision/exit.rs#L15), [termination code](../../../../native/manager/src/supervision/windows.rs#L42), [profiles](../../../../native/platform/Cargo.toml#L10).

## Working notes

- Path, storage-root, launch-profile and environment policy lives only in `native/platform`, driven by `native/application-environment.toml`. The `contract.*` files are generated, never hand-authored. [declaration](../../../../native/CONTRACT.md#L114), [generated](../../../../native/CONTRACT.md#L240)
- The application `.rlib` is not a runtime file. `fixture-test-mode` is refused in release builds. [statement](../../../../native/CONTRACT.md#L149), [guard](../../../../native/manager/src/lib.rs#L5)
- Gated tests:
  - `supervision.rs` is Windows-only.
  - `custody_conformance` needs `CADRUMO_TEST_PYTHON`.
  - The installer kit test is `#[ignore]`.
  - Window smoke needs an interactive logon.
  - `live-package-tests` runs as `application.package`, while `live-python-tests` has no CMake wiring.

  [supervision](../../../../native/manager/tests/supervision.rs#L6), [custody](../../../../native/manager/tests/custody_conformance.rs#L118), [package test](../../../../native/application/CMakeLists.txt#L59), [smoke](../../../../native/CONTRACT.md#L1556)
- Login start: MSI authoring writes a per-scope `Run` value that launches the manager with `--sign-in`. Linux and macOS packaging add no services or automatic launch. [Run](../../../../dev/packaging/native/windows_msi.py#L252), [no services](../../../../native/CONTRACT.md#L2027)
