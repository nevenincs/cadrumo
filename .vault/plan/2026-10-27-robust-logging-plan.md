---
tags:
  - '#plan'
  - '#robust-logging'
date: '2026-10-27'
tier: L1
related:
  - '[[2026-10-27-robust-logging-adr]]'
modified: '2026-10-27'
body_schema: body-v2
body_hash: 'sha256:e8ccdc1c39453e98af8e2f462e725c075a86ea61d1714969d1be05067403b797'
---

# Robust logging implementation

## Description

Approved 2026-10-27. The user explicitly instructed fixing logging defects throughout the codebase, making logging robust, fast, dependable and thread safe, benchmarking it and continuing corrections. The related accepted ADR governs bounded asynchronous dispatch, redaction, loss visibility, sink isolation and shutdown. Shared Python and native diagnostics are in scope; operation journals and command result contracts retain their durability and authority.

## Steps

- [ ] `S01` - Implement bounded Python diagnostic dispatch with adversarial tests; `src/cadrumo/core/logging.py, diagnostic_dispatch.py, log_file_handler.py, core logging tests, dev/ci/logging_benchmark.py and scoped import metadata`.
- [ ] `S02` - Isolate native diagnostics and restore worker debug enrollment with responsiveness tests; `native/application/src/diagnostics, native/application/tests, src/cadrumo_runtime/host/worker.py and worker tests`.
- [ ] `S03` - Benchmark, profile and harden integrated logging and review the completed work; `logging benchmark and worker probes, py-spy and handle evidence, scoped corrections, shared verification gates`.

## Parallelization

Execute sequentially in this session. Preserve other sessions' unrelated work and commit only scoped paths. The calendar-repair session has stopped its overlapping logging edits and handed over compatible settings-context/type/test fixes. No subagents are assigned.

## Verification

Exercise blocked sinks and filters, malformed and large record values, saturation, recursion, thread/fork safety, context and routing, rotation and bounded shutdown. Run scoped Python tests and lint/type gates, shared import/code checks after source stabilizes, and native CMake tests. Benchmark producer latency and throughput under healthy, slow and blocked outputs. Use py-spy and native handle/frame observations; rerun worker lease churn with logging enabled. Review the integrated implementation at completion.
