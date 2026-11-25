---
tags:
  - '#exec'
  - '#ollama-provider-settings'
date: '2026-10-26'
modified: '2026-10-26'
body_schema: 'body-v2'
body_hash: 'sha256:5f00328da1e6d33965ac051ce1ce6bac991c7c48b23aafae8d20c768a75986ed'
related:
  - "[[2026-10-26-ollama-provider-settings-plan]]"
---

# `ollama-provider-settings` ledger

## Changes

- `S01` `M` `native/application/src/provisioning/engine.rs`
- `S01` `M` `native/application/src/provisioning/local_ai/models.rs`
- `S01` `M` `native/application/src/provisioning/local_ai/models/tests.rs`
- `S01` `M` `native/application/src/provisioning/protocol/tests.rs`
- `S01` `verify:` `cargo test --lib provisioning::` -> `pass`
- `S01` `verify:` `cargo test --features test-support --test provisioning_faults` -> `pass`
- `S01` `verify:` `cargo clippy --all-targets --features test-support -- -D warnings` -> `pass`
- `S01` `verify:` `cargo fmt --check` -> `pass`
- `S02` `M` `native/desktop/src-tauri/src/shell/setup/admission.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/setup/admission_tests.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/setup/wire.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/setup/components.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/setup/components_tests.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/setup/mod.rs`
- `S02` `verify:` `cmake --build build/windows-x64 --target desktop-host-unit-test` -> `pass`
- `S03` `A` `native/desktop/frontend/src/components/settings/LocalModels.tsx`
- `S03` `A` `native/desktop/frontend/src/shell/modelRoles.ts`
- `S03` `M` `native/desktop/frontend/src/components/agent/ModelRolesDialog.tsx`
- `S03` `M` `native/desktop/frontend/src/shell/agentModelRoles.ts`
- `S03` `M` `native/desktop/frontend/src/components/settings/ProviderSettings.tsx`
- `S03` `M` `native/desktop/frontend/src/components/AgentColumn.tsx`
- `S03` `M` `native/desktop/frontend/src/App.tsx`
- `S03` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S03` `M` `native/desktop/frontend/src/shell/host.ts`
- `S03` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S03` `M` `native/desktop/frontend/src/shell/setup.ts`
- `S03` `verify:` `npx tsc --noEmit -p .` -> `pass`
- `S04` `M` `src/cadrumo_agent_service/locales/en.yml`
- `S04` `M` `src/cadrumo_agent_service/locales/es.yml`
- `S04` `M` `src/cadrumo_agent_service/locales/ca.yml`
- `S04` `M` `src/cadrumo_agent_service/locales/hu.yml`
- `S04` `M` `dev/locales/desktop_chrome.py`
- `S04` `verify:` `cmake --build build/windows-x64 --target desktop-frontend-chrome` -> `pass`
- `S05` `A` `native/desktop/frontend/tests/scenarios/local-models.spec.ts`
- `S05` `A` `native/desktop/frontend/src/components/settings/LocalModels.stories.tsx`
- `S05` `M` `native/desktop/frontend/src/dev/fixtures/agentCatalog.ts`
- `S05` `M` `native/desktop/frontend/src/dev/setupFixture.ts`
- `S05` `verify:` `cmake --build build/windows-x64 --target desktop-frontend-test` -> `fail`

## Notes

- `S05` full gate: 44 failures traced to a shared build regenerated mid-run, load timeouts and stale specs; stale specs fixed and 24 of 25 targeted reruns pass; ledger-benchmark still over budget under machine load
