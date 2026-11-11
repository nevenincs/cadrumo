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
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
  - '[[2026-10-17-single-binary-process-tree-adr]]'
modified: '2026-10-18'
body_schema: body-v2
body_hash: 'sha256:5d93160e7f404acc10a4920fc4182d81e7273e2cdd7e3793c418d9d95041582b'
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
- [x] `S04` - Repair the Windows local profile login prerequisite exposed by packaged sign-in verification and verify the real GUI flow; `native Windows manifests and session admission and provider catalog compatibility and frontend capability display and localization and external debug storage and packaged GUI verification`.
- [x] `S05` - Repair normal-launch provider sign-in, enable declared Claude browser support and surface actionable failures; `provider executable discovery and transient browser handoff and auth diagnostics and provider sign-in UI and packaged verification`.
- [ ] `S06` - Make successful provider sign-in clear and restore the agent after the intentional authentication pause; `provider sign-in completion UI and agent service lifecycle and native supervisor integration and packaged verification`.
- [x] `S07` - Simplify provider settings with search, expandable provider groups, visible icons, clear states and plain localized messages; `native/desktop frontend provider settings and picker and packaged icon generation and four canonical provider locales and focused UI verification`.
- [x] `S08` - Present provider authentication failures with a settings action and no internal failure prose; `native/desktop frontend agent failure presentation and focused scenario tests and packaged verification`.

## Parallelization

Principal owns service/process integration, package assembly and shared verification. After the typed contract is fixed, one Luna max worker owns frontend dialog, wiring, presentation tests and localized strings; another owns native provider_settings commands/wire and application-environment invocations. Native and frontend checks have their respective worker owners. The principal integrates both with service behavior. Other readers and the reviewer remain read-only. Writers preserve concurrent work and do not share implementation files. The principal integrates and reviews all work.

## Verification

Run focused pure wire and real-process/service lifecycle checks, native tests and frontend type/lint/build/interaction checks through configured tooling. Verify profile/session loss, duplicate attempts, cancellation, terminal URL clearing and failure reporting. Package/helper integration uses CMake-built images, never checkout injection. Report unavailable prerequisites and human-completed OAuth/real-turn gates explicitly; do not claim capability from fixtures. No permanent service or login registration is created.
