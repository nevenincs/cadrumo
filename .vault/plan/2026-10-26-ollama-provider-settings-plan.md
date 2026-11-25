---
tags:
  - '#plan'
  - '#ollama-provider-settings'
date: '2026-10-26'
tier: L1
related:
  - '[[2026-10-25-agent-owned-models-adr]]'
  - '[[2026-10-24-rust-component-provisioning-adr]]'
  - '[[2026-10-13-provider-settings-adr]]'
modified: '2026-10-26'
body_schema: body-v2
body_hash: 'sha256:e6870435508395ddbdd5b14f6e5fbc03191cb577e779e555f24dbd3e9e95b27a'
---

# `ollama-provider-settings` plan

Fold local model provisioning into the Ollama lane of the desktop provider settings.

## Description

Approved 2026-10-26. Basis: the owner's request of 2026-10-26 in conversation to fold the existing local model provisioning into the Ollama provider settings, with enable/disable and download/remove controls and the preferred vision models kept primary, and the owner's answers to the removal, switch and download questions recorded in the 2026-10-26 amendments of both governing ADRs.

Decision coverage: `2026-10-25-agent-owned-models-adr` (catalogue, per-role selection, recommendations and their placement, amendment 2026-10-26) governs S03 and S04. `2026-10-24-rust-component-provisioning-adr` (engine ownership, desktop exposure, per-model removal and turned-off lane admission, amendment 2026-10-26) governs S01 and S02. `2026-10-13-provider-settings-adr` governs the lane switch S03 reuses unchanged. No other decision is involved.

S01 belongs to the session that owns `native/application/src/provisioning`; this plan's S02 and S03 consume it and do not change its other contracts. The catalogue's served order, its `installed` flag and its recommended entries come from cadrumo-agent and are rendered, never re-ranked.

## Steps

- [x] `S01` - Add an engine operation that removes one named local model under the local_ai writer lock, keeping the program, receipt, other models and shared layers (owned by the provisioning session); `native/application/src/provisioning/engine.rs, local_ai/models.rs`.
- [x] `S02` - Admit only turned-on keyless lanes and expose a desktop remove-model command that clears the model's role selections first; `native/desktop/src-tauri/src/shell/setup/admission.rs, mod.rs, components.rs, wire.rs and tests`.
- [x] `S03` - Render the Ollama lane's local models in provider settings: switch, recommended vision entries first, size, vision, licence, installed state and roles, Download that picks roles then opens setup review, Remove; `native/desktop/frontend/src/components/settings/ProviderSettings.tsx, LocalModels.tsx, AgentColumn.tsx, shell/setup.ts, host.ts, tauriHost.ts, ipc/contract.ts`.
- [x] `S04` - Author the local-model strings in en, es, ca and hu through dev.locales; `canonical desktop locale sources`.
- [x] `S05` - Add the keyless-lane scenario and fixture facts and run the desktop frontend type, lint and Playwright gates plus the CMake desktop host tests; `native/desktop/frontend/tests/scenarios/local-models.spec.ts, src/dev/fixtures/agentCatalog.ts, src/dev/setupFixture.ts`.

## Parallelization

S01 and the admission half of S02 are independent. The remove-model command of S02 waits on S01. S03 can build against the S02 wire with a fixture and lands after S02. S04 and S05 follow S03.

## Verification

- Admission tests prove a turned-off keyless lane hands the engine no model and a turned-on one still does.
- Engine and host tests prove removing one model keeps the program, the receipt, other models and shared layers, and that the model's role selections are cleared first.
- Frontend tests and stories show the keyless lane's model list in the agent's order with recommended vision entries leading, Download routing through role choice and the setup review, Remove, and hidden model controls while the lane is off.
- The desktop frontend type, lint and test gates, the setup cargo tests and the locale coverage check pass.
