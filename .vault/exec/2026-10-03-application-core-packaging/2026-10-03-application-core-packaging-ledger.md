---
tags:
  - '#exec'
  - '#application-core-packaging'
date: '2026-10-03'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:8adb15cdc079bb206d36f5e5bd6650f09bcaa52059647fe49ee66a326b8f943d'
related:
  - "[[2026-10-03-application-core-packaging-plan]]"
---

# `application-core-packaging` ledger

## Changes

- `S01` `M` `.vault/plan/2026-10-03-application-core-packaging-plan.md`
- `S01` `verify:` `vaultspec-core status application-core-packaging` -> `pass`
- `S01` `verify:` `vaultspec-core check --feature application-core-packaging` -> `fail`
- `S06` `A` `native/application/Cargo.toml`
- `S06` `A` `native/application/Cargo.lock`
- `S06` `A` `native/application/src/lib.rs`
- `S06` `A` `native/application/src/value.rs`
- `S06` `A` `native/application/src/error.rs`
- `S06` `A` `native/application/src/filesystem.rs`
- `S06` `A` `native/application/src/package.rs`
- `S06` `A` `native/application/src/capability.rs`
- `S06` `A` `native/application/src/child.rs`
- `S06` `A` `native/application/src/component.rs`
- `S06` `A` `native/application/tests/application.rs`
- `S06` `M` `.vault/plan/2026-10-03-application-core-packaging-plan.md`
- `S06` `A` `.vault/audit/2026-10-03-application-core-packaging-audit.md`
- `S06` `verify:` `cargo test --locked --manifest-path native/application/Cargo.toml --target x86_64-pc-windows-msvc` -> `pass`
- `S06` `verify:` `cargo clippy --locked --manifest-path native/application/Cargo.toml --target x86_64-pc-windows-msvc --all-targets -- -D warnings` -> `pass`
- `S06` `verify:` `cargo fmt --manifest-path native/application/Cargo.toml -- --check` -> `pass`
- `S06` `verify:` `cargo build --locked --release --lib --manifest-path native/application/Cargo.toml --target x86_64-pc-windows-msvc` -> `pass`
- `S06` `verify:` `wsl -d Ubuntu -- bash /mnt/y/code/cadrumo-worktrees/tui/build/linux-x86-64/application-core/verify.sh` -> `fail`
- `S06` `verify:` `wsl -d Ubuntu -- bash /mnt/y/code/cadrumo-worktrees/tui/build/linux-x86-64/application-core/verify-native-filesystem.sh` -> `pass`
- `S06` `M` `.vault/index/application-core-packaging.index.md`
- `S06` `verify:` `vaultspec-core check --feature application-core-packaging` -> `pass`
- `S06` `verify:` `git diff --check -- native/application .vault/plan/2026-10-03-application-core-packaging-plan.md` -> `pass`
- `S09` `M` `native/application/Cargo.toml`
- `S09` `M` `native/application/Cargo.lock`
- `S09` `M` `native/application/src/component.rs`
- `S09` `M` `native/application/src/error.rs`
- `S09` `M` `native/application/src/lib.rs`
- `S09` `A` `native/application/src/binary.rs`
- `S09` `A` `native/application/src/python.rs`
- `S09` `A` `native/application/src/python_probe.py`
- `S09` `A` `native/application/tests/binary.rs`
- `S09` `A` `native/application/tests/live_python.rs`
- `S09` `A` `native/application/tests/live_package.rs`
- `S09` `M` `.vault/plan/2026-10-03-application-core-packaging-plan.md`
- `S09` `M` `.vault/audit/2026-10-03-application-core-packaging-audit.md`
- `S09` `verify:` `Windows Rust 1.96 cargo test (29 library/integration tests)` -> `pass`
- `S09` `verify:` `Linux x86_64 Rust 1.96 native-filesystem cargo test (31 tests)` -> `pass`
- `S09` `verify:` `Windows/Linux cargo clippy --all-targets -- -D warnings` -> `pass`
- `S09` `verify:` `Windows cargo clippy --all-targets --all-features -- -D warnings` -> `pass`
- `S09` `verify:` `cargo fmt --check` -> `pass`
- `S09` `verify:` `Windows cargo build --locked --release --lib` -> `pass`
- `S09` `verify:` `ruff check and format --check native/application/src/python_probe.py` -> `pass`
- `S09` `verify:` `Windows cargo test --release --features live-python-tests --test live_python; CPython3.13.11 MissingBuilds and version/distribution refusals` -> `pass`
- `S09` `verify:` `Initial relocated Windows Release package execution; CPython3.13.11 all80manifest distributions MissingDependency` -> `pass`
- `S09` `verify:` `Final Windows cargo test --locked --release --features live-package-tests --test live_package; original manifest+inventory unchanged, CPython3.13.11 all80distributions matched` -> `pass`
- `S10` `M` `native/CMakeLists.txt`
- `S10` `A` `native/cmake/Rust.cmake`
- `S10` `M` `native/cmake/platforms/Windows.cmake`
- `S10` `A` `native/application/CMakeLists.txt`
- `S10` `M` `native/cmake/Packaging.cmake`
- `S10` `M` `native/application/tests/live_package.rs`
- `S10` `M` `native/CONTRACT.md`
- `S10` `M` `.vault/plan/2026-10-03-application-core-packaging-plan.md`
- `S10` `M` `.vault/audit/2026-10-03-application-core-packaging-audit.md`
- `S10` `verify:` `CMake 4.4.3 isolated configure build/windows-x64/application-cmake` -> `pass`
- `S10` `verify:` `CMake Debug rust_application and rust_platform build` -> `pass`
- `S10` `verify:` `CMake Release rust_application and rust_platform build with explicit CC AR INCLUDE` -> `pass`
- `S10` `verify:` `Final CTest Debug -R ^application.rust$` -> `pass`
- `S10` `verify:` `Final CTest Release -R ^(application.|platform.) with prior extracted Release fixture; five CTests` -> `pass`
- `S10` `verify:` `Fresh CMake Release bundle; existing authority compiler refuses Modelo2322016-2017 bindings` -> `fail`
- `S10` `verify:` `Rust cargo fmt --check and clippy --all-targets --all-features -- -D warnings` -> `pass`
- `S10` `verify:` `Prior release manifest excludes rlibs Cargo manifests and dev packaging tooling` -> `pass`
- `S10` `verify:` `CMake build immediately after standalone CTest preserves artifact timestamp` -> `fail`
- `S10` `verify:` `Repeated identical CMake Release rust_application build preserves rlib timestamp and SHA256` -> `pass`
- `S10` `M` `native/application/CMakeLists.txt`
- `S10` `M` `dev/packaging/native/artifact_verify.py`
- `S10` `M` `dev/packaging/tests/test_native_artifact_identity.py`
- `S10` `verify:` `CMake configure with generated profile-specific artifact-probe JSON argv` -> `pass`
- `S10` `verify:` `pytest dev/packaging/tests/test_native_artifact_identity.py (4 tests including real subprocess failure and mutation)` -> `pass`
- `S10` `verify:` `Adjacent native storage/environment contract tests` -> `pass`
- `S10` `verify:` `Ruff check and format --check for changed Python files` -> `pass`
- `S10` `verify:` `Real artifact_verify with CMake-generated Release command and pinned prior ZIP; Python relocation plus Rust exact80distribution probe` -> `pass`
- `S10` `verify:` `Post-run archive and extracted manifest hash comparison against fixture locator` -> `pass`
- `S10` `verify:` `Fresh CMake Release bundle retry; existing Modelo2322016-2017 authority bindings refused` -> `fail`

