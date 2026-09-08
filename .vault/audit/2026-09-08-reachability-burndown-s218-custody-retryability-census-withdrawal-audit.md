---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:6b924d9e6314365a047849d39714a87ceb94011d9b9ad9f7827ba351cb2b97b8'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S218]]"
---

# `reachability-burndown` audit: `S218 custody retryability census withdrawal review`

## Scope

Independent materiality review of W05.P12.S218, covering deletion of the orphaned custody retryable-code declaration census, the authoritative error registrations, the retained type/AST-derived handler-flattening gate and its planted controls, exact orphan evidence, residue and Ruff evidence, and the S218 Step Record.

## Findings

No critical, high, medium, or low findings.

The deleted test was a second development ledger. It selected ownership using hand-maintained qualified-name fragments, repeated seven registered code identities in `_RETRYABLE_BECAUSE`, attached prose dispositions to that copied set, and tested both missing and stale census entries. It did not execute retry behavior or a handler boundary. The error registry remains the executable authority for each error type, code, category, message key, and `retryable` decision; focused behavioral tests continue to protect the important permanent duplicate-label versus retryable stale-witness distinction.

The retained handler-flattening gate is materially stronger for the defect class it owns. It derives divergent retryability pairs from registered error types and real subclassing, scans handler ASTs rather than copied code names, proves the registry result is nonempty, proves source-package traversal is nonempty, and carries positive flattening and negative routed planted controls. Its current red result found two real handlers that collapse divergent retryability. That is a valid next live finding, not a regression caused by deleting the independent census.

Exact residue contains none of the deleted test identity, `_RETRYABLE_BECAUSE`, or `_OWNED_QUALNAME_FRAGMENTS`. Ruff passes for the retained gate. The exact reachability record honestly shows orphaned tests falling from 16 to 15 while the remaining graph is reported as 62 unreachable modules, 311 exact unused symbols, and 2028/2091 reachable shipped modules.

## Recommendations

Approve W05.P12.S218. Pursue the two handler-flattening findings through their owning error-translation paths; do not restore or widen a retryable-code census, package-fragment list, or prose disposition map to make the retained gate green.
