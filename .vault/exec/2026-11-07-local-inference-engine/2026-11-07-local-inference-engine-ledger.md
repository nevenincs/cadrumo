---
tags:
  - '#exec'
  - '#local-inference-engine'
date: '2026-11-07'
modified: '2026-11-07'
body_schema: 'body-v2'
body_hash: 'sha256:fb99d08ccc38249fc664304c84a6a17a60e2b3a9d36c86c51f9f490b5df814ec'
related:
  - "[[2026-11-07-local-inference-engine-plan]]"
---

# `local-inference-engine` ledger

## Changes

- `S01` `M` `.vault/adr/2026-10-18-dependency-provisioning-unified-setup-adr.md`
- `S01` `M` `.vault/adr/2026-10-24-rust-component-provisioning-adr.md`
- `S01` `M` `.vault/adr/2026-10-25-agent-owned-models-adr.md`
- `S01` `M` `.vault/adr/2026-06-13-llm-evidence-classification-adr.md`
- `S01` `verify:` `vaultspec-core vault check all` -> `pass`
- `S01` `by:` `vaultspec-high-executor`
- `S25` `M` `.vault/research/2026-11-07-local-inference-engine-research.md`
- `S25` `M` `.vault/adr/2026-11-07-local-inference-engine-adr.md`
- `S25` `verify:` `gpu_pass.py --go --cleanup` -> `pass`
- `S10` `A` `dev/env/llamacpp_pins.py`
- `S10` `A` `dev/env/tests/test_llamacpp_pins.py`
- `S10` `A` `native/llamacpp-pins.json`
- `S10` `M` `justfile`
- `S10` `M` `dev/quality/metadata/import_load_targets.json`
- `S10` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S10` `verify:` `pytest dev/env/tests/test_llamacpp_pins.py dev/env/tests/test_local_ai_pins.py dev/quality/tests/test_no_model_definitions.py` -> `pass`
- `S10` `verify:` `ruff check and format --check` -> `pass`
- `S10` `verify:` `ty check` -> `pass`
- `S10` `verify:` `dev.quality.import_gate` -> `pass`
- `S10` `by:` `vaultspec-standard-executor`
- `S12` `M` `native/application/src/provisioning/pins.rs`
- `S12` `M` `native/application/src/provisioning/engine.rs`
- `S12` `M` `native/application/src/provisioning/engine/tests.rs`
- `S12` `M` `native/application/src/provisioning/network.rs`
- `S12` `M` `native/application/src/provisioning/local_ai/program/tests.rs`
- `S12` `M` `native/manager/src/supervision/local_ai.rs`
- `S12` `verify:` `rustfmt --edition 2024 --emit stdout (six files)` -> `pass`
- `S12` `verify:` `pytest dev/quality/tests/test_no_model_definitions.py` -> `pass`
- `S12` `by:` `vaultspec-standard-executor`
- `S10` `verify:` `uv run --no-sync pytest dev/env/tests/test_llamacpp_pins.py dev/env/tests/test_local_ai_pins.py dev/quality/tests/test_no_model_definitions.py dev/quality/tests/test_no_git_cli.py` -> `pass`
- `S10` `verify:` `just check-import-boundaries` -> `pass`
- `S10` `by:` `vaultspec-high-executor`
- `S12` `verify:` `ctest --preset debug -R manager.(rust|supervision|fmt|clippy|fixture.clippy)` -> `pass`
- `S12` `verify:` `ctest --preset debug -R application.(rust|fmt|clippy|features.clippy)` -> `pass`
- `S12` `verify:` `uv run --no-sync pytest dev/env/tests/test_local_ai_pins.py` -> `pass`
- `S12` `by:` `vaultspec-high-executor`
- `S14` `M` `native/application/src/provisioning/local_ai/registry/tests.rs`
- `S14` `verify:` `ctest --preset debug -R application.(rust|fmt|clippy|features.clippy)` -> `pass`
- `S14` `by:` `vaultspec-high-executor`
- `S10` `verify:` `pytest llamacpp_pins, local_ai_pins, no_model_definitions, no_git_cli (123 tests)` -> `pass`
- `S28` `verify:` `uv run --no-sync pytest src/cadrumo_agent_service/adapters/tests/test_agent_background_runs.py dev/locales/tests/test_desktop_chrome.py (51 tests)` -> `pass`
- `S28` `verify:` `just check-locales (0 blocking)` -> `pass`
- `S28` `verify:` `npm run check (90 node tests, tsc, eslint, prettier)` -> `pass`
- `S28` `verify:` `npx playwright test tests/agent-live.spec.ts (38 tests)` -> `pass`
- `S28` `by:` `vaultspec-high-executor`
- `S11` `A` `dev/packaging/native/llama_server.py`
- `S11` `A` `dev/packaging/native/platforms/elf.py`
- `S11` `A` `dev/packaging/native/platforms/tests/test_elf.py`
- `S11` `A` `dev/packaging/native/tests/test_llama_server.py`
- `S11` `M` `dev/packaging/native/action_selection.py`
- `S11` `M` `dev/packaging/native/assemble.py`
- `S11` `M` `dev/packaging/native/assembly_staging.py`
- `S11` `M` `dev/packaging/native/cmake_build.py`
- `S11` `M` `dev/packaging/native/platforms/windows.py`
- `S11` `M` `dev/packaging/native/platforms/tests/test_windows.py`
- `S11` `M` `dev/packaging/native/tests/binary_fixtures.py`
- `S11` `M` `dev/packaging/native/tests/test_platform_enrollment.py`
- `S11` `M` `dev/packaging/tests/test_native_layout_entrypoints.py`
- `S11` `M` `dev/quality/tests/test_no_model_definitions.py`
- `S11` `M` `dev/quality/metadata/import_load_targets.json`
- `S11` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S11` `M` `native/CMakeLists.txt`
- `S11` `M` `native/cmake/BuildPaths.cmake`
- `S11` `M` `native/cmake/Packaging.cmake`
- `S11` `M` `native/package-layout.json`
- `S11` `M` `native/platforms/macos-arm64.json`
- `S11` `M` `native/CONTRACT.md`
- `S11` `verify:` `pytest llama_server elf layout enrollment windows no_model_definitions no_git_cli assembly_refusals` -> `pass`
- `S11` `verify:` `ruff check and format on dev/packaging and the model gate` -> `pass`
- `S11` `verify:` `ty check on the touched modules` -> `pass`
- `S11` `verify:` `lint-imports quick contract check` -> `pass`
- `S11` `verify:` `import load targets recompiled` -> `pass`
- `S11` `by:` `vaultspec-standard-executor`
- `S11` `A` `dev/packaging/native/msvc_redist.py`
- `S11` `A` `dev/packaging/native/tests/test_msvc_redist.py`
- `S11` `M` `dev/packaging/native/llama_server.py`
- `S11` `M` `dev/packaging/native/tests/test_llama_server.py`
- `S11` `M` `native/cmake/AssemblyTools.cmake`
- `S11` `verify:` `pytest msvc_redist llama_server platforms layout no_model_definitions no_git_cli assembly_refusals cmake_package_inputs` -> `pass`
- `S11` `verify:` `ruff check and format on dev/packaging` -> `pass`
- `S11` `verify:` `ty check on the touched modules` -> `pass`
- `S11` `verify:` `lint-imports quick contract check` -> `pass`
- `S11` `verify:` `real Windows archive with the real MSVC redistributable resolves every import` -> `pass`
- `S13` `A` `native/application/src/provisioning/local_ai/fake_llamacpp.rs`
- `S13` `M` `native/application/src/provisioning/local_ai/mod.rs`
- `S13` `by:` `vaultspec-standard-executor`
- `S15` `A` `native/application/src/provisioning/local_ai/huggingface.rs`
- `S15` `A` `native/application/src/provisioning/local_ai/huggingface/tests.rs`
- `S15` `M` `native/application/src/provisioning/local_ai/registry.rs`
- `S15` `M` `native/application/src/provisioning/local_ai/models.rs`
- `S15` `M` `native/application/src/provisioning/local_ai/mod.rs`
- `S15` `verify:` `rustfmt --edition 2024 --check local_ai sources` -> `pass`
- `S15` `verify:` `pytest dev/quality/tests/test_no_model_definitions.py dev/quality/tests/test_no_git_cli.py` -> `pass`
- `S15` `by:` `vaultspec-high-executor`
- `S13` `verify:` `ctest --preset debug -R application.(rust|fmt|clippy|features.clippy)` -> `pass`
- `S15` `verify:` `ctest --preset debug -R application.(rust|fmt|clippy|features.clippy)` -> `pass`
- `S11` `verify:` `pytest S11 packaging focus (156)` -> `pass`

