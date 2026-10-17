---
tags:
  - '#exec'
  - '#provider-sign-in'
date: '2026-10-17'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:7950cfe0a330162da93826f5dfdd6ba07dac99561db2c380888f84ec95eb96dd'
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
- `S04` `verify:` `real GUI demo login before rebuild returns runtime_peer_untrusted` -> `fail`
- `S04` `verify:` `source native Windows login tests -n0 -m empty 2 tests` -> `pass`
- `S04` `M` `native/desktop/CMakeLists.txt`
- `S04` `verify:` `native Windows manifest tests14` -> `pass`
- `S04` `M` `dev/packaging/native/service_descriptors.py`
- `S04` `A` `dev/packaging/tests/test_native_service_descriptors.py`
- `S04` `verify:` `pytest packaging descriptor matrix plus real native service verifier` -> `pass`
- `S04` `verify:` `ruff focused check and format` -> `pass`
- `S04` `M` `src/cadrumo_agent_service/service.py`
- `S04` `M` `src/cadrumo_agent_service/providers/domain/catalog.py`
- `S04` `M` `src/cadrumo_agent_service/adapters/agent_provider_catalog.py`
- `S04` `M` `src/cadrumo_agent_service/providers/domain/tests/test_catalog.py`
- `S04` `M` `src/cadrumo_agent_service/providers/application/tests/synthetic_catalog.py`
- `S04` `M` `src/cadrumo_agent_service/host/tests/test_provider_sign_in_preparation.py`
- `S04` `verify:` `app-payload descriptor rebuild and inventory binding` -> `pass`
- `S04` `verify:` `live GUI local profile restored and session holder admitted` -> `pass`
- `S04` `verify:` `provider domain adapter and preparation regressions 90 tests` -> `pass`
- `S04` `verify:` `focused ruff format and ty` -> `pass`
- `S04` `M` `native/tests/agent_smoke.py`
- `S04` `M` `.vault/adr/2026-10-13-provider-settings-adr.md`
- `S04` `verify:` `agent service unit suite 329 tests` -> `pass`
- `S04` `M` `dev/locales/desktop_chrome.py`
- `S04` `M` `native/desktop/frontend/src/shell/agentCatalog.ts`
- `S04` `M` `native/desktop/frontend/src/shell/agentSession.ts`
- `S04` `M` `native/desktop/frontend/tests/agentCatalog.spec.ts`
- `S04` `M` `src/cadrumo_agent_service/locales/en.yml`
- `S04` `M` `src/cadrumo_agent_service/locales/es.yml`
- `S04` `M` `src/cadrumo_agent_service/locales/ca.yml`
- `S04` `M` `src/cadrumo_agent_service/locales/hu.yml`
- `S04` `verify:` `pytest dev/locales/tests/test_desktop_chrome.py 20 cases` -> `pass`
- `S04` `verify:` `Playwright product agentCatalog.spec.ts 11 cases` -> `pass`
- `S04` `verify:` `npm run check` -> `pass`
- `S04` `verify:` `bundle.agent and bundle.provider-auth packaged tests` -> `pass`
- `S04` `verify:` `external debug-root relocation file count and byte total` -> `pass`
- `S04` `verify:` `ruff check and format desktop_chrome.py` -> `pass`
- `S04` `verify:` `ty check desktop_chrome.py` -> `pass`
- `S04` `verify:` `cmake --build --preset debug --target app-payload final rebuild` -> `pass`
- `S04` `verify:` `ctest Debug bundle.agent and bundle.provider-auth final package` -> `pass`
- `S04` `verify:` `normal packaged GUI demo login provider panel and translated controls` -> `pass`
- `S04` `verify:` `real GUI prompt reached Codex turn started outside Git` -> `pass`

## Notes

