---
tags:
  - '#audit'
  - '#ledger-hardening-close'
date: '2026-06-11'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
  - '[[2026-06-11-ledger-hardening-close-audit]]'
---

# `ledger-hardening-close` audit: `close honesty review pass 2`

## Scope

Fresh inherited-state review after commit `da5b1c5e0`, which retired the C4 `AggregationSourceKind.INVOICE` alias and reconciled the C4 plan from 23/30 to 29/30.

## Findings

### HIGH - Full-tree collection is still not green

The C4 alias-retirement implementation is verified by focused lint, aggregation/operator/registry tests, API-stub conformance, documented-command conformance, and JSON schema conformance. The exact C4 full collect-only gate remains open: `uv run --no-sync pytest --collect-only -q src/aeat` currently collects 14,689 selected tests and stops with 20 collection errors before a green full-tree answer is possible.

Tracking: `P04.S24` remains open in `2026-06-10-ledger-invoice-unification-plan`, with the current failure signature recorded in the S24 exec note.

### MEDIUM - Remaining collection failures are outside the C4 alias-retirement surface

The current collection errors are support-module export splits and peer campaign drift: declaracion verification-chain support, AEAT auth support, secure-object support, runtime migrated repository support, ledger action support, modelo file-flow support, registry referential/schema support, `_validate_semantic_roles`, and `LedgerPeriodPayload`. These are not introduced by the C4 alias deletion and should not be patched opportunistically from the ledger close pass.

Tracking: do not create C4 implementation steps for these; wait for owning campaigns or route to their active plans.

### LOW - C4 alias-retirement claim is now structurally backed

The prior close audit's C4 HIGH finding is no longer current. `AggregationSourceKind.INVOICE` has been removed, production `src/aeat` has no remaining references, the operator taxonomy now matches the core taxonomy exactly, and registry invoice-shaped validation routes through canonical invoice source kinds.

Tracking: C4 remains open only because `P04.S24` is a full-tree verification gate and the tree is not currently collect-clean.

## Recommendations

- Treat C4 authoring as complete except for the full-tree collect-only gate.
- Do not mark the ledger hardening epic structurally complete until `P04.S24` can be checked green or formally deferred by a follow-up campaign that owns the repository-wide support-split cleanup.
- Continue using focused green ledger gates while the shared factory tree is in peer churn.

## Codification candidates

- **Source:** HIGH finding above. **Rule slug:** `full-tree-gate-must-distinguish-owner`. **Rule:** When a required full-tree gate is red, record the exact current failure signatures and distinguish owner-surface failures from unrelated factory churn before marking a feature step complete.
