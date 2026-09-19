---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:15a984c8cb4adcbd982e32ce7104e36361b0eee1003b7f4d99370ff968336461'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# `deadline-window-revision-authority` audit: `real cli json deadline parity`

## Scope

Audit the real CLI JSON calendar, agenda, backlog, workflow, and explain paths for deadline-coordinate loss, duplication, reordering, or command-local redeclaration. Confirm the regressions exercise production registry and deadline owners through isolated storage rather than mocked schedules.

## Findings

### row-bearing-cli-projections | high | Calendar agenda and backlog now preserve exact quarterly cardinality

The real CLI regressions assert ordered tuples rather than sets. Each row-bearing projection must emit exactly the four Modelo 303 filing-year 2025 quarters, so a duplicate, omission, or reorder fails. The date ranges include the 2025 Q4 window that closes during 2026.

### workflow-registry-binding | high | Work creation resolves all quarterly targets through canonical revision selection

Four real JSON work-create invocations cover `1T` through `4T`. Each returned coordinate is asserted once and its `revision_id` is compared with the existing `select_revision` owner for the same filing year and period. No workflow-local revision rule is added.

### explain-native-contract | medium | Explain retains a single applicability result and engine rationale

`overview explain` does not expose obligation rows and must not grow a copied deadline-window DTO solely for cross-surface symmetry. Its regression instead proves the Modelo 303 filing year and applicability result and requires the existing engine-owned `scheduling_rationale` to be present.

### canonical-reuse-sweep | low | No CLI deadline authority was redeclared

Vaultspec RAG followed by exact symbol inspection located the established CLI runner, isolated profile fixtures, overview typed payloads, registry `select_revision`, and the application projections. Changes are confined to tests and reuse those owners directly; no resolver, parser, cadence map, supported-year horizon, deduplicator, or deadline catalogue was introduced.

## Recommendations

- Preserve ordered semantic-coordinate assertions on all row-bearing JSON projections.
- Test each surface at its native typed contract instead of manufacturing a universal CLI deadline DTO.
- Broaden this five-surface witness through the all-model fleet parity step while continuing to consume the canonical supported-year projection.