- `S03` Overall verification pending clean repository-wide gates. See build/windows-x64/provider-auth-check-code.log and provider-auth-test-gate.log. No auth path was named in those failures; do not modify unrelated working-tree work to conceal them. Final stable package build and lifecycle probes pending.
- `S01` Sibling agent main checkout adds auth providers --interface gui --json, its test, and operations.rst discovery documentation; the terminal catalog stays compatible. Agent scoped ruff passes. These sibling changes remain uncommitted.
- `S03` Final stable payload is build/windows-x64/stage/Debug/app. Raw hashes differ only because packaging normalizes CRLF to LF; normalized full source text matches for service, admin, `auth_attempt,` `auth_protocol,` `agent_provider_catalog,` and sibling `provider_auth.` Real provider lifecycle probe running.
- `S01` Final packaged interpreter/imports and admitted helper initiated real Codex browser/device authentication without opening a terminal. All three routes reached `browser_action` then cancelled, cleared transient URL/code and confirmed process cleanup. No OAuth completion or real model request was attempted.
- `S03` All in-scope package verification is complete. S03 and overall audit stay pending because repository-wide test-gate and check-code remain failed in unrelated areas. Human-completed OAuth, credential persistence after completion and a real model turn remain unverified. Changes remain uncommitted.
- `S03` Live GUI verification started in isolated build/windows-x64/testing/Debug/provider-sign-in-live storage with admitted external Codex binary directory. UI Automation observes the real Crear un perfil screen; runtime is running. Awaiting user-created test profile and subsequent human provider OAuth completion. No provider credentials inspected, no OAuth success claimed.
- `S03` Committed 2026-10-17 at the operator's instruction 'commit them' while the session that wrote it was gone; S03 and S04 stay open and the live GUI check from stage/Debug is still running.
- `S04` User requested live verification and reported profile login failure, authorizing repair of this prerequisite. Runtime refused `login_owner_inactive_or_mismatch` before password validation. Luna readers and principal isolated stale packaged cadrumo.exe manifest lacking Windows10 supportedOS while source template and existing regression test already contain correction. Keep accepted runtime-manager native trust requirements unchanged. Reconfigured CMake and rebuilding package, preserving demo test profile. No password or provider token retained in evidence.
- `S04` Rebuild exposed missing ordering: desktop-host-build ran while generated desktop manifest was still stale; `native_metadata` producer had not run. Added Windows-only `native_metadata` prerequisites for Cargo/Tauri host build prepare test clippy and packaged-host targets. desktop-run only launches an existing image and is unchanged. Old-graph full payload build will finish before reconfigure and app-native rebuild; validate final executable resource and actual GUI authentication.
- `S04` Packaged demo login succeeds after `native_metadata` dependency correction and app-native rebuild. Staged desktop manifest has Windows 10 supportedOS. Subsequent `desktop_holder_unverified` occurs before parent checks: Windows SignIn launches cadrumo.exe --role runtime session hold but descriptor named bin/cadrumo-runtime.exe. Align Windows holder descriptor to desktop image/digest without changing admission checks. Preserve standalone image elsewhere and without desktop. Six focused tests pass. Luna read-only review passes. Full app-payload assembly pending.
- `S04` Actual app PID73392 now passes session admission. Provider settings `read_failed` traced to catalog v3 producer vs v2 consumer; `credentials_unavailable` was caused by refused catalog, not established absence of account credentials. Update strict consumer version and presentation metadata shape to v3. Preserve typed provider status refusal before adding success-only metadata. Actual packaged catalog parses into 12 lanes incl `codex_cli.` Rebuild and final GUI provider configuration pending.
- `S04` Bundled catalog producer/consumer compatibility is now checked by bundle.agent, including GUI auth provider membership. Source tests pass 329 unit cases; 27 integration cases were intentionally deselected. Scoped Luna review passes current v3 producer behavior. Existing optional opaque presentation metadata defaults remain unchanged; auth fields and unknown schema versions stay strict. Reconcile stale ADR supplier version reference to v3 without changing credential custody authority.
- `S04` Actual GUI `agent_ready` exposed Intl.ListFormat crash on new subagent capability names. Added known labels and unknown-proof filtering with generation scoping. Added missing desktop chrome allowlist entries; all four generated translations validated. Diagnostic page-only bypass let operator see providers and attempt a turn; bypass is not shipped proof. Operator turn failed isolated runtime Git ancestry due to principal explicit disposable storage override inside checkout. Stop diagnostic app and relocate isolated debug data outside checkout without weakening guard or changing normal user storage. Final package rebuild ongoing.
- `S04` Documented manual storage relocation completed while all diagnostic package processes were stopped. Complete root including encrypted profile material and agent identity moved to C:/Users/hello/AppData/Local/cadrumo-provider-sign-in-dev. 5858 files and 171284433 bytes preserved; zero source files remain and old source root retired to empty-directory archive. First Windows cross-volume Move-Item stopped on hidden/read-only entries; completed by validated per-file Force moves with no overwrites. A cleanup command was policy rejected; safe alternative retained empty directories rather than recursively deleting them. Local untracked build launcher pins external root and refuses Git ancestry. Normal canonical data root remains unchanged.
- `S04` Relocation exposed displaced .runtime/installation.json `storage_identity,` returned as unknown sign-in observation and `runtime_root_mismatch` on password logout. With all package processes stopped, preserved old nonsecret installation record outside .runtime; production admission generated fresh root-bound installation. Password-verified config logout then actual GUI password login succeeded. Fresh installation invalidates previous automation/session bindings; existing profile/keystore/provider files retained. Normal app PID34956 reached `agent_ready` and showed translated Iniciar sesion plus API-key controls without diagnostic bypass. Actual GUI minimal Codex/gpt-5.5 prompt created a private home under external data root and reached Codex turn started. `Window_close_requested` occurred before model completion; no completed model turn or OAuth completion claimed. App remains closed. Local build/windows-x64/launch-provider-sign-in-dev.ps1 pins external debug root for repeat launches. Broader repository failures from S03 remain recorded.
