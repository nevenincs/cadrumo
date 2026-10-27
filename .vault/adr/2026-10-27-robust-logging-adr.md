---
tags:
  - '#adr'
  - '#robust-logging'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:2aab6b8170417450ced3e2142712a6e77f9f83b6cf25b2097b5f04176c719a7f'
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
