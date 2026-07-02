---
tags:
  - '#exec'
  - '#arch-remediation-lazy-import-policy'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S04'
related:
  - "[[2026-07-02-arch-remediation-lazy-import-policy-plan]]"
---

# Sweep every current unsanctioned function-local import site and record each in the allowlist with its class, reason, and restructuring disposition, entering the error-registry deferred-bind queue and named cycle-breakers with their existing ADR citations

## Scope

- `src/aeat/tests/test_lazy_import_policy.py`

## Description

- Sweep every current unsanctioned function-local first-party import site with the gate's own AST walk at HEAD (2026-07-02) and record all 655 runtime-graph edges in `_ALLOWLIST`, grouped by `UnsanctionedClass`.
- Enter the error-registry deferred-bind queue (`ERROR_REGISTRY_BOOTSTRAP`) and the named `_coverage` cycle break (`NAMED_CYCLE_BREAK`) with their ADR-cited class metadata; file the domain-to-adapters seam under `PORTS_INVERSION_PENDING` with the delete-via-ports-inversion disposition.

## Outcome

Baseline refreshed to HEAD-at-commit: 451 edges / 727 sites. Per-class edge counts -- APPLICATION_DEFERRAL 301, ADAPTER_INTERNAL_DEFERRAL 74, DOMAIN_CYCLE_BREAK 33, CORE_INTERNAL_DEFERRAL 27, PORTS_INVERSION_PENDING 12, ERROR_REGISTRY_BOOTSTRAP 3, NAMED_CYCLE_BREAK 1. The start-of-execution HEAD held 655 edges / 1181 sites; the concurrent import-centralization and ports-inversion campaigns removed ~200 function-local first-party edges during execution (free decreases under the subset ratchet), and the submission-repository relocation added the adapter edges, so the committed baseline is the current-HEAD snapshot regenerated from the gate's own discovery. `test_every_allowlisted_edge_is_classified_where_filed` confirms every edge sits under the class its consumer/target imply.

## Notes

The allowlist is asserted a SUPERSET of the live discovered set, so the concurrent ports-inversion and import-centralization campaigns' edge removals lower the live count freely and never force an edit here.
