---
tags:
  - '#plan'
  - '#session-lifetime-repair'
date: '2026-10-15'
tier: L1
related:
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-08-13-profile-session-lifecycle-successor-adr]]'
modified: '2026-10-15'
body_schema: body-v2
body_hash: 'sha256:605e6793eab0e94bdb143f2ac60dc77c223b70a5a1e72fdff269dc5f0db78454'
---

# `session-lifetime-repair` plan

## Description

Approved 2026-10-15. The user reported active-use logout and application termination in the Debug package, then explicitly instructed: keep digging and fixing. Scope covers active human session lifetime, background observation/recovery, and native shutdown/crash sequencing. Existing sign-in and lifecycle decisions govern ownership and revocation. The user's requirement that active work never times out authorizes amendment of the fixed absolute cap for renewed active human sessions; record its evidence and scoped wording before implementing that policy.

## Steps

- [x] `S01` - Ground and repair active human session lifetime and uncertain OS observations; reconcile authorized policy; `src/cadrumo_runtime, src/cadrumo_client, src/cadrumo/application/user_profile, src/cadrumo/adapters/persistence/storage, .vault/adr`.
- [x] `S02` - Trace and repair native crash and desktop shutdown sequencing; `native/desktop/src-tauri, native/interpreter host paths and focused tests`.
- [x] `S03` - Repair TUI background status handling and session-loss recovery; `src/cadrumo/entrypoints/tui and focused tests`.
- [ ] `S04` - Review integrated repairs, run shared checks and verify rebuilt Debug package; `changed runtime, TUI and native files and build/windows-x64/stage/Debug/app`.

## Parallelization

S01 runtime investigation and lifetime repair is owned by the supervisor. S02 desktop shutdown/native crash investigation and repairs may be delegated concurrently to a worker owning native desktop/native host files and focused tests. S03 TUI observation and recovery may be delegated to a worker owning TUI session files and tests. Workers must not edit shared plans, ADRs or commit; supervisor serializes governance, integration checks and commits. S04 integrated review and package verification follows all repairs.

## Verification

Focused session authority, custody, TUI and native lifecycle regressions; configured lint/format/type checks for changed code. Verify logout cannot renew retired sessions, background/agent traffic cannot prolong human activity, active person activity can renew, unavailable status is not falsely reported as expiry, and shutdown settles clients before their runtime. Rebuild the Debug package and exercise synthetic profiles where feasible; do not change the user's real profile. Report any unavailable interactive/native crash proof explicitly.
