---
tags:
  - '#plan'
  - '#debug-startup-reliability'
date: '2026-10-28'
tier: L1
related:
  - '[[2026-10-13-provider-settings-adr]]'
  - '[[2026-10-16-idle-churn-adr]]'
  - '[[2026-10-28-debug-startup-reliability-adr]]'
modified: '2026-10-28'
body_schema: body-v2
body_hash: 'sha256:13f71b4c72e5d2b41e40a115682a1c9a778f70fb08ebde85746a771cb89d5a7a'
---

# `debug-startup-reliability` plan

## Description

Approved 2026-10-28. The user authorizes diagnosis/fixes for current Debug-build warnings and first-login agent failures, work alongside the parallel Claude session, and focused commits as work progresses. S01/S02 reuse accepted provider-settings and idle-churn constraints as routine deadline/guard corrections. The user's later explicit instruction requires signal/slot-driven GUI and multi-service orchestration with hard times only as absolute last-resort timeouts. Accepted2026-10-28-debug-startup-reliability-adr governs the resulting correlated pending-login/service protocols, readiness/cancellation ownership and centralized timeout policy in S04/S05/S06. The original timeout increases are recorded as mitigation, not final fulfillment of that requirement. Preserve workbench snapshot consistency checks and report unproven causes honestly.

## Steps

- [x] `S01` - Align desktop agent startup and admission waits with the runtime exchange budget and cover cold readiness boundaries; `native/desktop/src-tauri/src/agent, src/cadrumo_client/transport frontend service admission, and owning tests`.
- [x] `S02` - Release the profile guard during slow service peer verification and reject retiring connections before admission or record access; `src/cadrumo_runtime/host/profile_connection_services.py, profile_connection_extension_records.py, profile_connection_sessions.py, profile_host.py and owning tests`.
- [x] `S06` - Replace native agent and service admission phase waits with generation-bound asynchronous completions and free exchange slots while pending; `native agent supervisor/person/runtime client and manager readiness, neutral service pending contracts/runtime service admission and owning tests`.
- [x] `S04` - Make first profile login and worker readiness use correlated pending completion/cancellation signals and one native GUI login path; `runtime worker startup/admission/session owner/login handlers, profile login contracts, Python frontend login, native GUI sign-in, frontend sign-in and owning tests`.
- [x] `S05` - Centralize timeout policy and make hosted agent ready/stop waits respond to readiness, exit and cancellation signals; `neutral timeout policy and native projection, agent service controller/process/service/launcher, desktop agent timeout presentation/locales and owning tests`.
- [x] `S07` - Carry the first-login absolute timeout deadline through supervised KDF proof without resetting queue, attestation or launch budgets; `canonical profile candidate/proof custody/KDF adapters, runtime profile proof seam and owning tests`.
- [x] `S08` - Replace KDF permit polling with cancellable same-domain OS lock signaling while preserving legacy worker interoperation and containment; `custody KDF lease adapter and private leaf helper, generated module inventory and owning cross-process tests`.
- [x] `S09` - Make agent preflight, store lifecycle and catalogue reads consume one startup timeout and cancellation owner without per-phase failure timers; `agent service composition/controller/store lifecycle, provider catalogues, contained invocation runner and owning tests`.
- [x] `S10` - Make GUI helper orchestration wait on capacity and child exit signals under the shared timeout policy; `native desktop managed child/process helper owners and tests`.
- [x] `S11` - Consolidate orchestration naming, protocol codes and user wording on timeout and cut over the current wire cohort; `neutral/native/runtime/agent timeout consumers, transport contracts, UI locale owners and affected documentation`.
- [x] `S12` - Propagate exact proof-attempt cancellation independently of the busy proof channel and settle queued KDF work promptly; `private worker cancellation channel and token registry, canonical proof/KDF cancellation plumbing and real held-permit regressions`.
- [x] `S03` - Review integrated fixes and record redacted warning triage with verified outcomes and remaining measurement gaps; `.vault/audit debug-startup-reliability and owning verification runners`.

## Parallelization

Sol6.1 high owns S04 runtime worker readiness, pending human login and native GUI sign-in, S06 pending service admission and native agent supervision, and S07/S08 custody deadline propagation and cancellable same-domain leases. The runtime and custody lanes coordinate S12 exact-proof cancellation and shared construction/admission joins. Sol6.1 medium owns S05 timeout policy and hosted-agent waits, S09 preflight/catalogue/credential ownership and S10 helper signal orchestration. Shared contracts and transport methods have one active writer at a time; native opening-cancellation corrections remain with the high native lane. One native builder runs isolated compile/test/lint checks after shared source is stable. Root owns S11 naming, catalogue enrollment, vault metadata, commits and broad gates. Luna6 supplies code/log summaries, while independent Sol6.1 reviewers evaluate completed changes and corrections. Preserve Claude edits, serialize overlapping writes and commit owned paths/hunks. S03 records integrated review and the final verification limits.

## Verification

Prove delayed readiness/proof/admission beyond former phase limits without long real sleeps; free GUI/person exchange slots while pending; exact correlated terminal claim/cancel without proof or mutation replay; prompt wake on peer/process exit, stop, cancellation, lock and profile/generation changes; no stale publication; one key-free worker-ready result after dispatchers exist; shared absolute timeout budget through dependent phases and cleanup; committed-result/UNKNOWN preservation; and a first-login to admitted-service typed-profile read path without retry. Verify selected/named target handover through the canonical product selection owner. Run owning Python/native/frontend tests, configured lint/format/types and applicable broader gates on stable inputs, retaining failure and environment evidence. Run new module inventory generation once all production modules are known. Independently review integrated workflows and report rebuilt cold-launch acceptance separately from source/regression evidence.
