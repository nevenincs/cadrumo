---
tags:
  - '#exec'
  - '#debug-startup-reliability'
date: '2026-10-28'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:914129c35faa829261a2300498e36065d1b29391c85c2ea7ef652db3726668d4'
related:
  - "[[2026-10-28-debug-startup-reliability-plan]]"
---

# `debug-startup-reliability` ledger

## Changes

- `S02` `M` `src/cadrumo_runtime/host/profile_connection_services.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_extension_records.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_sessions.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_host.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_service_records.py`
- `S02` `verify:` `Ruff check and format owned5` -> `pass`
- `S02` `verify:` `ty check owned production4` -> `pass`
- `S02` `verify:` `focused service-record and admission interleavings8 across scoped runs` -> `pass`
- `S02` `verify:` `independent Sol medium integrated lifecycle source review` -> `pass`
- `S02` `by:` `Sol 6.1 high; root integration`
- `S01` `M` `native/desktop/src-tauri/src/agent/supervisor.rs`
- `S01` `M` `native/desktop/src-tauri/src/agent/person/native.rs`
- `S01` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S01` `A` `src/cadrumo_client/transport/tests/test_service_admission_deadline.py`
- `S01` `verify:` `cmake --build --preset windows-tests-debug --target desktop-host-unit-test with agent:: filter146 tests` -> `pass`
- `S01` `verify:` `cmake --build --preset windows-tests-debug --target desktop-host-unit-clippy` -> `pass`
- `S01` `verify:` `ctest desktop.fmt` -> `pass`
- `S01` `verify:` `pytest test_service_admission_deadline.py2 tests` -> `pass`
- `S01` `verify:` `Ruff check and format owned Python paths` -> `pass`
- `S01` `verify:` `ty scoped client paths` -> `pass`
- `S01` `verify:` `independent integrated source review` -> `pass`
- `S01` `by:` `Sol 6.1 high; root integration`
- `S05` `M` `src/cadrumo_client/contracts/deadline_budget.py`
- `S05` `M` `src/cadrumo_client/contracts/contracts.py`
- `S05` `M` `src/cadrumo_client/contracts/tests/test_deadline_budget.py`
- `S05` `M` `dev/packaging/native/generate.py`
- `S05` `M` `src/cadrumo_agent_service/service.py`
- `S05` `M` `src/cadrumo_agent_service/host/controller.py`
- `S05` `M` `src/cadrumo_agent_service/host/launcher_protocol.py`
- `S05` `M` `src/cadrumo_agent_service/adapters/agent_process.py`
- `S05` `M` `src/cadrumo_agent_service/host/tests/test_agent_replacement.py`
- `S05` `M` `src/cadrumo_agent_service/host/tests/test_controller_native_refusal.py`
- `S05` `M` `src/cadrumo_agent_service/host/tests/test_hosted_start_refusal.py`
- `S05` `M` `src/cadrumo_agent_service/host/tests/test_launcher_protocol.py`
- `S05` `M` `src/cadrumo_agent_service/host/tests/test_lifecycle_answers.py`
- `S05` `M` `src/cadrumo_agent_service/host/tests/test_service_failure.py`
- `S05` `M` `src/cadrumo_agent_service/adapters/tests/agent_host_fixture.py`
- `S05` `M` `src/cadrumo_agent_service/adapters/tests/test_agent_process_native.py`
- `S05` `M` `native/desktop/frontend/src/shell/agentSession.ts`
- `S05` `M` `native/desktop/frontend/src/components/AgentColumn.tsx`
- `S05` `M` `dev/locales/desktop_chrome.py`
- `S05` `M` `src/cadrumo_agent_service/locales/en.yml`
- `S05` `M` `src/cadrumo_agent_service/locales/es.yml`
- `S05` `M` `src/cadrumo_agent_service/locales/ca.yml`
- `S05` `M` `src/cadrumo_agent_service/locales/hu.yml`
- `S05` `verify:` `host unit and deadline325 tests` -> `pass`
- `S05` `verify:` `focused controller and mapping97 tests` -> `pass`
- `S05` `verify:` `corrected final controller24 tests` -> `pass`
- `S05` `verify:` `focused Windows process5 tests` -> `pass`
- `S05` `verify:` `scoped Ruff format and ty` -> `pass`
- `S05` `verify:` `npm run check` -> `pass`
- `S05` `verify:` `four-locale emergency-key projection` -> `pass`
- `S05` `verify:` `independent S05 delta review` -> `pass`
- `S05` `by:` `Sol6.1 medium and root`

## Notes

- `S02` Initial owning fixture startup failed twice before regression bodies; final reruns passed, logs125649/130851/131345/132021 under2026-10-28 test-runs. Root aggregate gates remain running.
- `S05` Initial real-process cohort containment confirmation timed out; repeated targeted real-child runs passed without relaxing containment proof. Locale focused check10pass1fail due two unused browser setup keys outside this change. Original broad code gate failed on types/import/symbol/manifest results while tree was changing; original broad test gate interrupted for expanded protocol scope after unrelated ledger failure. Fresh integrated gates pending S04/S06/S07.
