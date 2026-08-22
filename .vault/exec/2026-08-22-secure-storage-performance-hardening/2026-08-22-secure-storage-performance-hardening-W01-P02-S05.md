---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:7dd1541c31fba41be5235953c04fdcf930db7629dcd9bfd8231843c80c09abc3'
step_id: 'S05'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Add a reusable fresh-process profiler for resolution, invocation, imports, Pydantic construction, filesystem changes, and storage operations

## Scope

- `src/cadrumo/tests/cli_performance.py`

## Description

- Run resolution and invocation in independent fresh interpreters against
  distinct clones of one starting storage state.
- Resolve exact live command paths through Click while transporting synthetic
  invocation values through a user-private request file outside process argv.
- Capture wall time, module and capability-family deltas, Pydantic validation,
  filesystem effects, storage-boundary calls, exit status, and terminal output
  in a dedicated machine-readable envelope.
- Return structured timeout, missing-envelope, and child-exception outcomes
  without embedding invocation values or child diagnostics.
- Add a planted fresh-process self-check covering aliased Path operations,
  native `os.open`, an aliased real storage call, constructor validation, and
  `model_validate`.
- Resolve every high- and medium-severity independent review finding before
  closure.

## Outcome

`profile_cli_path` now supplies reusable cold resolution and invocation
observations for any live CLI path without warming one phase from the other.
The observation reports exact imported modules and registry, crypto, custody,
keyring, and storage families; Pydantic validator calls; relative filesystem
deltas and audited operations; storage-boundary call owners; exit and terminal
output; and secret-free structured failure state.

Scoped Ruff and `ty` checks passed. Six real-subprocess integration tests passed
in 49.40 seconds, including the instrumentation bite proof and timeout lane.
The independent re-review approved with no critical, high, or medium findings.

## Notes

The first review rejected raw JSON argv transport, inferred command-token
parsing, reuse of one storage root, incomplete Pydantic measurement, broad but
unproven instrumentation, and exception-only timeout handling. The final shape
uses explicit command paths, private request-file transport, equal-state cloned
roots, `SchemaValidator.validate_python` observation, a planted real-operation
self-check, and structured failure results. Budgets, calibration, and baseline
distributions remain intentionally owned by S06 and S07.
