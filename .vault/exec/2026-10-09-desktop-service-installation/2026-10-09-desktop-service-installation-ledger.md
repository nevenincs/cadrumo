---
tags:
  - '#exec'
  - '#desktop-service-installation'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:13e5112039e6ea70e2730f029fec7964429429aba0accd524d143a3b4bb7f2ab'
related:
  - "[[2026-10-09-desktop-service-installation-plan]]"
---

# `desktop-service-installation` ledger

## Changes

- `S01` `A` `.vault/adr/2026-10-09-desktop-service-installation-adr.md`
- `S01` `M` `.vault/adr/2026-10-04-desktop-shell-adr.md`
- `S01` `M` `.vault/adr/2026-10-04-runtime-manager-architecture-adr.md`
- `S01` `M` `.vault/adr/2026-10-07-application-distribution-windows-versioned-msi-adr.md`
- `S01` `M` `native/application/src/installation.rs`
- `S01` `M` `native/installer/Cargo.toml`
- `S01` `M` `native/installer/src/runner.rs`
- `S01` `A` `native/installer/src/runner/bootstrap.rs`
- `S01` `M` `native/package-layout.json`
- `S01` `M` `native/cmake/InstallerFlow.cmake`
- `S01` `M` `native/cmake/distribution/CMakeLists.txt`
- `S01` `M` `dev/packaging/native/windows_msi_build.py`
- `S01` `A` `dev/packaging/native/tests/test_bootstrap_kit.py`
- `S01` `verify:` `cargo test --manifest-path native/installer/Cargo.toml --lib` -> `pass`
- `S01` `verify:` `cargo clippy --manifest-path native/installer/Cargo.toml --lib --tests -- -D warnings` -> `pass`
- `S01` `verify:` `cargo fmt --manifest-path native/installer/Cargo.toml --check` -> `pass`
- `S01` `verify:` `pytest test_distribution_prepare.py test_bootstrap_kit.py -n 0 -m unit with WiX 5.0.2 on PATH` -> `pass`
- `S01` `verify:` `ruff scoped packaging checks` -> `pass`
- `S01` `verify:` `ty scoped kit builder and tests` -> `pass`
- `S01` `by:` `vaultspec-executor`
- `S02` `M` `dev/locales/desktop_chrome.py`
- `S02` `M` `dev/packaging/native/linux_desktop_runtime.py`
- `S02` `M` `native/application/src/error/application.rs`
- `S02` `M` `native/desktop/frontend/src/components/SignIn.tsx`
- `S02` `M` `native/desktop/frontend/src/dev/fixtures/account.ts`
- `S02` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S02` `M` `native/desktop/frontend/src/dev/scenarios.ts`
- `S02` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S02` `M` `native/desktop/frontend/src/shell/host.ts`
- `S02` `M` `native/desktop/frontend/src/shell/signIn.ts`
- `S02` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S02` `A` `native/desktop/frontend/tests/scenarios/install.spec.ts`
- `S02` `M` `native/desktop/scripts/backend-snapshot.mjs`
- `S02` `M` `native/desktop/src-tauri/Cargo.lock`
- `S02` `M` `native/desktop/src-tauri/Cargo.toml`
- `S02` `M` `native/desktop/src-tauri/src/manager.rs`
- `S02` `M` `native/desktop/src-tauri/src/manager/tests.rs`
- `S02` `M` `native/desktop/tests/backend-snapshot.test.mjs`
- `S02` `M` `src/cadrumo/locales/ca/common.yml`
- `S02` `M` `src/cadrumo/locales/en/common.yml`
- `S02` `M` `src/cadrumo/locales/es/common.yml`
- `S02` `M` `src/cadrumo/locales/hu/common.yml`
- `S02` `A` `.vault/audit/2026-10-09-desktop-service-installation-audit.md`
- `S02` `verify:` `node native/desktop/scripts/tauri.mjs test-unit` -> `pass`
- `S02` `verify:` `node native/desktop/scripts/tauri.mjs clippy-backend` -> `pass`
- `S02` `verify:` `ctest -C Release -R application.rust --output-on-failure` -> `pass`
- `S02` `verify:` `node --test native/desktop/tests/backend-snapshot.test.mjs` -> `pass`
- `S02` `verify:` `npm run check` -> `pass`
- `S02` `verify:` `playwright test tests/scenarios/install.spec.ts --project=scenarios` -> `pass`
- `S02` `verify:` `dev.locales audit` -> `pass`
- `S02` `verify:` `dev.quality.data_files check scoped catalogues and Cargo manifests` -> `pass`
- `S02` `verify:` `cargo tree --locked --target x86_64-unknown-linux-gnu -e normal,build,features prior-vs-current equality` -> `pass`
- `S02` `by:` `vaultspec-executor`
- `S01` `M` `dev/packaging/native/windows_msi.py`
- `S01` `M` `dev/packaging/native/windows_msi_database.py`
- `S01` `M` `dev/packaging/tests/test_windows_msi.py`
- `S01` `M` `dev/packaging/native/tests/test_cmake_installer_flow.py`
- `S01` `verify:` `pytest test_windows_msi.py test_bootstrap_kit.py -n 0 -m unit with WiX and actual native adapter` -> `pass`
- `S01` `verify:` `pytest test_cmake_installer_flow.py -n 0 -m unit` -> `pass`
- `S01` `verify:` `cargo test --manifest-path native/installer/Cargo.toml --lib after request-handle closure` -> `pass`
- `S01` `verify:` `cargo clippy --manifest-path native/installer/Cargo.toml --lib --tests -- -D warnings after request-handle closure` -> `pass`
- `S02` `verify:` `node native/desktop/scripts/tauri.mjs test-unit manager latest shared bootstrap` -> `pass`
- `S02` `verify:` `node native/desktop/scripts/tauri.mjs clippy-backend latest shared bootstrap` -> `pass`
- `S01` `verify:` `cmake --build build/windows-x64 --config Release --target native-installer sequential stable stage` -> `pass`
- `S01` `verify:` `cargo test --lib assembled_kit_admits_both_scopes -- --ignored first integration invocation` -> `fail`
- `S01` `verify:` `cargo test --manifest-path native/installer/Cargo.toml --lib assembled_kit_admits_both_scopes -- --ignored corrected fresh reader` -> `pass`

## Notes

- `S01` Native-installer package build and assembled-kit read-only admission are still running/not yet exercised; no native install command was executed on the development host.
- `S02` Installed interactive acceptance remains pending on a disposable Windows desktop; Session 0 and this development host do not establish login registration, UAC or future TUI/CLI connectivity.
- `S01` Initial full Windows MSI test invocation used an incorrect native-adapter path and failed the environment prerequisite. Corrected to `cargo/native/x86_64-pc-windows-msvc/release;` all 46 selected tests passed, including compiled conditional-owner refusal, without installing a valid native plan.
- `S01` The assembled-kit test initially re-hashed the already-consumed custody reader at EOF, producing an empty-stream digest and a native owner mismatch. Production bootstrap opens a fresh retained reader for this second hash. Corrected the test to use that same real fresh-reader path; rerun pending. The change is within cfg(test), so the production build evidence remains applicable.
- `S01` The final assembled-kit admission passed for both user and machine scopes against the full production stage and generated compiler contract, including wrong native role/runner refusal, absence of legacy MSI gate, native request serialization, and temporary-file cleanup. No installation ran; this completes the earlier pending build/read-only admission evidence.
