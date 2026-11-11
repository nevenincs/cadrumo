---
tags:
  - '#plan'
  - '#runtime-connection-performance'
date: '2026-10-26'
tier: L1
related:
  - '[[2026-10-16-idle-churn-adr]]'
  - '[[2026-10-17-idle-churn-operation-observation-adr]]'
modified: '2026-10-26'
body_schema: body-v2
body_hash: 'sha256:b49a08eec367121e4b747bc312f1c6553dce2b481fb9a7601ddcc1a13ec78aac'
---

# `runtime-connection-performance` plan

## Description

Approved 2026-10-26. The user requests benchmarking, review and fixes of runtime threads, sessions, waits, async and Rust/Python client connections for authentication, profile reads/writes, calculation and Modelo provisioning. Luna 6 max agents were authorized for the initial read-only investigation. The user subsequently explicitly authorized Sol 6.1 medium and high agents to implement the four remaining measured workstreams while root continues attributing the long journal holds. Existing accepted idle-churn decisions govern event-driven observation and unchanged authority and settlement contracts. This work preserves unrelated worktree edits. Semantic discovery was attempted but the RAG service could not start in this client-only installation; targeted discovery was used.

## Steps

- [x] `S01` - Restore and run current native profile and Modelo benchmark entrypoints, retaining payload-free baseline evidence; `dev/ci/profile_wizard_benchmark.py, dev/ci/modelo_runtime_benchmark.py and isolated build/runtime-connection-review-20261026 outputs`.
- [x] `S03` - Repair reproduced runtime and client concurrency or event-delivery defects with regression coverage; `src/cadrumo_runtime, src/cadrumo_client, native runtime client owners and their owning tests`.
- [x] `S04` - Reduce journal read lock hold time while preserving captured-record consistency, legacy purge exclusion and serialized writes; verify with a deterministic interleaving regression; `src/cadrumo/adapters/persistence/operations/journal.py and owning journal, observation, purge and settlement tests`.
- [x] `S05` - Attribute long journal lock holds to capture, validation, serialization, lease, durable filesystem and scheduling phases with payload-free measurements; `dev/ci/runtime_journal_benchmark.py and isolated benchmark artifacts`.
- [ ] `S06` - Fix measured journal contention and operation deadline failures under concurrent load while preserving durable settlement and unknown outcomes; `journal and lease persistence, operation orchestration and owning regression tests`.
- [x] `S07` - Measure and optimize repeated Modelo catalogue loading and decoding while preserving authority freshness and profile isolation; `Modelo registry catalogue loading and decoding owners, corresponding tests and Modelo benchmark`.
- [x] `S08` - Separate authentication, profile read and profile write latency and implement evidence-backed local fixes; `profile benchmark instrumentation and owning authentication or profile flow tests`.
- [ ] `S02` - Measure candidate behavior and review integrated authentication, profile and operation paths; `owning benchmark/test runners and runtime-connection-performance audit`.

## Parallelization

Root owns S05 journal phase measurements, shared governance, integration review and coordination of expensive checks. S06 may run with S07 and S08: Sol 6.1 high owns journal/lease persistence and operation deadline work; Sol 6.1 high owns Modelo catalogue loading/decoding; Sol 6.1 medium owns authentication/profile measurement instrumentation and its tests. Workers preserve all existing edits and announce exact source ownership before touching shared files. Root serializes plan, ledger and commit writes. Heavy benchmark runs are serialized through root; independent focused tests may run concurrently with bounded workers. No worker runs the full corpus or whole-code gate independently.

## Verification

Exercise real native transport, encrypted synthetic-profile reads and writes, and the Modelo calculation/export journey. Reproduce fixes with behavioral regressions and retain payload-free measurements. Run owning tests and configured style, format, type and applicable broader gates. Preserve unknown settlement, native custody and no-lost-frame cancellation. Review integrated changes and report environment and pre-existing failures separately; no latency speedup claim follows from shared-host variation alone.
