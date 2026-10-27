---
tags:
  - '#adr'
  - '#robust-logging'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:9aebb6dc5034ff700588af9e3fad093408a587b94952eede118dc6475182a5a3'
related:
  - "[[2026-10-27-robust-logging-research]]"
  - "[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]"
---
# `robust-logging` adr: `Bounded diagnostics independent of application progress` | (**status:** `accepted`)

## Problem Statement

Diagnostic I/O and registry-backed redaction can freeze the profile-worker event loop and cause containment. Native file writes also hold diagnostic state locks. The related research records real reproductions and profile samples.

## Decision

Accepted 2026-10-27 under the operator's explicit instruction to fix logging throughout the codebase, benchmark it and continue correcting defects. Application-owned diagnostic producers hand off bounded records without filesystem, stream, registry or arbitrary rendering work. Background processing redacts before every output sink. Slow sinks cannot hold producer/status locks, and independent outputs are isolated. Preserve emission identity and routing.

Bound queue admission and retained data. Saturation, rendering, redaction and sink failures increment non-private observable counters. Never recursively log diagnostic failure, expose raw rejected contents, create unbounded threads or fall back to synchronous I/O. Bounded drain attempts preserve healthy pending records; permanently blocked diagnostics cannot prevent shutdown. Forks cannot reuse stale thread or lock ownership. Preserve file rotation and shared-writer coordination.

Capacity, record snapshots, scheduling and drain limits are measured implementation choices. Permanently failing sinks cannot guarantee delivery. Abrupt process death may lose queued records, including panic diagnostics; the native event ring remains immediately readable. Diagnostic loss is measurable. Operation journals, authoritative audit records, command results and transport authority retain their current semantics.

## Coverage and Implementation

This refines diagnostics under the accepted supervisor stream-hygiene contract without changing its authority or journal durability. Prior synchronous diagnostic timing was an implementation behavior. Implement shared Python dispatch before rendering/redaction, bounded initialization/shutdown, worker logger enrollment and native file-write isolation, then validate adversarial cases and benchmark the complete paths. Public bounded flush is for tests and shutdown, never an authority or commit fence.

## Considerations

Diagnostics must remain private and useful under healthy operation while filesystem, registry and arbitrary formatter work may block indefinitely. A finite queue cannot promise lossless delivery during indefinite sink failure.

## Considered options

Retaining synchronous filters and handlers preserves immediate disk timing but reproduces event-loop deadline failures. One global background sink isolates producers but lets a blocked file consume stderr delivery. Bounded record dispatch with independently bounded outputs isolates both producer and sink progress and was selected.

## Constraints

Use one worker per owned output, bounded retained record data, observable refusal/failure counters, no recursive fallback and finite drain. Preserve rotation, emission identity, settings/routing and redaction before output. Do not change authoritative journal or command-result semantics.

## Implementation

Shared Python diagnostic dispatch owns snapshots and redaction; each configured sink owns a background queue. Native diagnostics retain immediate in-memory facts and enqueue bounded file work outside status locks; observers run independently. Worker first-party namespaces enroll before startup DEBUG records. Benchmark and adversarial coverage calibrate limits.

Diagnostic redaction must not borrow application registry authority, cache or admission locks. Queued diagnostic processing uses a context-only conservative lexical identity-admission scope: identity-shaped lookalikes may be hashed in logs rather than validated against live authority. Other threads, domain validation and command-result redaction keep their existing host-bound admission. This is an authorized implementation refinement of the operator's explicit prohibition on logging-induced application failures, demonstrated by the blocked-admission regression. It avoids adding a second database owner or service.

## Rationale

The original real-worker profile placed diagnostic file flush and registry-backed redaction directly on its event loop. Moving both beyond bounded admission addresses that mechanism rather than extending operation deadlines. Explicit best-effort loss under overload is preferable to application failure or unbounded retention.

## Consequences

Healthy logging can be explicitly drained at test or shutdown boundaries. Permanent stalls or abrupt process termination can lose queued diagnostics, including panic facts; counters expose saturation/failure and the native ring remains immediately readable. Thread scheduling still precludes real-time latency guarantees.
