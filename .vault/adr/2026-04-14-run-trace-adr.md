---
name: run-trace observability ADR
description: Architecture decisions for project-wide run_id propagation, JSONL audit log, and deterministic dry-run replay
tags:
  - "#adr"
  - "#run-trace"
date: '2026-04-14'
modified: '2026-07-17'
related:
  - "[[2026-04-14-run-trace-research]]"
  - "[[2026-04-14-run-trace-plan]]"
  - "[[2026-04-12-workflow-engine-adr]]"
---
# run-trace observability ADR | (**status:** `accepted`)

## Context

Cadrumo needs one structured run trace that propagates through nested and
asynchronous application work, persists secret-free diagnostic evidence, and
supports deterministic read-only replay. The original implementation has been
consolidated into the core observability package; former product namespaces and
settings names are not extension points.

## Decision

### One core observability authority

`src/cadrumo/core/observability` owns run context propagation, strict trace and
event models, JSONL emission, persistence, redaction, replay, golden-envelope
comparison, fingerprinting, and observability errors. Consumers import only
from `cadrumo.core.observability`; underscored modules remain internal.

`run_context()` is the outer lifecycle boundary. The outermost context mints a
validated 16-character run identifier, captures corpus, database, and
certificate fingerprints, attaches one `JsonlRunSink`, emits step boundaries,
and persists the final `RunTrace`. Nested contexts reuse the run identifier and
push only a nested step identifier. Context variables propagate across normal
async task boundaries; detached threads must copy or re-enter the context.

`record_event()` is the single structured emission primitive. It requires an
active run context and emits a strict `RunEvent` through the standard logging
pipeline. Event payloads use the closed typed variants in
`cadrumo.core.observability`; arbitrary untyped dictionaries are not a durable
event contract.

### Diagnostic persistence and retention

`Settings.cadrumo_runs_dir` is the sole run-store root. Each valid run directory
contains `trace.json`, `events.jsonl`, and, when a result envelope was emitted,
`envelope.json`. Run identifiers are validated before path composition. Trace
and event string leaves pass through the DIAGNOSTIC redaction rules before
serialization, and every read revalidates the strict pydantic record.

`Settings.cadrumo_runs_retention_days` defines the retention window.
`prune_run_traces()` removes only valid run directories older than that window,
and `save_trace()` invokes pruning best-effort after a successful save. A
retention failure must not invalidate the trace that was just persisted.

### Replay is deterministic and fail-closed

`cadrumo.core.observability.replay_run()` loads the original trace, recomputes
the current fingerprints, and refuses corpus or database drift before invoking
the recorded entrypoint. Replay is read-only, records its source run identifier,
and can compare the newly emitted schema envelope with the captured golden
envelope. Missing, malformed, incompatible, or divergent evidence produces a
typed observability error rather than a best-effort reproduction claim.

### Error and ownership boundaries

Observability errors derive from `CadrumoObservabilityError` and the shared
`CadrumoError` hierarchy. Sink teardown and final boundary-event emission are
best-effort so they cannot mask the yielded operation's primary exception.
Trace persistence failure is raised when the operation itself succeeded; a
failed operation remains the primary failure.

## Consequences

- Run tracing has one public `cadrumo.core.observability` facade.
- Run records are bounded by explicit retention and diagnostic redaction.
- Replay proves fingerprint and optional envelope parity or refuses.
- Instrumented CLI and application call sites share the same context and event
  contracts without recreating observability logic.

## Verification

Core observability tests cover strict model validation, context propagation,
nested contexts, detached-thread refusal, JSONL redaction, run identifier path
safety, retention, replay drift refusal, and golden-envelope parity. Settings
tests bind `cadrumo_runs_dir` and `cadrumo_runs_retention_days` to the same live
store and lifecycle.
