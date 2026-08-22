---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:1e7c282a0ab1f2729f15954884e3f82e4ebc8ad18ec89fa23609a006ec3048a4'
step_id: 'S52'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Migrate operator-surface and MCP HITL consumers to live-node execution policy, remove all legacy risk rows, and delete the keyed risk table

## Scope

- `src/cadrumo/application/operator_surface and src/cadrumo/adapters/inbound/mcp`

## Description

- Delete the keyed risk module, application classification wrapper, public
  exports, mutation helper, table rows, and obsolete table-specific tests.
- Project destructive, handoff, live-write, read-only, idempotence, and
  open-world posture from callback-attached live command policy.
- Carry the immutable projection on every MCP descriptor and route runtime
  annotations, HITL, identity, elicitation, persona, direct and meta consumers
  through that descriptor object.
- Add exact live key-to-path reconciliation, physical and AST absence,
  fail-closed planted nodes, live-write blocking, rename invariance, and
  zero-additional-import consumer gates.
- Resolve every mandatory review finding and obtain independent approval.

## Outcome

The legacy keyed authority is physically absent with no shim, alias, fallback,
empty replacement table, or duplicated risk catalogue. All exposed MCP
descriptors carry their callback's live policy projection. Unknown and
unclassified commands refuse; network posture is capability-derived and key
invariant. The focused integration lane passed 81 tests, Ruff passed, the new
policy module passed `ty`, and the feature-scoped Vaultspec check passed.

## Notes

Concurrent shared-tree commit `005b1c2fdc` consumed the primary deletion and
migration paths while the Step was in progress; follow-up hardening and evidence
were kept as exact-path work. A broader MCP lane passed 52 tests and reported
two credential-campaign expectation failures about `config.passphrase.change`;
they are unrelated to S52. Broad harness `ty` continues to report existing
dynamic-facade diagnostics; the S52-owned policy module itself is clean.
