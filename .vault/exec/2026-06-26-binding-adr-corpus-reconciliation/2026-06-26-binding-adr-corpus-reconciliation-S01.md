---
tags:
  - '#exec'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S01'
related:
  - "[[2026-06-26-binding-adr-corpus-reconciliation-plan]]"
---

# REWORK: re-point the bindings-interface-hardening Status from the apex to the phase ADRs (registry to registry+mesh via phase 2.1

## Scope

- `typed-op to relations via phase 2.3)`
- `.vault/adr/2026-06-14-bindings-interface-hardening-adr.md`

## Description

- Reconstruct the execution record for the already-checked S01 row.
- Confirm commit `c9432500c9` reworked `2026-06-14-bindings-interface-hardening-adr.md`.
- Verify the status block now points at the phase ADRs rather than a central apex.

## Outcome

- S01 is backed by landed evidence. The bindings-interface-hardening ADR remains
  accepted and foundational while its extension points are assigned to phase 2.1
  (`BindingSourceKind` registry-to-mesh widening) and future phase 2.3
  (typed aggregation discipline for relations).
- No source code or plan checkbox was changed in this reconciliation pass.

## Notes

- Reconstructed on 2026-07-05 because the step was checked without an exec record.
- Evidence command: `git show --stat --oneline c9432500c9`.
