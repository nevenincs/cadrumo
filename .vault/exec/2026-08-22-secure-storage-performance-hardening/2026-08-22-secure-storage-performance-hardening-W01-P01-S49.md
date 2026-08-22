---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:e53371275ebfef9e64b7b044f391f9dd0fd8a9b876c262d9b21ca7a689efff8e'
step_id: 'S49'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Attach execution policy to every ledger subtree callback and group while retaining legacy risk rows until mandatory S52 consumer migration and deletion

## Scope

- `src/cadrumo/entrypoints/cli/ ledger modules`

## Description

- Attached immutable, callback-local execution policy to every live ledger root,
  group, and leaf without introducing a command-path authority.
- Preserved inert group help and missing-command behavior while retaining the
  executable `participation` callback.
- Declared maximum conditional network, Google, calculation, encrypted-fact,
  destructive, handoff, and profile-bound write authority at each owning callback.
- Added a dynamic live-census exact-set gate, external unclassified and
  downgraded-policy specimens, representative authority assertions, in-process
  behavior coverage, and a real-process help probe.
- Retained the legacy risk rows strictly until the mandatory S52 consumer
  migration removes every row and deletes the keyed table.

## Outcome

The live installed tree exposed 85 ledger nodes; all 85 carried a policy and
none were unclassified. Focused Ruff and type checks passed. The post-fix
policy, ledger-spine selection, and participation lane completed with 15 passing
tests; the focused policy module independently completed with six passing tests.
The planted downgraded callback proved that semantic network under-declaration
reds the same assertion used against the live callbacks.

Independent review initially withheld approval because six callbacks omitted
conditional ECB, model, or Google authority. Ledger add/import, invoice
add/import, evidence confirm, and document linking were corrected and their
live projections were pinned. Re-review approved with no critical or high
finding remaining.

## Notes

The source commit was serialized by the campaign supervisor as `caa422240b`
while this executor was validating the shared tree. A later broad ledger-spine
rerun at advancing HEAD produced three unrelated existing contract failures:
the already-mounted `detach` verb is absent from an old fixed roster/count, and
one help assertion assumes English while the active output was Spanish. These
failures are not caused or hidden by policy attachment; the S49-owned dynamic
policy gate remained green. A transient peer user-profile import regression
also blocked one reviewer rerun before collection and was explicitly not
reported as passing evidence.

The retained risk table is temporary ordering, not compatibility debt or a
scope reduction. S52 remains the mandatory deletion milestone after
operator-surface and MCP HITL consumers have migrated to live-node metadata.
