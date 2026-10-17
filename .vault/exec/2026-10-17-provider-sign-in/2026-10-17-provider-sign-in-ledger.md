---
tags:
  - '#exec'
  - '#provider-sign-in'
date: '2026-10-17'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:d5e0dddc62564601c056a01a68f187b1c1fe168ff15b7398c3f387266520c771'
related:
  - "[[2026-10-17-provider-sign-in-plan]]"
---

# `provider-sign-in` ledger

## Changes

- `S02` `M` `native/desktop/frontend/src/components/AgentColumn.tsx`
- `S02` `M` `native/desktop/frontend/src/components/settings/ProviderSettings.tsx`
- `S02` `A` `native/desktop/frontend/src/components/settings/ProviderSignInDialog.tsx`
- `S02` `M` `native/desktop/frontend/src/shell/providerSettings.ts`
- `S02` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S02` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S02` `M` `native/desktop/frontend/src/dev/providerSettingsFixture.ts`
- `S02` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S02` `M` `native/desktop/frontend/tests/scenarios/providers.spec.ts`
- `S02` `M` `native/desktop/src-tauri/src/shell/provider_settings/mod.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/provider_settings/wire.rs`
- `S02` `M` `src/cadrumo_agent_service/locales/en.yml`
- `S02` `M` `src/cadrumo_agent_service/locales/es.yml`
- `S02` `M` `src/cadrumo_agent_service/locales/ca.yml`
- `S02` `M` `src/cadrumo_agent_service/locales/hu.yml`
- `S02` `verify:` `cmake desktop-host-unit-test 345 tests` -> `pass`
- `S02` `verify:` `cmake desktop-host-unit-clippy` -> `pass`
- `S02` `verify:` `cmake desktop-frontend-check` -> `pass`
- `S02` `verify:` `playwright providers.spec.ts workers1 11 scenarios` -> `pass`
- `S02` `by:` `principal-and-luna-max-workers`
- `S01` `M` `src/cadrumo_agent_service/service.py`
- `S01` `M` `src/cadrumo_agent_service/admin.py`
- `S01` `M` `src/cadrumo_agent_service/adapters/agent_provider_catalog.py`
- `S01` `A` `src/cadrumo_agent_service/host/auth_attempt.py`
- `S01` `A` `src/cadrumo_agent_service/host/auth_protocol.py`
- `S01` `A` `src/cadrumo_agent_service/host/tests/test_auth_attempt.py`
- `S01` `A` `src/cadrumo_agent_service/host/tests/test_auth_protocol.py`
- `S01` `M` `src/cadrumo_agent_service/host/tests/test_admin_authority.py`
- `S01` `M` `src/cadrumo_agent_service/host/tests/test_provider_sign_in_preparation.py`
- `S01` `M` `src/cadrumo_agent_service/host/tests/test_hosted_certification_status.py`
- `S01` `M` `src/cadrumo_agent_service/adapters/tests/test_agent_provider_catalog.py`
- `S01` `M` `native/application-environment.toml`
- `S01` `verify:` `focused Python service auth/catalog/preparation/authority 79 tests` -> `pass`
- `S01` `verify:` `latest auth protocol and revoked attempt 22 tests` -> `pass`
- `S01` `verify:` `scoped ruff and ty` -> `pass`
- `S01` `by:` `principal`
- `S03` `M` `native/CONTRACT.md`
- `S03` `M` `native/cmake/Packaging.cmake`
- `S03` `A` `native/tests/provider_auth_smoke.py`
- `S03` `M` `dev/packaging/native/tests/test_agent_image.py`
- `S03` `verify:` `package invocation declaration 60 tests` -> `pass`
- `S03` `verify:` `just check-registry-gate` -> `pass`
- `S03` `verify:` `just test-gate scoped manifest 174 passed one unrelated fixture failure` -> `fail`
- `S03` `verify:` `just check-code seven unrelated global gates failed` -> `fail`
- `S03` `by:` `principal`
- `S02` `M` `native/desktop/src-tauri/src/agent/admin.rs`
- `S02` `verify:` `cmake desktop-host-unit-test filter agent::admin 3 tests including 7second connect response` -> `pass`
- `S02` `verify:` `cmake desktop-host-unit-clippy after connect grace change` -> `pass`
- `S02` `by:` `principal-and-luna-max-native`
- `S01` `verify:` `Windows process cleanup fault-port contracts 16 tests` -> `pass`
- `S01` `verify:` `sibling cadrumo-agent provider_auth tests 6 tests` -> `pass`
- `S03` `verify:` `cmake app-payload final stable build` -> `pass`
- `S03` `verify:` `ctest bundle.agent and bundle.provider-auth 2 tests` -> `pass`
- `S03` `verify:` `installed service and agent catalog source text matches after newline normalization` -> `pass`
- `S01` `verify:` `final shipped AuthAttempt real Codex browser cancel device authority loss and unobserved watchdog` -> `pass`
- `S03` `verify:` `final real-provider package lifecycle probe three routes` -> `pass`
- `S03` `verify:` `scoped git diff whitespace check` -> `pass`
- `S03` `verify:` `packaged desktop --gui starts visible Cadrumo window and runtime in interactive session` -> `pass`

## Notes

- `S03` Overall verification pending clean repository-wide gates. See build/windows-x64/provider-auth-check-code.log and provider-auth-test-gate.log. No auth path was named in those failures; do not modify unrelated working-tree work to conceal them. Final stable package build and lifecycle probes pending.
- `S01` Sibling agent main checkout adds auth providers --interface gui --json, its test, and operations.rst discovery documentation; the terminal catalog stays compatible. Agent scoped ruff passes. These sibling changes remain uncommitted.
- `S03` Final stable payload is build/windows-x64/stage/Debug/app. Raw hashes differ only because packaging normalizes CRLF to LF; normalized full source text matches for service, admin, `auth_attempt,` `auth_protocol,` `agent_provider_catalog,` and sibling `provider_auth.` Real provider lifecycle probe running.
- `S01` Final packaged interpreter/imports and admitted helper initiated real Codex browser/device authentication without opening a terminal. All three routes reached `browser_action` then cancelled, cleared transient URL/code and confirmed process cleanup. No OAuth completion or real model request was attempted.
- `S03` All in-scope package verification is complete. S03 and overall audit stay pending because repository-wide test-gate and check-code remain failed in unrelated areas. Human-completed OAuth, credential persistence after completion and a real model turn remain unverified. Changes remain uncommitted.
- `S03` Live GUI verification started in isolated build/windows-x64/testing/Debug/provider-sign-in-live storage with admitted external Codex binary directory. UI Automation observes the real Crear un perfil screen; runtime is running. Awaiting user-created test profile and subsequent human provider OAuth completion. No provider credentials inspected, no OAuth success claimed.
- `S03` Committed 2026-10-17 at the operator's instruction 'commit them' while the session that wrote it was gone; S03 and S04 stay open and the live GUI check from stage/Debug is still running.
