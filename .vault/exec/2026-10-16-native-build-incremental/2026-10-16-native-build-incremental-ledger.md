---
tags:
  - '#exec'
  - '#native-build-incremental'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:51981e2c84dac09d01dcced6ca72c5054f50bf0ea6352b2155fd62807696ed63'
related:
  - "[[2026-10-16-native-build-incremental-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `native-build-incremental` ledger

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

- `S01` `M` `dev/_paths.py`
- `S01` `M` `justfile`
- `S01` `M` `native/cmake/Bootstrap.cmake`
- `S01` `M` `native/cmake/BuildPaths.cmake`
- `S01` `D` `native/cmake/CleanBuilder.cmake`
- `S01` `M` `dev/packaging/native/cmake_build.py`
- `S01` `M` `src/cadrumo/core/storage_environment.py`
- `S01` `verify:` `cmake --preset windows-x64` -> `pass`
- `S01` `verify:` `focused storage builder cleanup tests 29` -> `pass`
- `S01` `verify:` `build storage and selected uv tests 8` -> `pass`
- `S01` `verify:` `changed parent Ruff and ty` -> `pass`
- `S02` `M` `dev/packaging/native/product.py`
- `S02` `M` `dev/packaging/native/agent.py`
- `S02` `M` `dev/packaging/native/agent_runtime.py`
- `S02` `M` `dev/packaging/wheel_metadata.py`
- `S02` `A` `dev/packaging/tests/test_wheel_install_currency.py`
- `S02` `A` `dev/packaging/native/tests/test_product_snapshot_links.py`
- `S02` `verify:` `producer fixtures 28 tests` -> `pass`
- `S02` `verify:` `authority and uv-selection 14 tests` -> `pass`
- `S02` `verify:` `snapshot links and real uv deletion currency 5 tests` -> `pass`
- `S02` `verify:` `scoped Ruff and ty` -> `pass`
- `S03` `M` `dev/packaging/native/assemble.py`
- `S03` `A` `dev/packaging/native/assembly_transaction.py`
- `S03` `M` `dev/packaging/native/stdlib.py`
- `S03` `M` `native/cmake/Packaging.cmake`
- `S03` `M` `native/desktop/tests/packaged/host.mjs`
- `S03` `verify:` `assembly platform and agent runtime focused tests 56` -> `pass`
- `S03` `verify:` `final authority reuse transactions 13` -> `pass`
- `S03` `verify:` `desktop snapshot tests 5` -> `pass`
- `S03` `verify:` `CPython3.13.15 bytecode executed on packaged3.13.11` -> `pass`
- `S03` `verify:` `scoped Ruff ty and Prettier` -> `pass`
- `S04` `A` `dev/packaging/native/build_directory.py`
- `S04` `M` `dev/packaging/native/cmake_build.py`
- `S04` `M` `dev/packaging/native/distribution_prepare.py`
- `S04` `M` `dev/packaging/native/installation.py`
- `S04` `A` `dev/packaging/native/installation_reuse.py`
- `S04` `M` `dev/packaging/native/package_launch_smoke.py`
- `S04` `A` `dev/packaging/native/tests/test_build_directory_admission.py`
- `S04` `M` `dev/packaging/native/tests/test_cmake_installer_flow.py`
- `S04` `M` `dev/packaging/native/tests/test_distribution_prepare.py`
- `S04` `M` `dev/packaging/native/tests/test_windows_msi.py`
- `S04` `A` `dev/packaging/native/tests/test_windows_msi_single.py`
- `S04` `M` `dev/packaging/native/windows_msi.py`
- `S04` `M` `dev/packaging/native/windows_msi_build.py`
- `S04` `M` `dev/packaging/native/windows_msi_database.py`
- `S04` `M` `dev/packaging/native/windows_msi_identity.py`
- `S04` `A` `dev/packaging/native/windows_msi_paths.py`
- `S04` `A` `dev/packaging/native/windows_msi_single.py`
- `S04` `M` `native/CONTRACT.md`
- `S04` `M` `native/application/src/installation/maintenance.rs`
- `S04` `M` `native/application/tests/installation.rs`
- `S04` `M` `native/cmake/distribution/CMakeLists.txt`
- `S04` `M` `native/desktop/CMakeLists.txt`
- `S04` `M` `native/installer/src/admission.rs`
- `S04` `M` `native/installer/src/owner.rs`
- `S04` `M` `native/installer/src/runner.rs`
- `S04` `M` `native/installer/src/runner/already_installed.rs`
- `S04` `M` `native/installer/src/runner/already_installed/observation_tests.rs`
- `S04` `M` `native/installer/src/runner/bootstrap.rs`
- `S04` `M` `native/installer/src/runner/recovery.rs`
- `S04` `M` `native/installer/src/runner/removal.rs`
- `S04` `M` `native/installer/src/windows.rs`
- `S04` `verify:` `Debug and Release rust_installer CMake builds` -> `pass`
- `S04` `verify:` `installer.rust and application.rust CTest 2 tests` -> `pass`
- `S04` `verify:` `focused installer Python 156 tests 2 skips` -> `pass`
- `S04` `verify:` `rebuilt adapter and runner admission external test` -> `pass`
- `S04` `verify:` `real WiX fixture 1 initial compile 0 unchanged` -> `pass`
- `S04` `verify:` `build-directory admission 14 tests` -> `pass`
- `S04` `verify:` `CMake desktop paths 6 tests` -> `pass`
- `S04` `verify:` `scoped Ruff ty and Rust checks` -> `pass`
- `S05` `M` `dev/packaging/native/cached_command.py`
- `S05` `M` `dev/packaging/native/distribution_prepare.py`
- `S05` `M` `dev/packaging/native/installation.py`
- `S05` `M` `dev/packaging/native/installation_reuse.py`
- `S05` `A` `dev/packaging/native/installation_plan.py`
- `S05` `A` `dev/packaging/native/installation_currency.py`
- `S05` `M` `native/cmake/CachedCommand.cmake`
- `S05` `M` `native/cmake/InstallerFlow.cmake`
- `S05` `M` `native/cmake/distribution/CMakeLists.txt`
- `S05` `M` `dev/packaging/native/tests/test_build_directory_admission.py`
- `S05` `M` `dev/packaging/native/tests/test_distribution_prepare.py`
- `S05` `A` `dev/packaging/native/tests/test_installation_currency.py`
- `S05` `M` `dev/packaging/tests/test_native_installation.py`
- `S05` `M` `.vault/audit/2026-10-16-native-build-incremental-audit.md`
- `S05` `verify:` `currency behavior tests 36 plus receipt tamper tests 4` -> `pass`
- `S05` `verify:` `staging CMake race rollback kit tests 18` -> `pass`
- `S05` `verify:` `installation compatibility tests 23 with 2 skips` -> `pass`
- `S05` `verify:` `independent integrated S05 source review` -> `pass`
- `S05` `verify:` `scoped Ruff and ty` -> `pass`
- `S05` `verify:` `final Debug publication with concurrent active harness` -> `fail`
- `S05` `verify:` `Debug full native-installer prior agent generation and exactly one actual WiX build` -> `pass`
- `S05` `verify:` `Debug noninstalling bootstrap after external app generation replacement` -> `fail`
- `S05` `verify:` `owned canceled build tree settled without publication` -> `pass`

## Notes

- `S04` Disposable Windows installed upgrade rollback removal acceptance remains unavailable; no workstation installation ran.
- `S05` S05 remains open: another live `dev.package_runner` test all session continuously starts Debug processes; both build configurations use whole-build quiescence. No manual kills or guard bypass. Final full package no-op proofs and commit await owner coordination.
- `S05` External agent and client source publishers changed the shared Debug generation after successful MSI kit publication. Digest guard correctly refuses stale pairing. Only our exact build tree was stopped; final current-generation packages, no-op proofs and S05 commit remain pending coordinated source/output ownership.