## Notes

- `S12` Rust not compiled in this worktree; cargo test and clippy for cadrumo-application and the manager are owed in a root build slot
- `S14` `A` `native/application/src/provisioning/local_ai/registry.rs`
- `S14` `A` `native/application/src/provisioning/local_ai/registry/tests.rs`
- `S14` `M` `native/application/src/provisioning/local_ai/mod.rs`
- `S14` `M` `native/application/src/provisioning/local_ai/models.rs`
- `S14` `M` `native/application/src/provisioning/http.rs`
- `S14` `M` `native/application/src/provisioning/transfer.rs`
- `S14` `verify:` `rustfmt --edition 2024 --check` -> `pass`
- `S14` `by:` `vaultspec-high-executor`
- `S14` Root build slot fixed two registry progress tests that unwrapped run.result by value before borrowing run; fix committed as e972b40632
- `S28` Full npm test: 4 `desktop-*.spec.ts` files do not load on tui since a8ebeaaa9d (desktopShell.ts bridge path resolves to native/docs); remaining 2473 tests: 2454 passed, 9 skipped, 10 failed in calendar-place, modelo-related-filings, touch and ledger-invoice-match specs, none importing P06 modules, while concurrent fixture-date commits landed
- `S11` Pending in the root build slot: CMake configure and build of the `llama_server` step, bundle build and test-native-bundle
- `S11` Linux llama-server archives exceed the glibc 2.28 floor (x86-64 2.34, aarch64 2.38); staging refuses them by design
- `S11` Pending in the root build slot: CMake configure resolves the redistributable, then bundle build and test-native-bundle
- `S15` cargo test and clippy for native/application are pending the root build slot; not run in the worktree
- `S11` configure, bundle and test-native-bundle owed in the DESKTOP proving cycle; Step stays open until it passes

