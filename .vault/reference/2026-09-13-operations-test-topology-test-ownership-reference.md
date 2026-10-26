---
tags:
  - '#reference'
  - '#operations-test-topology'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:9694d1d2d33866319df1db44b8a8bb4c6b7cf4f0614f19dc44c2bb18e4665a1c'
related: []
---

# `operations-test-topology` reference: `Operations test topology ownership`

The operations test suite contains two distinct seams: application contract
proofs and integration proofs over durable journal, lease, and secure-reference
adapters. The governing topology ADRs (`2026-08-11-tui-architecture-adr` and
the import-centralisation decisions) place real persistence/composition proofs
under the adapter test package; inward application tests must remain adapter
free and use protocol-conforming fakes.

## Summary

The six measured targets had 14 adapter import occurrences in their original
application-test locations: projection services (4), supervisor replay (4),
observation (2), restart reconciliation (2), financial operand dependency
receipt (1), and supervisor recovery (1). The first four modules are
real-adapter integration proofs and belong in
`cadrumo.adapters.persistence.operations.tests`; their application imports
must become canonical absolute imports after relocation. The restart child
process must import its relocated module directly.

The financial operand dependency receipt module is otherwise an inward
contract test. Its one real-filesystem composition assertion belongs beside the
custody adapter tests, while the remaining protocol/schema and non-retention
assertions stay in `cadrumo.application.operations.tests`. The recovery proof
is likewise an adapter-owned integration test. No compatibility module,
forwarder, alias, or production helper is needed.
