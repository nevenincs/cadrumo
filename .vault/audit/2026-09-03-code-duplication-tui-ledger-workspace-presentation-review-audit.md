---
tags:
  - '#audit'
  - '#code-duplication'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:ade2ee87052bbfcf12354374b62dbda19aa4e145894e50f8969d81f9e464fef8'
related:
  - "[[2026-09-03-code-duplication-inventory-command-spec-audit]]"
---
# `code-duplication` audit: `TUI Ledger workspace-presentation dedup review`

## Scope

Read-only review of `c8ebca310a` and `d3a87c3e10`, the TUI and Ledger architecture contracts, the complete affected Ledger presentation family, route/controller boundary, shipped locale changes, and the focused workspace, flow, and slice-three tests. The review assessed presentation-only extraction, single-scroll ownership, semantic focus, confirmation and submission behavior, local row/message/custody preservation, override typing, and clone evidence.

Re-reviewed the mechanical type remediation in `8cba4f3b0c` and `e29c1f1aae`. It changes only explicit Textual table casts, the context-manager annotation, and override markers; it adds no business, I/O, network, persistence, route, or submission behavior.

## Findings

### helper-basedpyright-contract | high | Resolved: the extracted helper now satisfies the static type contract

The original helper boundary passed query results inferred as `DataTable[Unknown]` to typed parameters and annotated an `@contextmanager` with deprecated `Iterator`. The remediation casts the two navigation query results to `DataTable[str]`, changes the generator annotation to `Generator`, and marks the shared overrides. Basedpyright now reports zero errors, warnings, and notes across the Ledger package.

### global-clone-measurement | low | Retained official clone evidence is unchanged by this mechanical patch

No global scan was run during the re-review, as the patch has no clone-affecting behavior and the current load does not permit the expensive recipe. The prior official product scan evidence of 66 clone groups and 0.29 percent duplicated lines remains the authoritative global measurement. The controller-to-route composition signature remains intentionally non-substitutable: the outer factory validates dependencies before closure creation, while the controller validates the already-injected dependencies against context, projection, visible identities, and local admission.

## Recommendations

Approve the remediation. Retain the 45 focused Ledger interaction tests and whole-package basedpyright check with future presentation extractions.