## Notes

- `S01` Partial S01 only: recorded explicit execution authorization and current-source handoff assessment. Interpreter owner retains shared files; predecessor S02-S05 remain open and revised ZIP verification is in progress. No implementation or acceptance outputs changed. Dependent work awaits stable handoff.
- `S01` Feature validation reports one schema error: approved plan links proposed application-packaging ADR. S01 must reconcile and accept scoped decision coverage; execution authorization does not accept unrelated proposal clauses. No Step closed.
- `S06` User corrected ownership: standalone Rust work proceeds independently of Python packaging. S06 completed in its clarified scope; initial S07-S08 library implementation is included but shared integration and remaining acceptance stay open. No Python/platform/root CMake source changed.
- `S06` Pinned Rust 1.96.0 used through explicit toolchain executables; ambient X:/ci-shared cargo shim is unusable. Windows final 20 tests, Linux native-filesystem final 22 tests passed. One prior WSL shared-drive test failed with PermissionDenied and passed alone; retained in audit, not suppressed. Explicit Linux B is /tmp/cadrumo-application.QsWHTMDZ/build/linux-x86-64; workspace build/linux-x86-64/application-core/native-filesystem-tests.log records final results.
- `S06` Semantic discovery service was unavailable; used targeted supplied-owner reads and searches. Read-only independent review found and verified fixes for path aliases, mirror identity, damaged-version repair and directory-inclusive entry limits. Four-target package/Chromium/TLS success acceptance remains open.
- `S09` Partial S09/library-owned S07 checkpoint only; no step closure. Canonical platform projection, trusted browser metadata/acquisition, ARM/macOS execution and write tracing remain open.
- `S09` Initial live probe timed out due to missing stdin EOF; fixed with explicit drop and regression. Initial minimal test environment failed; disposable home/cache/temp projection fixed it.
- `S09` Release archive SHA256 be4eaf81eb2b254d2d535db69609efbe684bca9c790d0994609268fb39923b0b copied after matching source/copy/source hashes; isolated extraction locator build/windows-x86-64/application-core/live-package-dir.txt. Stronger original-manifest postcondition rerun is pending; final result will be appended to audit.
- `S09` Corrective independent review resolved dynamic-library/fat-header acceptance, EOF handling and live-test original-inventory comparison. No new production defect remains; no descendant containment or hostile same-user filesystem guarantee.
- `S09` Resolves the prior pending stronger package-immutability rerun. Archive identity and isolated extraction locator remain as recorded. S09 remains open for trusted acquisition metadata and complete Chromium provisioning.
- `S10` User explicitly authorizes shared CMake/package integration. Shared inputs were clean/committed before edits. S10 partial checkpoint only: capability projections and four-target acceptance remain open.
- `S10` Standalone CTest initially failed after pinning CC because it lacked SDK INCLUDE; adapter now projects pinned header directories. Final both configurations passed.
- `S10` Package CTest used the immutable prior Release archive SHA256 be4eaf81eb2b254d2d535db69609efbe684bca9c790d0994609268fb39923b0b via absolute `CADRUMO_APPLICATION_TEST_PACKAGE_ROOT;` canonical expected platform ABI and manifest location still come from current layout. This does not establish fresh bundle success.
- `S10` Fresh product/ready and stage/Release/ready were not produced. No registry validation guard bypass, registry source edits, or build-only rlib installation. S10 remains open.
- `S10` Cross-CTest/MSBuild Cargo rebuild behavior remains recorded; no cache fingerprint bypass. All final correctness tests passed.
- `S10` The live combined verifier used build/windows-x64/application-cmake/archive-fixture and prior ZIP SHA256 be4eaf81eb2b254d2d535db69609efbe684bca9c790d0994609268fb39923b0b. It is not a fresh source-build acceptance. result.json records `application_probe=passed.`
- `S10` The live process started before the final manifest recheck assertion was added; that assertion is covered by a real manifest-mutation regression and the successful post-run comparison against the original locator.
- `S10` Concurrent shared-branch merge commits captured the implementation during verification; source remains intact. This checkpoint records verification without rewriting those commits. No registry source changes or validation bypass. Full S10/S11 remain open.
