---
tags:
  - '#plan'
  - '#client-concurrency'
date: '2026-10-26'
tier: L1
related:
  - '[[2026-10-16-idle-churn-adr]]'
  - '[[2026-10-17-idle-churn-operation-observation-adr]]'
modified: '2026-10-26'
body_schema: body-v2
body_hash: 'sha256:f3a6406d1882df158b42bfe6667eacffd6654b4d7ba7120715d1b8841a950b78'
---

# `client-concurrency` plan

## Description

Approved 2026-10-26. The user requested benchmarking, review and fixes of cadrumo_client threads, sessions, async waits and Rust/Python consumers, with read-only Luna 6 Max discovery assistance. Existing accepted idle-churn decisions govern event-driven observation and connection-bound authority. Repair implementation within those constraints; no new protocol or authority decision is proposed. Preserve existing shared-worktree edits and integrate the concurrent runtime session's changes without reverting them.

## Steps

- [x] `S01` - Repair Python disconnect delivery and async cue scheduling with native regressions and before/after benchmarks; `src/cadrumo_client/transport`.
- [x] `S02` - Enforce Rust exchange deadlines and race-free subscriptions and verify native consumers; `native/application/src/runtime_client.rs`.
- [ ] `S03` - Repair Python consumer wait misuse and review retry paths, then run integrated verification; `src/cadrumo_client and Python consumers`.
- [ ] `S04` - Build current package, run full native runtime lifecycle and Rust package verification, and fix related verification failures; `native client/package lifecycle, Python live consumers, and related quality gates`.

## Parallelization

Read-only Python transport, Python consumer and Rust consumer discovery run concurrently through Luna 6 Max agents. The principal owns implementation and verification, preserving concurrent runtime/backend edits.

## Verification

Reproduce lifecycle and deadline defects, exercise native channel waits and async cue delivery, benchmark cue scheduling before and after, and run focused consumer tests and configured static checks. Scratch belongs in `.tmp/client-concurrency/`. Report infrastructure limits and existing failures separately.
