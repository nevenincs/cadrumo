---
tags:
  - '#plan'
  - '#provider-sign-in'
date: '2026-10-17'
tier: L1
related:
  - '[[2026-10-13-provider-settings-adr]]'
  - '[[2026-10-13-native-agent-adr]]'
  - '[[2026-10-05-desktop-design-system-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:a3bc8dc640027ed4d155bf0c77a17d3f8881f598efa61b4e87ef022b22f6132e'
---

# `provider-sign-in` plan

## Description

Approved 2026-10-17

The owner explicitly asked the principal agent to integrate the completed hidden CLI helper with the Cadrumo Tauri application, using Luna max readers to map the implementation. The owning checkout is feature/tui; main lacks the agent panel. Reuse provider-settings ownership, native-agent package provenance and desktop-design-system presentation decisions. This implements their existing service/person/UI boundaries with transient sign-in commands; it adds no credential store, runtime authority or model execution. The helper protocol is defined in the sibling cadrumo-agent main checkout, docs/operations.rst and cli/_auth_protocol.py. No commit or push is authorized.

Discovery: Luna max readers mapped service.py preparation, AgentHost.administer, providerSettings.ts, components/settings/ProviderSettings.tsx and the CMake invocation contract. The service will own the helper and its bounded lifetime. Native token-checked commands relay start/status/cancel; observation occurs only during a user-started attempt and never extends person activity. The UI opens the provider page and keeps URL/device codes transient. Claude remains explicitly unsupported until the agent declares GUI support. Completed sign-in and real-turn capability require human/provider participation and are separate from component evidence.

## Steps

- [x] `S01` - Own hidden helper lifecycle and transient authenticated sign-in administration; `src/cadrumo_agent_service and native/application-environment.toml`.
- [x] `S02` - Connect token-checked native commands to the localized provider sign-in dialog; `native/desktop and src/cadrumo_agent_service/locales`.
- [ ] `S03` - Verify integration and document evidence and remaining live-account gates; `tests and native/CONTRACT.md`.
- [ ] `S04` - Repair the Windows local profile login prerequisite exposed by packaged sign-in verification and verify the real GUI flow; `src/cadrumo_runtime and its native login tests and packaged desktop verification`.

## Parallelization

Principal owns service/process integration, package assembly and shared verification. After the typed contract is fixed, one Luna max worker owns frontend dialog, wiring, presentation tests and localized strings; another owns native provider_settings commands/wire and application-environment invocations. Native and frontend checks have their respective worker owners. The principal integrates both with service behavior. Other readers and the reviewer remain read-only. Writers preserve concurrent work and do not share implementation files. The principal integrates and reviews all work.

## Verification

Run focused pure wire and real-process/service lifecycle checks, native tests and frontend type/lint/build/interaction checks through configured tooling. Verify profile/session loss, duplicate attempts, cancellation, terminal URL clearing and failure reporting. Package/helper integration uses CMake-built images, never checkout injection. Report unavailable prerequisites and human-completed OAuth/real-turn gates explicitly; do not claim capability from fixtures. No permanent service or login registration is created.
