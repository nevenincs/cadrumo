---
tags:
  - '#plan'
  - '#runtime-concurrency-review'
date: '2026-10-26'
tier: L1
related:
  - '[[2026-10-16-idle-churn-adr]]'
  - '[[2026-10-17-idle-churn-operation-observation-adr]]'
  - '[[2026-10-22-worker-authorization-channel-adr]]'
  - '[[2026-10-22-startup-performance-authority-observation-adr]]'
modified: '2026-10-26'
body_schema: body-v2
body_hash: 'sha256:24a6894c121e0c22f2f5c45b8f2c347854d6576a87853735a69387f38f70e49a'
---

# `runtime-concurrency-review` plan

## Description

Approved 2026-10-26

The user requested benchmarking, review and fixes for runtime threads, sessions, waits, async execution and Rust/Python connections, with Luna read-only assistance. Preserve unrelated concurrent edits. Reuse the linked accepted event-driven observation, worker connection reuse and authority observation decisions without changing protocol or authority boundaries.

## Steps

- [x] `S01` - Wake subscribed Python clients on every terminal connection closure and cover native disconnect paths; `src/cadrumo_client/transport`.
- [ ] `S02` - Fix confirmed runtime and Rust client lifecycle findings and verify benchmarks with an integrated review; `src/cadrumo_runtime, src/cadrumo_client, native and .vault/audit`.

## Parallelization

The principal agent implements sequentially and owns benchmarks and checks. Luna agents independently summarize runtime, Python client and Rust client code without edits.

## Verification

Run native IPC latency, idle, disconnect, contention and shutdown checks before and after fixes. Regressions must fail before fixes. Run configured formatting, lint, typing and applicable gates, distinguishing unrelated failures. Review session authority, cancellation and cleanup across both client languages; record findings and benchmark limits in an audit.
