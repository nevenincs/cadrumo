---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:cdde3bf737e25d34abc241696d2dc620b9502d814ac851fb5834801220c8f0b1'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# `secure-storage-performance-hardening` audit: `W01.P02.S05 profiler implementation review`

## Scope

Independently review the reusable cold-process CLI profiler against the accepted
performance-hardening decision. The review covered timing boundaries, live path
resolution, process and storage isolation, import and construction attribution,
filesystem and storage-operation instrumentation, envelope integrity, timeout
and crash behavior, secret handling, and whether the tests prove each detector
bites.

## Findings

### profiler-review | high | Invocation values crossed observable transport boundaries

The first implementation placed raw CLI values in JSON on the child process
command line, retained them in the result, and included child stderr in a
missing-envelope exception. It now accepts only synthetic non-secret values,
transports them in a permission-restricted user-private request file, deletes
that file immediately after reading, omits values from results, and returns
secret-free structured failures.

### profiler-review | high | Resolution and storage state were not independently cold

Token inference stopped at options and mistook positional values for child
commands, while sequential probes shared a mutable storage root. Resolution now
takes the exact live path separately from invocation values. Both phases receive
distinct symlink-preserving clones whose initial content digest is equal and
whose hashed root identity differs.

### profiler-review | high | Attribution detectors lacked a planted bite proof

The initial Pydantic assertion was vacuous and the broad filesystem and storage
maps did not prove aliases or native operations were observable. A dedicated
fresh child now performs constructor and `model_validate` validation, aliased
Path and native `os.open` writes, and an aliased real storage-boundary call.
Tests assert all four observations, including native flag classification.

### profiler-review | medium | Timeouts and hard child loss had no structured result

The original transport raised `TimeoutExpired` or a stderr-bearing runtime
exception. Both timeout and missing-envelope paths now return typed,
secret-free observations and let the temporary context remove request and
result state.

The re-review approved the final implementation with no remaining critical,
high, or medium finding. Six integration tests passed.

## Recommendations

No S05 recommendation remains open. Calibration, ratio budgets, repeated-sample
statistics, and baseline distributions remain with S06 and S07 rather than
being smuggled into this instrumentation Step.