## Notes

- `S14` cargo clippy and the registry tests are pending the root build slot; no cargo ran in the worktree
- `S28` `M` `src/cadrumo_agent_service/adapters/agent_background_runs.py`
- `S28` `M` `src/cadrumo_agent_service/adapters/tests/test_agent_background_runs.py`
- `S28` `M` `src/cadrumo_agent_service/locales/en.yml`
- `S28` `M` `src/cadrumo_agent_service/locales/es.yml`
- `S28` `M` `src/cadrumo_agent_service/locales/ca.yml`
- `S28` `M` `src/cadrumo_agent_service/locales/hu.yml`
- `S28` `M` `dev/locales/desktop_interface_keys.py`
- `S28` `M` `native/desktop/frontend/src/shell/agentViews.ts`
- `S28` `M` `native/desktop/frontend/src/shell/agentWords.ts`
- `S28` `M` `native/desktop/frontend/tests/agent-live.spec.ts`
- `S28` `verify:` `pytest test_agent_background_runs` -> `pass`
- `S28` `verify:` `ruff check+format` -> `pass`
- `S28` `verify:` `ty` -> `pass`
- `S28` `verify:` `lint-imports` -> `pass`
- `S28` `verify:` `dev.locales audit` -> `pass`
- `S28` `verify:` `dev.locales tests test_desktop_chrome` -> `pass`
- `S28` `by:` `vaultspec-standard-executor`

## Notes

- `S28` desktop typecheck and playwright pending root slot; locales status blocked by unprovisioned docs pot manifest and spelling dictionaries in this worktree
