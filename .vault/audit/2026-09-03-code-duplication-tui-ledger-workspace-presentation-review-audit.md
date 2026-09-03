---
tags:
  - '#audit'
  - '#code-duplication'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:923d4b5b9f0af402cdec05f75e9c17b0f07b4e15e1423e210bd847d90340b1fa'
related:
  - "[[2026-09-03-code-duplication-inventory-command-spec-audit]]"
---
# `code-duplication` audit: `TUI Ledger workspace-presentation dedup review`

## Scope

Read-only review of `c8ebca310a` and `d3a87c3e10`, the TUI and Ledger architecture contracts, the complete affected Ledger presentation family, route/controller boundary, shipped locale changes, and the focused workspace, flow, and slice-three tests. The review assessed presentation-only extraction, single-scroll ownership, semantic focus, confirmation and submission behavior, local row/message/custody preservation, override typing, and clone evidence.

The 45 focused Ledger tests passed. Ruff and ty passed. A scoped Ledger clone scan found three retained groups: two test-only groups and the controller-to-route composition signature group. The latter is non-substitutable presentation wiring: the outer factory accepts its composed dependencies and validates catalogue actions before closure creation, while the controller accepts the same already-injected dependencies to validate context, projection, visible identities, and local submission admission. Sharing it would turn an explicit typed composition boundary into a propagation bag without removing duplicated behavior.

## Findings

### helper-basedpyright-contract | high | The newly extracted helper fails the required static type gate

Basedpyright reports three errors in the changed surface. The two callers of `restore_transaction_focus` supply a query result inferred as `DataTable[Unknown]` to the helper's `DataTable[str]` parameter, and the `@contextmanager` return annotation uses deprecated `Iterator` rather than `Generator`. The 45 interaction tests and ty do not cover this stricter type contract, so the claimed type completion is incomplete.

### global-clone-measurement | low | The global product clone reduction is not independently attested

The repository duplication recipe did not produce a result during the available command window; its configured product scan may run for up to five minutes. The completed scoped Ledger scan confirms the intended screen-layout and confirmation-flow clones are removed from production screens, but it cannot establish a repository-wide clone decrease. The remaining controller-to-route signature group is intentionally non-substitutable as described in scope.

## Recommendations

1. Correct the helper's generic boundary and context-manager return annotation, then require Ruff, ty, and basedpyright to pass over the Ledger package before closure.
2. Re-run the canonical whole-product duplication recipe to completion and record its actual result; do not represent the scoped scan as global evidence.
