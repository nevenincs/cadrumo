---
tags:
  - '#exec'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-10'
step_id: 'S12'
related:
  - "[[2026-06-26-binding-adr-corpus-reconciliation-plan]]"
---

# RE-TARGET the 13 cross-campaign Status pointers from the apex to the phase+foundational ADRs per the re-target mapping (source-kind to phase-2.1

## Scope

- `carry to live-iva-compensation-wallet`
- `resolver-contract to calculation-source-connectivity`
- `future phase ADRs named in prose)`
- `.vault/adr/`

## Description

- Reconstruct the execution record for the already-checked S12 row.
- Confirm the cross-campaign status-pointer retargets from the apex to phase and foundational ADRs.
- Verify current ADR status text for the carry anchor, routing/carry, carry-continuity, and per-ADR rework set.

## Outcome

- S12 is backed by landed evidence. The corpus no longer points at the rejected
  apex as canonical authority; affected status blocks name phase 2.1 for
  source-kind, the live IVA wallet ADR for compensacion carry, future phase 2.2
  for resolver-contract folding, future phase 2.3 for fold-in/carry, and future
  phase 2.4 for vocabulary/CLI.
- Representative evidence commits include `4c0e76a55d`, `d644ff01dc`,
  `7f6ce3d21e`, `c9432500c9`, `c2ff972dfd`, `cd0bc3e00d`, `648f290cb6`,
  `0ebf3fabe0`, `e511d8fed3`, `2ba5c1cc8d`, `ef2f812532`, `83e6a083a7`,
  `ce0f6990c8`, and `3edc8eba23`.
- No source code or plan checkbox was changed in this reconciliation pass.

## Notes

- Reconstructed on 2026-07-05 because the step was checked without an exec record.
- Evidence commands included `rg -n "central apex doc|future phase-2" .vault/adr`
  and targeted `git blame` over the status blocks for the carry anchor, routing
  carry, and carry-continuity ADRs.
