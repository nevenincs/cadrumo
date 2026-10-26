---
tags:
  - '#exec'
  - '#desktop-agent-host'
date: '2026-10-13'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:12a2219f67f61ade42b91c1dfb62169f14cb9c978c047b1e91cffd56a1c93d55'
related:
  - "[[2026-10-13-desktop-agent-host-plan]]"
---

# `desktop-agent-host` ledger

## Changes

- `S03` `A` `native/desktop/src-tauri/src/agent/mod.rs`
- `S03` `A` `native/desktop/src-tauri/src/agent/launcher.rs`
- `S03` `A` `native/desktop/src-tauri/src/agent/runner.rs`
- `S03` `A` `native/desktop/src-tauri/src/agent/supervisor.rs`
- `S03` `A` `native/manager/src/process_job.rs`
- `S03` `M` `native/manager/src/lib.rs`
- `S03` `M` `native/manager/Cargo.toml`
- `S03` `M` `native/desktop/src-tauri/src/app.rs`
- `S03` `M` `native/desktop/src-tauri/src/main.rs`
- `S03` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S03` `verify:` `node native/desktop/scripts/tauri.mjs clippy-backend` -> `pass`
- `S03` `verify:` `node native/desktop/scripts/tauri.mjs test-unit agent::` -> `pass`
- `S03` `by:` `implementation-engineer`
- `S03` `M` `native/desktop/src-tauri/src/agent/runner.rs`
- `S04` `A` `native/desktop/src-tauri/src/agent/gateway.rs`
- `S04` `A` `native/desktop/src-tauri/src/agent/session.rs`
- `S04` `A` `native/desktop/src-tauri/src/agent/sse.rs`
- `S04` `A` `native/desktop/src-tauri/src/agent/stream.rs`
- `S04` `M` `native/desktop/src-tauri/src/agent/mod.rs`
- `S04` `M` `native/desktop/src-tauri/src/agent/supervisor.rs`
- `S04` `M` `native/desktop/src-tauri/src/agent/launcher.rs`
- `S04` `M` `native/desktop/src-tauri/src/agent/runner.rs`
- `S04` `M` `native/desktop/src-tauri/Cargo.toml`
- `S04` `M` `native/desktop/src-tauri/Cargo.lock`
- `S04` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S04` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S04` `verify:` `node native/desktop/scripts/tauri.mjs clippy-backend` -> `pass`
- `S04` `verify:` `node native/desktop/scripts/tauri.mjs test-unit agent` -> `pass`
- `S04` `verify:` `npx tsc --noEmit` -> `pass`
- `S04` `verify:` `npx eslint src/shell/tauriHost.ts src/ipc/contract.ts` -> `pass`
- `S04` `by:` `implementation-engineer`
- `S05` `A` `native/desktop/frontend/tests/live/attach.live.ts`
- `S05` `A` `native/desktop/frontend/tests/live/fixture.ts`
- `S05` `A` `native/desktop/frontend/tests/live/playwright.config.ts`
- `S05` `A` `native/desktop/frontend/tests/live/tsconfig.json`
- `S05` `A` `native/desktop/frontend/tests/live/README.md`
- `S06` `M` `justfile`

## Notes

- `S03` Full test-unit: 248 passed, 1 failed: `manager::tests::repeated_helpers_remain_settled_and_report_measured_latency` timed out in the full run and passed alone and with the manager tests alone; this Step changed no manager code it runs
- `S03` This Step's code landed in the checkpoint commits acd546f3a1 and 69b9dffb6e, made by another session on the owner's instruction
- `S03` Stopping now waits until the job is empty: the overrun test failed under load because a grandchild the job had ended was still exiting
- `S04` This Step's code landed in the checkpoint commits acd546f3a1 and 69b9dffb6e, made by another session on the owner's instruction
- `S04` Full test-unit: 262 passed, 1 failed: `manager::tests::repeated_helpers_remain_settled_and_report_measured_latency` timed out in the full run on a heavily loaded host and passed alone and with the manager tests alone; this Step changed no code it runs
- `S04` Mapped to agentSession.ts as committed in acd546f3a1; the contract v2 rework is pending, so the Step stays open
- `S04` Conversation-keyed commands, send and history refuse with typed codes: the launcher reports no conversation workspace, and the gateway returns no person turn id and keeps no turn order
- `S05` rows recorded retroactively on 2026-10-14 from git history; the Step was closed without a ledger row; landed in acd546f3a1 and 9e256e3a41
- `S06` rows recorded retroactively on 2026-10-14 from git history; the Step was closed without a ledger row; the desktop-agent-live recipe landed in acd546f3a1
