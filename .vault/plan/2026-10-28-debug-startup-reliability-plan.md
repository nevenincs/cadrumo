---
tags:
  - '#plan'
  - '#debug-startup-reliability'
date: '2026-10-28'
tier: L1
related:
  - '[[2026-10-13-provider-settings-adr]]'
  - '[[2026-10-16-idle-churn-adr]]'
modified: '2026-10-28'
body_schema: body-v2
body_hash: 'sha256:d54c50b7de25b5db16f852d6616877a501bb229ddc82cea931e3dbf859061dfc'
---

# `debug-startup-reliability` plan

## Description

Approved 2026-10-28. The user requests diagnosis and fixes for current debug-build warnings and first-launch agent failures, explicitly authorizes continued work alongside a parallel Claude session, and requires focused commits as work progresses. Reuse accepted provider-settings exact-service admission and idle-churn peer-recheck constraints unchanged. Startup budgets and moving slow verification outside a profile guard with authority revalidation are implementation corrections; no new persisted schema, public authority boundary or costly decision is introduced. The supplied workbench warnings describe completed nested reads; preserve consistency rechecks and record unproven performance causes honestly.

## Steps

- [ ] `S01` - Align desktop agent startup and admission waits with the runtime exchange budget and cover cold readiness boundaries; `native/desktop/src-tauri/src/agent, src/cadrumo_client/transport frontend service admission, and owning tests`.
- [x] `S02` - Release the profile guard during slow service peer verification and reject retiring connections before admission or record access; `src/cadrumo_runtime/host/profile_connection_services.py, profile_connection_extension_records.py, profile_connection_sessions.py, profile_host.py and owning tests`.
- [ ] `S03` - Review integrated fixes and record redacted warning triage with verified outcomes and remaining measurement gaps; `.vault/audit debug-startup-reliability and owning verification runners`.

## Parallelization

S01 and S02 may run concurrently with disjoint ownership. Sol 6.1 high owns native agent startup/admission deadlines and client admission timeouts for S01. Sol 6.1 high owns runtime service admission and extension-record guards and their tests for S02. Root owns governance, commits, shared expensive checks and integrated review. Luna 6 agents supply read-only module and log summaries. Preserve concurrent Claude edits. S03 follows both implementation Steps.

## Verification

Exercise startup deadline boundaries and exact service authority through owning native/client tests and deterministic runtime interleavings. Verify unrelated profile status/lock can progress during blocked verification and stale authority is denied after revocation or disconnect. Run configured lint, formatting, types and applicable broader gates. Preserve encrypted custody and unknown mutation outcomes. Distinguish source/regression acceptance from a rebuilt live cold launch; record any remaining evidence gaps.
