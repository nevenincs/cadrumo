---
tags:
  - '#exec'
  - '#debug-startup-reliability'
date: '2026-10-28'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:c174bfae363a6584085cc58363f9b0ff7837f116b7a8f5393a04d63c099257ca'
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
- `S07` `M` `src/cadrumo_runtime/host/profile_login.py`
- `S07` `M` `src/cadrumo/application/user_profile/login_session.py`
- `S07` `M` `src/cadrumo/application/user_profile/custody_ports.py`
- `S07` `M` `src/cadrumo/adapters/persistence/storage/profile_custody.py`
- `S07` `M` `src/cadrumo/adapters/persistence/storage/custody/errors.py`
- `S07` `M` `src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py`
- `S07` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_worker_supervision.py`
- `S07` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py`
- `S07` `verify:` `pytest owning KDF supervision/prewarm/login-port/custody-adapter47 tests` -> `pass`
- `S07` `verify:` `scoped Ruff format and ty` -> `pass`
- `S07` `by:` `Sol6.1 high`
- `S12` `A` `src/cadrumo/application/user_profile/proof_cancellation.py`
- `S12` `A` `src/cadrumo_runtime/adapters/worker_proof_control.py`
- `S12` `M` `src/cadrumo_runtime/host/session_owner.py`
- `S12` `verify:` `pytest crypto and token51 plus Windows and Linux three cancellation cases` -> `pass`
- `S12` `verify:` `pytest worker91 construction20 token3 and native exact-attempt cancel EOF queued admission` -> `pass`
- `S12` `verify:` `independent Sol6.1 high S12 delta review` -> `pass`
- `S12` `by:` `Sol6.1 high`
- `S08` `A` `src/cadrumo/adapters/persistence/storage/custody/_kdf_file_lease.py`
- `S08` `A` `src/cadrumo/adapters/persistence/storage/custody/_kdf_lease_worker.py`
- `S08` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py`
- `S08` `verify:` `pytest owning KDF51 and Windows legacy-lock cancellation` -> `pass`
- `S08` `verify:` `WSL Linux same-domain leases and exact-child cancellation` -> `pass`
- `S08` `verify:` `Ruff format and ty Windows Linux macOS` -> `pass`
- `S08` `by:` `Sol6.1 high`

## Notes

- `S02` Initial owning fixture startup failed twice before regression bodies; final reruns passed, logs125649/130851/131345/132021 under2026-10-28 test-runs. Root aggregate gates remain running.
- `S05` Initial real-process cohort containment confirmation timed out; repeated targeted real-child runs passed without relaxing containment proof. Locale focused check10pass1fail due two unused browser setup keys outside this change. Original broad code gate failed on types/import/symbol/manifest results while tree was changing; original broad test gate interrupted for expanded protocol scope after unrelated ledger failure. Fresh integrated gates pending S04/S06/S07.
- `S07` Run20261028T141339.796127Z-pytest-30576-685e7846. Same-domain OS lock signaling is separately sequenced S08; S07 retains legacy permit implementation until that checkpoint.
