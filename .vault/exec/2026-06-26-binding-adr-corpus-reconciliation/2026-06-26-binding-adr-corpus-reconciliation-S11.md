---
tags:
  - '#exec'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S11'
related:
  - "[[2026-06-26-binding-adr-corpus-reconciliation-plan]]"
---

# DEMOTE the apex central ADR: set status to rejected with a note (apex declined by operator

## Scope

- `C1-C6 analysis preserved in the research doc + this plan's verdict table`
- `canonical direction = phase + foundational ADRs)`
- `do NOT convert to research`
- `.vault/adr/2026-06-26-bindings-architecture-unification-adr.md`

## Description

- Reconstruct the execution record for the already-checked S11 row.
- Confirm commit `3edc8eba23` demoted `2026-06-26-bindings-architecture-unification-adr.md` to rejected.
- Verify the demotion note preserves C1-C6 analysis as input while denying apex authority.

## Outcome

- S11 is backed by landed evidence. The central bindings architecture apex ADR is
  rejected, the operator no-apex directive is recorded, and the canonical
  direction is the phase and foundational ADR set.
- No source code or plan checkbox was changed in this reconciliation pass.

## Notes

- Reconstructed on 2026-07-05 because the step was checked without an exec record.
- Evidence command: `git show --stat --oneline 3edc8eba23`.
