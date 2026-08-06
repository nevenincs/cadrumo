---
tags:
  - '#adr'
  - '#aeat-verify'
date: '2026-04-24'
modified: '2026-07-17'
body_hash: 'sha256:19626ab224e2600c90972324561415e93bcca0ecee9076957192a50ad645c5b2'
related:
  - "[[2026-04-24-aeat-verify-research]]"
  - "[[2026-04-21-calc-verification-adr]]"
---
# `aeat-verify` adr: `remote-aeat-domain-and-filing-reconciliation` | (**status:** `accepted`)

## Context

Remote AEAT verification must answer whether locally held filing state agrees
with read-only evidence obtained from the authenticated Sede. The original
proposal placed this work in `aeat.remote`, composed a `StatusReader`, and kept
file-backed caches. Those packages and persistence paths no longer exist. The
live code has one adapter/application split and one secure evidence boundary.

## Decision

### Read-only Sede adapters are the transport authority

`src/cadrumo/adapters/outbound/aeat/sede` owns authenticated declaration-tree,
notification, filed-data, justificante, and related Sede reads. Its public
functions accept the typed `AeatSession` and return strict adapter records.
`src/cadrumo/adapters/outbound/aeat/verify` owns the separate read-only CSV
verification navigation. Both surfaces enforce non-mutating HTTP and browser
actions; neither implements application reconciliation or persistence.

There is no `StatusReader`, `HistoryFetcher`, `aeat.remote`, or parallel
certificate-backend adapter. Workflow integrations inject the exact Sede
callables they need, such as `walk_expedientes_tree` and
`fetch_notifications_query`.

### Application live services own capture and reconciliation

`src/cadrumo/application/live` composes authenticated Sede reads into typed
capture outcomes, filed observations, remote-state acquisition, justificante
registration, and verification results. Application services decide how a
remote observation maps to a local modelo, period, declaration, or filing
record. Adapters do not write domain state, and CLI entrypoints delegate to
these application services rather than reproducing reconciliation logic.

### Authentication is provider-owned and session-typed

Live acquisition obtains an `AeatSession` through the application auth
orchestrator and concrete `AuthProvider`. Certificate authentication is proved
only by the canonical protected-browser navigation; Cl@ve providers retain
their own typed session details. Verification consumes the resulting session
and never selects a certificate backend, handshake implementation, marker, or
per-call authentication target.

### Evidence is encrypted, bucket-scoped, and provenance-bearing

Captured remote state and verification observations persist through
`SecureObjectRepository`-backed, active-bucket repositories. Stored records
carry schema, source, revision, identity, and capture metadata needed to judge
freshness and provenance. Evidence-bearing filing records retain the evidence
bytes or a secure enrolled object, not an external filesystem link. Local
observations remain explicitly non-official until the applicable justificante
or other authoritative evidence gate is satisfied.

### Verification stays read-only and fail-closed

Remote acquisition may navigate, download, parse, compare, and persist local
evidence. It must not fill, click, submit, acknowledge remotely, or mutate an
AEAT filing. Authentication failure, unexpected navigation, ambiguous remote
identity, missing evidence, or unsupported schema returns a typed refusal or
failure outcome; it never fabricates agreement from partial data.

## Consequences

- `adapters.outbound.aeat.sede` is the sole live Sede read adapter family.
- `application.live` is the sole orchestration and secure-evidence family.
- `adapters.outbound.aeat.verify` remains a narrow CSV verification adapter,
  not a second remote-domain architecture.
- Deleted status/history/remote compatibility packages are not architectural
  extension points.
- Verification results are reproducible from typed, encrypted, provenance-rich
  evidence and cannot silently authorize a remote write.

## Verification

Architecture tests prohibit mutating Sede actions, direct adapter persistence,
and retired package imports. Real adapter and application tests exercise typed
auth sessions, Sede parsing, secure snapshot round-trips, justificante evidence
enrolment, stored-evidence reload, and read-only CSV verification.
